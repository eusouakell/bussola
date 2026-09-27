"""Aplica o DDL de ``contracts/bigquery/*.sql`` no BigQuery (FR-020, contratos §3).

Cria, de forma idempotente e na região de ``GOOGLE_CLOUD_LOCATION``
(``bussola_mcp.config.local_gcp``), os datasets ``bussola_dados``,
``bussola_app`` e ``bussola_app_dev`` com as tabelas deles (o RAG não usa BigQuery;
Q-17):

- só aceita ``CREATE SCHEMA IF NOT EXISTS`` e ``CREATE TABLE IF NOT EXISTS``
  (qualquer outra instrução aborta antes de executar), então rodar de novo não
  altera nada;
- ``bussola_app_dev`` recebe o DDL de ``bussola_app.sql`` com o identificador do
  dataset trocado (``--dataset-app-dev``, padrão ``bussola_app_dev``);
- os jobs rodam com ``project=GOOGLE_CLOUD_PROJECT`` (os ``.sql`` usam nomes sem projeto);
- depois de aplicar, compara o schema real de cada tabela com o DDL (nome, tipo e
  modo) e a localização de cada dataset. Divergências são **reportadas**, nunca
  corrigidas.

Uso, com ADC (``gcloud auth application-default login``)::

    uv run --project mcp_server python data/scripts/aplicar_ddl.py --dry-run
    uv run --project mcp_server python data/scripts/aplicar_ddl.py

Códigos de saída: 0 (ok), 2 (projeto ausente ou DDL inválido), 3 (schema divergente).
"""

import argparse
import re
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bussola_mcp import config

# A raiz do repositório, a região e o dataset de dados têm um dono só:
# ``bussola_mcp.config`` (contratos §7). Aqui só se lê de lá.
RAIZ_REPO = config.RAIZ_REPOSITORIO
DIR_DDL = RAIZ_REPO / "contracts" / "bigquery"
LOCALIZACAO = config.LOCAL_GCP_PADRAO
"""Região padrão. O valor efetivo vem de :func:`config.local_gcp`."""

DATASET_DADOS = config.DATASET_DADOS_PADRAO
DATASET_APP = "bussola_app"
DATASET_APP_DEV = "bussola_app_dev"
# Arquivo de DDL → dataset que ele declara.
ARQUIVOS_DDL: dict[str, str] = {
    "bussola_dados.sql": DATASET_DADOS,
    "bussola_app.sql": DATASET_APP,
}
DATASETS_CONTRATO = frozenset(ARQUIVOS_DDL.values())

