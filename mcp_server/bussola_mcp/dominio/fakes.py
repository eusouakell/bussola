"""Fakes dos Protocols de domínio sobre ``contracts/fixtures/`` (contratos §4 e §8).

- :class:`RepositorioFake` lê ``bussola_dados/<tabela>.json`` e ``usuarios.json``.
- :class:`BuscadorFake` lê ``rag/trechos_exemplo.json``.

Os dois recebem o diretório de fixtures por parâmetro. ``None`` resolve para
``<raiz do repositório>/contracts/fixtures``. Os arquivos são lidos sob demanda,
na primeira consulta, e validados com os modelos de :mod:`bussola_mcp.contratos`.

Escopo e tempo (FR-010, constituição III e IV):

- leituras por cliente só devolvem linhas do ``id_usuario`` pedido, com
  ``anomes <= ate_anomes`` (e ``>= desde_anomes`` quando informado);
- o buscador aplica o filtro obrigatório de contratos §3: ``id_usuario`` do
  cliente **ou** ``tipo = "coorte"``, e ``anomes`` nulo **ou** ``<= ate_anomes``.

Formato aceito dos arquivos: uma lista JSON de linhas ou um objeto com a lista
numa chave conhecida (``usuarios``, ``linhas``, ``trechos`` ou
``dados.trechos``). Tabela ausente equivale a tabela vazia.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bussola_mcp.contratos import (
    Categoria,
    EntradaCategoria,
    GastoCategoria,
    Parcela,
    PerfilMes,
    Recorrente,
    RefCoorte,
    TipoDocumento,
    Trecho,
    UsuarioFixture,
)

# fakes.py → dominio → bussola_mcp → mcp_server → raiz do repositório.
RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]

ARQUIVO_USUARIOS = "usuarios.json"
DIR_TABELAS = "bussola_dados"
ARQUIVO_TRECHOS = Path("rag") / "trechos_exemplo.json"


def dir_fixtures_padrao() -> Path:
    """``<raiz do repositório>/contracts/fixtures``."""
    return RAIZ_REPOSITORIO / "contracts" / "fixtures"


def resolver_dir_fixtures(dir_fixtures: Path | str | None) -> Path:
    return dir_fixtures_padrao() if dir_fixtures is None else Path(dir_fixtures)


def ler_json(caminho: Path) -> Any | None:
    """Conteúdo JSON do arquivo, ou ``None`` se ele não existe."""
    if not caminho.is_file():
        return None
    with caminho.open(encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _extrair_linhas(conteudo: Any, chaves: tuple[str, ...]) -> list[Any]:
    if isinstance(conteudo, list):
        return conteudo
    if isinstance(conteudo, dict):
        for chave in chaves:
            valor = conteudo.get(chave)
            if isinstance(valor, list):
                return valor
            if isinstance(valor, dict):
                # Envelope ``{"dados": {"trechos": [...]}}`` de buscar_contexto_financeiro.
                try:
                    return _extrair_linhas(valor, chaves)
                except ValueError:
                    continue
    raise ValueError("formato de fixture não reconhecido")


def carregar_usuarios(dir_fixtures: Path | str | None = None) -> dict[str, UsuarioFixture] | None:
    """Usuários de ``usuarios.json`` indexados pelo ``id_usuario`` em minúsculas.

    Devolve ``None`` quando o arquivo não existe.
    """
    conteudo = ler_json(resolver_dir_fixtures(dir_fixtures) / ARQUIVO_USUARIOS)
    if conteudo is None:
        return None
    usuarios = [
        UsuarioFixture.model_validate(linha)
        for linha in _extrair_linhas(conteudo, ("usuarios", "linhas"))
    ]
    return {u.id_usuario.lower(): u for u in usuarios}


def _normalizar_id(id_usuario: str) -> str:
    return id_usuario.lower() if isinstance(id_usuario, str) else id_usuario


class RepositorioFake:
    """Implementa ``RepositorioFinanceiro`` sobre ``bussola_dados/<tabela>.json``."""

    def __init__(self, dir_fixtures: Path | str | None = None) -> None:
        self.dir_fixtures = resolver_dir_fixtures(dir_fixtures)
        self._tabelas: dict[str, list[Any]] = {}
        self._usuarios: dict[str, UsuarioFixture] | None = None

    # -- carga -------------------------------------------------------------

    def _tabela[M: BaseModel](self, nome: str, modelo: type[M]) -> list[M]:
        if nome not in self._tabelas:
            conteudo = ler_json(self.dir_fixtures / DIR_TABELAS / f"{nome}.json")
            linhas = [] if conteudo is None else _extrair_linhas(conteudo, ("linhas",))
            self._tabelas[nome] = [modelo.model_validate(linha) for linha in linhas]
        return self._tabelas[nome]

    def _usuarios_fixture(self) -> dict[str, UsuarioFixture]:
        if self._usuarios is None:
            self._usuarios = carregar_usuarios(self.dir_fixtures) or {}
        return self._usuarios

    def _por_cliente[M: BaseModel](
        self,
        nome: str,
        modelo: type[M],
        id_usuario: str,
        ate_anomes: int,
        desde_anomes: int | None = None,
    ) -> list[M]:
        alvo = _normalizar_id(id_usuario)
        linhas = [
            linha
            for linha in self._tabela(nome, modelo)
            if linha.id_usuario.lower() == alvo
            and linha.anomes <= ate_anomes
            and (desde_anomes is None or linha.anomes >= desde_anomes)
        ]
        return sorted(linhas, key=lambda linha: linha.anomes)

    # -- RepositorioFinanceiro --------------------------------------------

    def usuario_existe(self, id_usuario: str) -> bool:
        alvo = _normalizar_id(id_usuario)
        if alvo in self._usuarios_fixture():
            return True
        return any(p.id_usuario.lower() == alvo for p in self._tabela("perfil_mensal", PerfilMes))

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        return self._por_cliente("perfil_mensal", PerfilMes, id_usuario, ate_anomes)

    def gastos_categoria(
        self, id_usuario: str, ate_anomes: int, desde_anomes: int | None = None
    ) -> list[GastoCategoria]:
        return self._por_cliente(
            "gastos_categoria", GastoCategoria, id_usuario, ate_anomes, desde_anomes
        )

    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]:
        return self._por_cliente("entradas_categoria", EntradaCategoria, id_usuario, ate_anomes)

    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]:
        return self._por_cliente("recorrentes", Recorrente, id_usuario, ate_anomes)

    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]:
        return self._por_cliente("parcelas", Parcela, id_usuario, ate_anomes)

    def categorias(self) -> list[Categoria]:
        return list(self._tabela("categorias", Categoria))

    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]:
        return [
            ref
            for ref in self._tabela("referencia_coorte", RefCoorte)
            if ref.faixa_renda == faixa_renda and (macro is None or ref.macro == macro)
        ]

    # -- acréscimo ao contrato ---------------------------------------------

    def faixa_renda_de(self, id_usuario: str) -> str | None:
        """Faixa de renda do usuário em ``usuarios.json`` (``None`` se ausente)."""
        usuario = self._usuarios_fixture().get(_normalizar_id(id_usuario))
        return usuario.faixa_renda if usuario else None


# ---------------------------------------------------------------------------
# Buscador
# ---------------------------------------------------------------------------

_PALAVRAS_VAZIAS = frozenset(
    {
        "que",
        "com",
        "para",
        "por",
        "uma",
        "uns",
        "umas",
        "dos",
        "das",
        "nos",
        "nas",
        "meu",
        "minha",
        "meus",
        "minhas",
        "quanto",
        "qual",
        "quais",
        "como",
        "mais",
        "menos",
        "mes",
        "sobre",
        "isso",
        "esse",
        "essa",
        "este",
        "esta",
        "tem",
        "sao",
        "foi",
    }
)
_RE_PALAVRA = re.compile(r"\w+")


def tokens(texto: str) -> set[str]:
    """Palavras de 3+ letras, sem acento e em minúsculas, sem palavras vazias."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return {
        palavra
        for palavra in _RE_PALAVRA.findall(sem_acento.casefold())
        if len(palavra) >= 3 and palavra not in _PALAVRAS_VAZIAS
    }


