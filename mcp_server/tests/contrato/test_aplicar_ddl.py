"""Testes offline de ``data/scripts/aplicar_ddl.py`` (T033, FR-020).

Parser do DDL, troca de dataset para ``bussola_app_dev``, ``--dry-run`` sem cliente e
aplicação com um cliente BigQuery falso (sem rede).
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from google.api_core.exceptions import NotFound
from google.cloud.bigquery import SchemaField

RAIZ_REPO = Path(__file__).resolve().parents[3]


def _carregar_script(nome: str) -> ModuleType:
    caminho = RAIZ_REPO / "data" / "scripts" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"bussola_scripts_{nome}", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ddl = _carregar_script("aplicar_ddl")

DATASETS = ["bussola_dados", "bussola_app", "bussola_app_dev"]


def _ler(arquivo: str) -> str:
    return (ddl.DIR_DDL / arquivo).read_text(encoding="utf-8")


def _tabelas(instrucoes: list[Any]) -> dict[str, Any]:
    return {i.alvo: i for i in instrucoes if i.tipo == "tabela"}


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def test_parse_bussola_dados() -> None:
    instrucoes = ddl.parse_ddl(_ler("bussola_dados.sql"))
    assert instrucoes[0].tipo == "schema"
    assert (instrucoes[0].dataset, instrucoes[0].localizacao) == ("bussola_dados", "us-central1")
    tabelas = _tabelas(instrucoes)
    assert list(tabelas) == [
        "bussola_dados.perfil_mensal",
        "bussola_dados.gastos_categoria",
        "bussola_dados.entradas_categoria",
        "bussola_dados.recorrentes",
        "bussola_dados.parcelas",
        "bussola_dados.categorias",
        "bussola_dados.referencia_coorte",
    ]
    perfil = tabelas["bussola_dados.perfil_mensal"].colunas
    assert len(perfil) == 10
    assert all(c.obrigatoria for i in tabelas.values() for c in i.colunas)
    assert (perfil[0].nome, perfil[0].tipo) == ("id_usuario", "STRING")
    assert (perfil[1].nome, perfil[1].tipo) == ("anomes", "INT64")
    categorias = tabelas["bussola_dados.categorias"].colunas
    assert [c.tipo for c in categorias] == ["STRING", "STRING", "BOOL", "FLOAT64"]


def test_sem_dataset_de_rag() -> None:
    """O RAG lê o corpus do repositório, não o BigQuery (Q-17)."""
    assert not (ddl.DIR_DDL / "bussola_rag.sql").exists()
    assert "bussola_rag" not in ddl.DATASETS_CONTRATO


def test_parse_nulidade_e_array() -> None:
    texto = """
    CREATE TABLE IF NOT EXISTS d.t (
      doc_id STRING NOT NULL,
      anomes INT64,
      fonte JSON NOT NULL,
      embedding ARRAY<FLOAT64>,
      gerado_em TIMESTAMP NOT NULL
    );
    """
    (tabela,) = ddl.parse_ddl(texto)
    colunas = {c.nome: c for c in tabela.colunas}
    assert not colunas["anomes"].obrigatoria
    assert colunas["doc_id"].obrigatoria and colunas["fonte"].tipo == "JSON"
    assert (colunas["embedding"].tipo, colunas["embedding"].obrigatoria) == (
        "ARRAY<FLOAT64>",
        False,
    )
    assert ddl.campo_esperado(colunas["embedding"]) == ("FLOAT64", "REPEATED")
    assert ddl.campo_esperado(colunas["anomes"]) == ("INT64", "NULLABLE")
    assert ddl.campo_esperado(colunas["gerado_em"]) == ("TIMESTAMP", "REQUIRED")


def test_parse_bussola_app() -> None:
    tabelas = _tabelas(ddl.parse_ddl(_ler("bussola_app.sql")))
    assert list(tabelas) == [
        "bussola_app.planos",
        "bussola_app.consentimentos",
        "bussola_app.auditoria",
        "bussola_app.acompanhamento",
    ]
    opcionais = {
        alvo: [c.nome for c in instrucao.colunas if not c.obrigatoria]
        for alvo, instrucao in tabelas.items()
    }
    assert opcionais == {
        "bussola_app.planos": [],
        "bussola_app.consentimentos": ["plano_id"],
        "bussola_app.auditoria": ["ferramenta"],
        "bussola_app.acompanhamento": ["categoria_desvio", "acao_sugerida"],
    }


def test_parse_tipos_aninhados_options_e_comentarios() -> None:
    texto = """
    /* bloco; com ponto e vírgula */
    CREATE TABLE IF NOT EXISTS d.t (
      a ARRAY<STRUCT<x INT64, y STRING>>,  -- vírgula dentro de <>
      b STRING NOT NULL OPTIONS (description = "texto -- com; separadores, e aspas"),
      # comentário estilo BigQuery
      `c` numeric
    );
    """
    (tabela,) = ddl.parse_ddl(texto)
    assert [(c.nome, c.tipo, c.obrigatoria) for c in tabela.colunas] == [
        ("a", "ARRAY<STRUCT<X INT64,Y STRING>>", False),
        ("b", "STRING", True),
        ("c", "NUMERIC", False),
    ]
    assert "com; separadores" in tabela.sql


@pytest.mark.parametrize(
    ("sql", "trecho"),
    [
        ("CREATE TABLE d.t (a INT64);", "IF NOT EXISTS"),
        ("CREATE SCHEMA d;", "IF NOT EXISTS"),
        ("CREATE OR REPLACE TABLE d.t (a INT64);", "não suportada"),
        ("DROP TABLE d.t;", "não suportada"),
        ("ALTER TABLE d.t ADD COLUMN b INT64;", "não suportada"),
        ("INSERT INTO d.t VALUES (1);", "não suportada"),
        ("CREATE TABLE IF NOT EXISTS p.d.t (a INT64);", "sem projeto"),
        ("CREATE TABLE IF NOT EXISTS d.t (a INT64, A STRING);", "repetida"),
        ("CREATE TABLE IF NOT EXISTS d.t (a INT64;", "sem fechamento"),
        ("CREATE TABLE IF NOT EXISTS d.t (a INT64); /* aberto", "sem fechamento"),
    ],
)
def test_parse_rejeita_instrucao_nao_idempotente_ou_malformada(sql: str, trecho: str) -> None:
    with pytest.raises(ddl.ErroDDL, match=trecho):
        ddl.parse_ddl(sql)


def test_dividir_instrucoes_respeita_aspas() -> None:
    assert ddl.dividir_instrucoes("A 'x;y'; B \"z;\"; ;") == ["A 'x;y'", 'B "z;"']


# ---------------------------------------------------------------------------
# Troca de dataset (bussola_app_dev)
# ---------------------------------------------------------------------------


def test_trocar_dataset_so_troca_o_identificador() -> None:
    texto = (
        "-- bussola_app_dev usa o DDL de bussola_app\n"
        'CREATE SCHEMA IF NOT EXISTS bussola_app OPTIONS (location = "us-central1");\n'
        "CREATE TABLE IF NOT EXISTS bussola_app.planos (bussola_app_x STRING, y STRING);\n"
        "-- x.bussola_app e bussola_app_dev ficam\n"
        "CREATE TABLE IF NOT EXISTS bussola_app_dev.z (a STRING);"
    )
    trocado = ddl.trocar_dataset(texto, "bussola_app_dev")
    assert "--" not in trocado  # comentários são removidos antes da troca
    assert "IF NOT EXISTS bussola_app_dev OPTIONS" in trocado
    assert "bussola_app_dev.planos (bussola_app_x STRING" in trocado
    assert "bussola_app_dev.z" in trocado and "bussola_app_dev_dev" not in trocado
    assert re.search(r"\bbussola_app\b(?!_)", trocado) is None


@pytest.mark.parametrize(
    "nome", ["bussola app", "1dataset", "bussola-app", "", "bussola_app", "bussola_dados"]
)
def test_nome_de_dataset_invalido(nome: str) -> None:
    with pytest.raises(ddl.ErroDDL):
        ddl.trocar_dataset("CREATE SCHEMA IF NOT EXISTS bussola_app;", nome)


def test_plano_cria_os_tres_datasets() -> None:
    plano = ddl.montar_plano()
    assert list(dict.fromkeys(i.dataset for i in plano)) == DATASETS
    assert [i.alvo for i in plano if i.tipo == "schema"] == DATASETS
    assert len(plano) == 3 + 7 + 4 + 4
    app = {i.tabela: i.colunas for i in plano if i.dataset == "bussola_app" and i.tabela}
    dev = {i.tabela: i.colunas for i in plano if i.dataset == "bussola_app_dev" and i.tabela}
    assert dev == app
    for instrucao in plano:
        assert re.match(r"CREATE (SCHEMA|TABLE) IF NOT EXISTS ", instrucao.sql)
        if instrucao.dataset == "bussola_app_dev":
            assert re.search(r"\bbussola_app\b(?!_)", instrucao.sql) is None


def test_plano_com_outro_dataset_dev() -> None:
    plano = ddl.montar_plano(dataset_app_dev="bussola_app_teste")
    assert list(dict.fromkeys(i.dataset for i in plano))[-1] == "bussola_app_teste"


def test_plano_rejeita_tabela_fora_do_dataset_do_arquivo(tmp_path: Path) -> None:
    for arquivo in ddl.ARQUIVOS_DDL:
        (tmp_path / arquivo).write_text(_ler(arquivo), encoding="utf-8")
    (tmp_path / "bussola_dados.sql").write_text(
        _ler("bussola_dados.sql") + "\nCREATE TABLE IF NOT EXISTS bussola_app.x (a STRING);\n",
        encoding="utf-8",
    )
    with pytest.raises(ddl.ErroDDL, match="fora do dataset bussola_dados"):
        ddl.montar_plano(tmp_path)


# ---------------------------------------------------------------------------
# Comparação de schema
# ---------------------------------------------------------------------------


def _campos_de(instrucao: Any, alias: bool = True) -> list[SchemaField]:
    nomes_api = {"INT64": "INTEGER", "FLOAT64": "FLOAT", "BOOL": "BOOLEAN"}
    campos = []
    for coluna in instrucao.colunas:
        tipo, modo = ddl.campo_esperado(coluna)
        campos.append(SchemaField(coluna.nome, nomes_api.get(tipo, tipo) if alias else tipo, modo))
    return campos


def test_comparar_schema_aceita_aliases_da_api() -> None:
    plano = ddl.montar_plano()
    for instrucao in plano:
        if instrucao.tipo == "tabela":
            assert ddl.comparar_schema(instrucao.colunas, _campos_de(instrucao)) == []
            assert ddl.comparar_schema(instrucao.colunas, _campos_de(instrucao, False)) == []


def test_comparar_schema_reporta_diferencas() -> None:
    colunas = [
        ddl.Coluna("a", "INT64", True),
        ddl.Coluna("b", "STRING", False),
        ddl.Coluna("c", "ARRAY<FLOAT64>", False),
        ddl.Coluna("d", "STRING", True),
    ]
    reais = [
        SchemaField("A", "INTEGER", "REQUIRED"),  # nome sem diferenciar maiúsculas
        SimpleNamespace(name="b", field_type="STRING", mode=None),  # None = NULLABLE
        SchemaField("c", "FLOAT", "NULLABLE"),
        SchemaField("e", "STRING", "NULLABLE"),
    ]
    assert ddl.comparar_schema(colunas, reais) == [
        "coluna c: modo NULLABLE, DDL REPEATED",
        "coluna d ausente na tabela",
        "coluna e existe na tabela e não no DDL",
    ]
    assert ddl.comparar_schema(
        [ddl.Coluna("x", "STRING", True)], [SchemaField("x", "JSON", "REQUIRED")]
    ) == ["coluna x: tipo JSON, DDL STRING"]
    assert ddl.comparar_localizacao("us-central1", "US-CENTRAL1") == []
    assert ddl.comparar_localizacao("us-central1", "US") == ["localização US, DDL us-central1"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _fabrica_proibida(projeto: str) -> Any:
    raise AssertionError("não deveria criar cliente BigQuery")


def test_dry_run_nao_cria_cliente(capsys: pytest.CaptureFixture[str]) -> None:
    assert ddl.main(["--dry-run"], criar_cliente=_fabrica_proibida) == 0
    saida = capsys.readouterr().out
    assert "datasets: bussola_dados, bussola_app, bussola_app_dev" in saida
    assert "CREATE TABLE IF NOT EXISTS bussola_app_dev.planos (" in saida
    assert saida.count("CREATE SCHEMA IF NOT EXISTS") == 3


def test_dry_run_com_dataset_app(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["--dry-run", "--dataset-app", "bussola_app_teste", "--projeto", "p"]
    assert ddl.main(argv, criar_cliente=_fabrica_proibida) == 0
    saida = capsys.readouterr().out
    assert "CREATE TABLE IF NOT EXISTS bussola_app_teste.auditoria (" in saida
    assert "bussola_app_dev" not in saida and "(projeto: p)" in saida


def test_dataset_app_invalido(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["--dry-run", "--dataset-app", "bussola_app"]
    assert ddl.main(argv, criar_cliente=_fabrica_proibida) == 2
    assert "Erro no DDL" in capsys.readouterr().err


def test_sem_projeto_nao_cria_cliente(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert ddl.main([], criar_cliente=_fabrica_proibida) == 2
    assert "GOOGLE_CLOUD_PROJECT" in capsys.readouterr().err


class _Job:
    def result(self) -> None:
        return None


class ClienteFalso:
    """Registra as queries e devolve o schema do DDL (com ``divergentes`` alterado)."""

    def __init__(self, divergentes: dict[str, list[Any]] | None = None) -> None:
        self.queries: list[tuple[str, str]] = []
        self.divergentes = divergentes or {}
        self.plano = {i.alvo: i for i in ddl.montar_plano()}

    def query(self, sql: str, location: str | None = None) -> _Job:
        self.queries.append((sql, location))
        return _Job()

    def get_dataset(self, alvo: str) -> Any:
        return SimpleNamespace(location="us-central1")

    def get_table(self, alvo: str) -> Any:
        tabela = alvo.split(".", 1)[1]
        if tabela in self.divergentes:
            campos = self.divergentes[tabela]
            if campos is None:
                raise NotFound(tabela)
            return SimpleNamespace(schema=campos)
        return SimpleNamespace(schema=_campos_de(self.plano[tabela]))


def test_aplica_com_cliente_falso(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "projeto-teste")
    clientes: list[tuple[str, ClienteFalso]] = []

    def fabrica(projeto: str) -> ClienteFalso:
        clientes.append((projeto, ClienteFalso()))
        return clientes[-1][1]

    assert ddl.main([], criar_cliente=fabrica) == 0
    ((projeto, cliente),) = clientes
    assert projeto == "projeto-teste"
    assert len(cliente.queries) == 18
    assert all(loc == "us-central1" for _, loc in cliente.queries)
    assert all(re.match(r"CREATE (SCHEMA|TABLE) IF NOT EXISTS ", sql) for sql, _ in cliente.queries)
    assert "sem divergência" in capsys.readouterr().out


def test_schema_divergente_e_reportado_sem_alterar(capsys: pytest.CaptureFixture[str]) -> None:
    divergentes = {
        "bussola_app_dev.planos": [SchemaField("plano_id", "STRING", "NULLABLE")],
        "bussola_dados.categorias": None,
    }
    cliente = ClienteFalso(divergentes)
    assert ddl.main(["--projeto", "p"], criar_cliente=lambda _: cliente) == 3
    erro = capsys.readouterr().err
    assert "bussola_app_dev.planos: coluna plano_id: modo NULLABLE, DDL REQUIRED" in erro
    assert "bussola_app_dev.planos: coluna session_id ausente na tabela" in erro
    assert "bussola_dados.categorias: não encontrado após aplicar o DDL" in erro
    assert "nada foi alterado" in erro
    assert len(cliente.queries) == 18  # só os CREATE ... IF NOT EXISTS do plano