_RE_IDENTIFICADOR = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,1023}")
_RE_SCHEMA = re.compile(
    r"CREATE\s+SCHEMA\s+IF\s+NOT\s+EXISTS\s+`?(?P<dataset>[\w-]+)`?(?P<resto>.*)",
    re.IGNORECASE | re.DOTALL,
)
_RE_TABELA = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(?P<nome>[`\w.-]+)\s*\(",
    re.IGNORECASE | re.DOTALL,
)
_RE_LOCALIZACAO = re.compile(r"\blocation\s*=\s*(['\"])(?P<valor>.*?)\1", re.IGNORECASE)
_RE_NOT_NULL = re.compile(r"\bNOT\s+NULL\b", re.IGNORECASE)
_RE_OPTIONS = re.compile(r"\bOPTIONS\s*\(", re.IGNORECASE)

# Nome da API do BigQuery (SchemaField.field_type) → nome do DDL.
_ALIAS_TIPO = {"INTEGER": "INT64", "FLOAT": "FLOAT64", "BOOLEAN": "BOOL"}


class ErroDDL(Exception):
    """DDL fora do formato aceito (não idempotente, malformado ou dataset inesperado)."""


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str  # normalizado: maiúsculas, sem espaços em ``ARRAY<...>``
    obrigatoria: bool  # NOT NULL


@dataclass(frozen=True)
class Instrucao:
    tipo: str  # "schema" | "tabela"
    dataset: str
    tabela: str | None
    sql: str
    colunas: tuple[Coluna, ...] = ()
    localizacao: str | None = None

    @property
    def alvo(self) -> str:
        return self.dataset if self.tabela is None else f"{self.dataset}.{self.tabela}"


# ---------------------------------------------------------------------------
# Parser (funções puras)
# ---------------------------------------------------------------------------


def remover_comentarios(texto: str) -> str:
    """Remove comentários ``--``, ``#`` e ``/* */`` fora de aspas e crases."""
    saida: list[str] = []
    i, n = 0, len(texto)
    aspas: str | None = None
    while i < n:
        c = texto[i]
        if aspas:
            saida.append(c)
            if c == "\\" and i + 1 < n:
                saida.append(texto[i + 1])
                i += 2
                continue
            if c == aspas:
                aspas = None
            i += 1
            continue
        if c in "'\"`":
            aspas = c
            saida.append(c)
            i += 1
        elif texto.startswith("--", i) or c == "#":
            fim = texto.find("\n", i)
            i = n if fim == -1 else fim
        elif texto.startswith("/*", i):
            fim = texto.find("*/", i + 2)
            if fim == -1:
                raise ErroDDL("comentário de bloco sem fechamento")
            saida.append(" ")
            i = fim + 2
        else:
            saida.append(c)
            i += 1
    if aspas:
        raise ErroDDL("texto entre aspas sem fechamento")
    return "".join(saida)


def _dividir_no_topo(texto: str, separador: str) -> list[str]:
    """Divide ``texto`` em ``separador`` fora de aspas, parênteses e ``<...>``."""
    partes: list[str] = []
    atual: list[str] = []
    aspas: str | None = None
    profundidade = 0
    for c in texto:
        if aspas:
            if c == aspas:
                aspas = None
        elif c in "'\"`":
            aspas = c
        elif c in "(<":
            profundidade += 1
        elif c in ")>":
            profundidade -= 1
        elif c == separador and profundidade == 0:
            partes.append("".join(atual))
            atual = []
            continue
        atual.append(c)
    partes.append("".join(atual))
    return [parte.strip() for parte in partes if parte.strip()]


def dividir_instrucoes(texto: str) -> list[str]:
    """Instruções separadas por ``;`` (o texto já deve estar sem comentários)."""
    return _dividir_no_topo(texto, ";")


def _fechamento(texto: str, abertura: int) -> int:
    profundidade = 0
    aspas: str | None = None
    for i in range(abertura, len(texto)):
        c = texto[i]
        if aspas:
            if c == aspas:
                aspas = None
        elif c in "'\"`":
            aspas = c
        elif c == "(":
            profundidade += 1
        elif c == ")":
            profundidade -= 1
            if profundidade == 0:
                return i
    raise ErroDDL("parêntese sem fechamento na definição da tabela")


def _normalizar_tipo(tipo: str) -> str:
    tipo = re.sub(r"\s+", " ", tipo.strip().upper())
    return re.sub(r"\s*([<>,])\s*", r"\1", tipo)


def _parse_coluna(definicao: str) -> Coluna:
    m = re.fullmatch(r"`?(?P<nome>\w+)`?\s+(?P<resto>.+)", definicao, re.DOTALL)
    if m is None:
        raise ErroDDL("definição de coluna inválida")
    resto = _RE_OPTIONS.split(m["resto"], maxsplit=1)[0]
    obrigatoria = _RE_NOT_NULL.search(resto) is not None
    tipo = _normalizar_tipo(_RE_NOT_NULL.sub(" ", resto))
    if not tipo:
        raise ErroDDL(f"coluna {m['nome']} sem tipo")
    return Coluna(nome=m["nome"], tipo=tipo, obrigatoria=obrigatoria)


def _parse_instrucao(sql: str) -> Instrucao:
    if m := _RE_SCHEMA.fullmatch(sql):
        loc = _RE_LOCALIZACAO.search(m["resto"])
        return Instrucao(
            tipo="schema",
            dataset=m["dataset"],
            tabela=None,
            sql=sql,
            localizacao=loc["valor"] if loc else None,
        )
    if m := _RE_TABELA.match(sql):
        partes = m["nome"].replace("`", "").split(".")
        if len(partes) != 2 or not all(partes):
            raise ErroDDL("use nomes de tabela no formato dataset.tabela, sem projeto")
        abertura = m.end() - 1
        corpo = sql[abertura + 1 : _fechamento(sql, abertura)]
        colunas = tuple(_parse_coluna(c) for c in _dividir_no_topo(corpo, ","))
        if not colunas:
            raise ErroDDL(f"tabela {m['nome']} sem colunas")
        nomes = [c.nome.lower() for c in colunas]
        if len(set(nomes)) != len(nomes):
            raise ErroDDL(f"coluna repetida em {m['nome']}")
        return Instrucao(
            tipo="tabela", dataset=partes[0], tabela=partes[1], sql=sql, colunas=colunas
        )
    primeira_linha = re.sub(r"\s+", " ", sql)[:60]
    if re.match(r"CREATE\s+(SCHEMA|TABLE)\b", sql, re.IGNORECASE):
        raise ErroDDL(f"instrução não idempotente (exige IF NOT EXISTS): {primeira_linha}")
    raise ErroDDL(f"instrução não suportada (só CREATE ... IF NOT EXISTS): {primeira_linha}")


def parse_ddl(texto: str) -> list[Instrucao]:
    """Instruções de um arquivo de DDL. Aborta em qualquer instrução não idempotente."""
    return [_parse_instrucao(sql) for sql in dividir_instrucoes(remover_comentarios(texto))]


def validar_nome_dataset(nome: str) -> str:
    """Nome de dataset válido e diferente dos datasets do contrato."""
    if not _RE_IDENTIFICADOR.fullmatch(nome):
        raise ErroDDL("nome de dataset inválido (use letras, dígitos e _)")
    if nome in DATASETS_CONTRATO:
        raise ErroDDL(f"o dataset de desenvolvimento não pode ser {nome}")
    return nome


def trocar_dataset(texto: str, destino: str, origem: str = DATASET_APP) -> str:
    """Troca o identificador ``origem`` por ``destino`` (comentários são removidos antes).

    Só troca o identificador inteiro: ``bussola_app.planos`` vira ``<destino>.planos``,
    mas ``bussola_app_dev`` e ``x.bussola_app`` ficam como estão.
    """
    validar_nome_dataset(destino)
    padrao = re.compile(r"(?<![\w.])" + re.escape(origem) + r"(?!\w)")
    return padrao.sub(destino, remover_comentarios(texto))


def _instrucoes_do_arquivo(texto: str, dataset: str, arquivo: str) -> list[Instrucao]:
    instrucoes = parse_ddl(texto)
    if not any(i.tipo == "schema" for i in instrucoes):
        raise ErroDDL(f"{arquivo}: falta CREATE SCHEMA IF NOT EXISTS {dataset}")
    for instrucao in instrucoes:
        if instrucao.dataset != dataset:
            raise ErroDDL(f"{arquivo}: {instrucao.alvo} fora do dataset {dataset}")
    return instrucoes


def montar_plano(
    dir_ddl: Path | str = DIR_DDL, dataset_app_dev: str = DATASET_APP_DEV
) -> list[Instrucao]:
    """Instruções na ordem de aplicação: dados, app e a cópia de app em ``dataset_app_dev``."""
    base = Path(dir_ddl)
    plano: list[Instrucao] = []
    for arquivo, dataset in ARQUIVOS_DDL.items():
        texto = (base / arquivo).read_text(encoding="utf-8")
        plano += _instrucoes_do_arquivo(texto, dataset, arquivo)
        if dataset == DATASET_APP:
            copia = trocar_dataset(texto, dataset_app_dev)
            plano += _instrucoes_do_arquivo(copia, dataset_app_dev, f"{arquivo} (cópia)")
    return plano


# ---------------------------------------------------------------------------
# Comparação com o schema real (pura)
# ---------------------------------------------------------------------------


def campo_esperado(coluna: Coluna) -> tuple[str, str]:
    """``(tipo, modo)`` que o BigQuery deve mostrar para a coluna do DDL."""
    if m := re.fullmatch(r"ARRAY<(.+)>", coluna.tipo):
        return _ALIAS_TIPO.get(m[1], m[1]), "REPEATED"
    return _ALIAS_TIPO.get(coluna.tipo, coluna.tipo), (
        "REQUIRED" if coluna.obrigatoria else "NULLABLE"
    )


def comparar_schema(colunas_ddl: Iterable[Coluna], campos_reais: Iterable[Any]) -> list[str]:
    """Diferenças entre o DDL e o schema real (objetos com ``name``, ``field_type``, ``mode``)."""
    esperadas = {c.nome.lower(): c for c in colunas_ddl}
    reais = {campo.name.lower(): campo for campo in campos_reais}
    diferencas: list[str] = []
    for nome, coluna in esperadas.items():
        campo = reais.get(nome)
        if campo is None:
            diferencas.append(f"coluna {coluna.nome} ausente na tabela")
            continue
        tipo, modo = campo_esperado(coluna)
        tipo_real = _normalizar_tipo(str(campo.field_type))
        tipo_real = _ALIAS_TIPO.get(tipo_real, tipo_real)
        modo_real = str(campo.mode or "NULLABLE").upper()
        if tipo_real != tipo:
            diferencas.append(f"coluna {coluna.nome}: tipo {tipo_real}, DDL {tipo}")
        if modo_real != modo:
            diferencas.append(f"coluna {coluna.nome}: modo {modo_real}, DDL {modo}")
    for nome, campo in reais.items():
        if nome not in esperadas:
            diferencas.append(f"coluna {campo.name} existe na tabela e não no DDL")
    return diferencas


def comparar_localizacao(esperada: str | None, real: str | None) -> list[str]:
    if esperada is None or (real or "").lower() == esperada.lower():
        return []
    return [f"localização {real}, DDL {esperada}"]


# ---------------------------------------------------------------------------
# Execução (única parte com BigQuery)
# ---------------------------------------------------------------------------


def aplicar(cliente: Any, plano: Sequence[Instrucao]) -> None:
    """Executa as instruções na ordem (todas ``IF NOT EXISTS``)."""
    for instrucao in plano:
        cliente.query(instrucao.sql, location=instrucao.localizacao or config.local_gcp()).result()
        print(f"aplicado: {instrucao.alvo}")


def verificar(cliente: Any, projeto: str, plano: Sequence[Instrucao]) -> list[str]:
    """Compara datasets e tabelas reais com o plano. Não altera nada."""
    from google.api_core.exceptions import NotFound

    divergencias: list[str] = []
    for instrucao in plano:
        alvo = f"{projeto}.{instrucao.alvo}"
        try:
            if instrucao.tipo == "schema":
                real = cliente.get_dataset(alvo).location
                diferencas = comparar_localizacao(instrucao.localizacao, real)
            else:
                diferencas = comparar_schema(instrucao.colunas, cliente.get_table(alvo).schema)
        except NotFound:
            diferencas = ["não encontrado após aplicar o DDL"]
        divergencias += [f"{instrucao.alvo}: {d}" for d in diferencas]
    return divergencias


def _criar_cliente_bigquery(projeto: str) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=projeto, location=config.local_gcp())


def _imprimir_plano(plano: Sequence[Instrucao], projeto: str | None) -> None:
    print(f"-- dry-run: nada será executado (projeto: {projeto or 'não definido'})")
    datasets = list(dict.fromkeys(i.dataset for i in plano))
    print(f"-- datasets: {', '.join(datasets)}")
    for instrucao in plano:
        print(f"\n-- {instrucao.alvo}\n{instrucao.sql};")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aplicar_ddl.py",
        description=(
            "Aplica contracts/bigquery/*.sql de forma idempotente (bussola_dados, bussola_app "
            "e a cópia de desenvolvimento) e compara o schema real com o DDL."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="só mostra as instruções, sem criar cliente BigQuery",
    )
    parser.add_argument(
        "--dataset-app-dev",
        "--dataset-app",
        dest="dataset_app_dev",
        default=DATASET_APP_DEV,
        help=f"dataset que recebe o DDL de bussola_app (padrão: {DATASET_APP_DEV})",
    )
    parser.add_argument(
        "--projeto",
        default=None,
        help="projeto GCP dos jobs (padrão: variável GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--dir-ddl",
        type=Path,
        default=DIR_DDL,
        help="diretório dos .sql (padrão: contracts/bigquery na raiz do repositório)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    criar_cliente: Callable[[str], Any] = _criar_cliente_bigquery,
) -> int:
    args = _parser().parse_args(argv)
    projeto = args.projeto or config.projeto_gcp()
    try:
        plano = montar_plano(args.dir_ddl, args.dataset_app_dev)
    except (ErroDDL, OSError) as exc:
        print(f"Erro no DDL: {exc}", file=sys.stderr)
        return 2
    if args.dry_run:
        _imprimir_plano(plano, projeto)
        return 0
    if not projeto:
        print("Erro: informe --projeto ou defina GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 2
    cliente = criar_cliente(projeto)
    aplicar(cliente, plano)
    divergencias = verificar(cliente, projeto, plano)
    if divergencias:
        print("Schema divergente do DDL (nada foi alterado):", file=sys.stderr)
        for divergencia in divergencias:
            print(f"  - {divergencia}", file=sys.stderr)
        return 3
    print(f"Schema conferido: {len(plano)} objetos sem divergência.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