class BuscadorFake:
    """Implementa ``BuscadorContexto`` sobre ``rag/trechos_exemplo.json``.

    A ordenação é determinística: sobreposição de palavras com a pergunta
    (decrescente) e, no empate, ``doc_id``. O ``score`` devolvido é a fração das
    palavras da pergunta presentes no trecho, com 4 casas.
    """

    def __init__(self, dir_fixtures: Path | str | None = None) -> None:
        self.dir_fixtures = resolver_dir_fixtures(dir_fixtures)
        self._trechos: list[Trecho] | None = None

    def _todos(self) -> list[Trecho]:
        if self._trechos is None:
            conteudo = ler_json(self.dir_fixtures / ARQUIVO_TRECHOS)
            linhas = [] if conteudo is None else _extrair_linhas(conteudo, ("trechos", "dados"))
            self._trechos = [Trecho.model_validate(linha) for linha in linhas]
        return self._trechos

    def buscar(self, id_usuario: str, pergunta: str, k: int, ate_anomes: int) -> list[Trecho]:
        alvo = _normalizar_id(id_usuario)
        permitidos = [
            trecho
            for trecho in self._todos()
            if (
                (trecho.origem.id_usuario is not None and trecho.origem.id_usuario.lower() == alvo)
                or trecho.tipo == TipoDocumento.COORTE
            )
            and (trecho.anomes is None or trecho.anomes <= ate_anomes)
        ]
        palavras = tokens(pergunta)
        pontuados: list[tuple[int, Trecho]] = [
            (len(palavras & tokens(trecho.texto)), trecho) for trecho in permitidos
        ]
        pontuados.sort(key=lambda item: (-item[0], item[1].doc_id))
        total = len(palavras) or 1
        return [
            trecho.model_copy(update={"score": round(sobreposicao / total, 4)})
            for sobreposicao, trecho in pontuados[: max(k, 0)]
        ]
