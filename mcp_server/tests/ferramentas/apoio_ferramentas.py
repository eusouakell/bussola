"""Apoio dos testes do ciclo 003: sessão MCP em memória, chamadas e dublês das portas.

Usa o cliente do SDK oficial (``ClientSession``) ligado ao servidor por streams em
memória, sem rede (decisão D-08 da spec).
"""

import io
import json
import logging
import uuid
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session

from bussola_mcp.contratos import (
    FERRAMENTAS,
    ID_ANCORA,
    Periodo,
    TemaConhecimento,
    Trecho,
)
from bussola_mcp.dominio.fakes import dir_fixtures_padrao
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.logging_json import configurar_logging
from bussola_mcp.server import create_server

DIR_OFICIAL = dir_fixtures_padrao()
UUID_DESCONHECIDO = str(uuid.UUID(int=0xB0550, version=4))
OBRIGATORIO = object()

TODAS = tuple(FERRAMENTAS)
BUSCA = "buscar_contexto_financeiro"
# Ferramentas que leem dados do cliente (a busca lê o corpus geral, Q-17).
FERRAMENTAS_CLIENTE = tuple(f for f in TODAS if f != BUSCA)

# Parâmetros adicionais de §5: nome → (tipos JSON, padrão ou OBRIGATORIO).
PARAMETROS_ESPERADOS: dict[str, dict[str, tuple[set[str], Any]]] = {
    "perfil_financeiro": {},
    "capacidade_poupanca": {},
    "oportunidades_corte": {"top_n": ({"integer"}, 5)},
    "dividas_e_parcelas": {},
    "simular_objetivo": {
        "valor_alvo": ({"number"}, OBRIGATORIO),
        "prazo_meses": ({"integer", "null"}, None),
        "aporte_mensal": ({"number", "null"}, None),
        "usar_saldo_atual": ({"boolean"}, False),
    },
    "comparar_cenarios": {
        "valor_alvo": ({"number"}, OBRIGATORIO),
        "prazo_meses": ({"integer"}, OBRIGATORIO),
    },
    "buscar_contexto_financeiro": {
        "pergunta": ({"string"}, OBRIGATORIO),
        "k": ({"integer"}, 5),
        "tema": ({"string", "null"}, None),
    },
    "resumo_mes": {"anomes": ({"integer"}, OBRIGATORIO)},
    "referencia_coorte": {"categoria": ({"string"}, OBRIGATORIO)},
}

# Argumentos mínimos válidos (além de id_usuario e ate_anomes) por ferramenta.
ARGUMENTOS_MINIMOS: dict[str, dict[str, Any]] = {
    "simular_objetivo": {"valor_alvo": 5000.0, "aporte_mensal": 250.0},
    "comparar_cenarios": {"valor_alvo": 5000.0, "prazo_meses": 12},
    BUSCA: {"pergunta": "Como funciona o rotativo do cartão?"},
    "resumo_mes": {"anomes": 202503},
    "referencia_coorte": {"categoria": "Lazer"},
}

RESTRICOES_DE_FAIXA = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
}


def argumentos(
    ferramenta: str, id_usuario: str = ID_ANCORA, ate_anomes: int = 202512, **extra: Any
) -> dict[str, Any]:
    return {
        "id_usuario": id_usuario,
        "ate_anomes": ate_anomes,
        **ARGUMENTOS_MINIMOS.get(ferramenta, {}),
        **extra,
    }


@asynccontextmanager
async def sessao(fixtures: Path | None = None, deps: ToolDependencies | None = None):
    """Sessão MCP em memória com o servidor real (fixtures ou portas injetadas)."""
    servidor = create_server(deps, fixtures_dir=fixtures if deps is None else None)
    async with create_connected_server_and_client_session(servidor) as cliente:
        yield cliente


async def chamar(cliente, ferramenta: str, argumentos_: dict[str, Any]) -> dict[str, Any]:
    """Chama a ferramenta e confere o formato do resultado (JSON estruturado e em texto)."""
    resultado = await cliente.call_tool(ferramenta, argumentos_)
    assert resultado.isError is False, "erro de negócio não usa isError"
    assert resultado.structuredContent is not None
    assert len(resultado.content) == 1 and resultado.content[0].type == "text"
    assert json.loads(resultado.content[0].text) == resultado.structuredContent
    envelope = resultado.structuredContent
    assert set(envelope) in ({"dados", "fonte", "avisos"}, {"erro"})
    return envelope


def codigo(envelope: dict[str, Any]) -> str | None:
    erro = envelope.get("erro")
    return erro.get("codigo") if isinstance(erro, dict) else None


def ler_golden(dir_fixtures: Path, nome_arquivo: str) -> dict[str, Any]:
    return json.loads((dir_fixtures / "ferramentas" / nome_arquivo).read_text(encoding="utf-8"))


def tipos_json(propriedade: dict[str, Any]) -> set[str]:
    if "anyOf" in propriedade:
        return {opcao["type"] for opcao in propriedade["anyOf"]}
    return {propriedade["type"]}


@contextmanager
def capturar_logs() -> Iterator[io.StringIO]:
    """Instala o ``JsonFormatter`` num buffer e restaura os handlers da raiz no fim."""
    raiz = logging.getLogger()
    handlers, nivel = list(raiz.handlers), raiz.level
    buffer = io.StringIO()
    configurar_logging("bussola-mcp", fluxo=buffer)
    try:
        yield buffer
    finally:
        for handler in list(raiz.handlers):
            raiz.removeHandler(handler)
        for handler in handlers:
            raiz.addHandler(handler)
        raiz.setLevel(nivel)


def linhas_json(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in buffer.getvalue().splitlines() if linha.strip()]


# ---------------------------------------------------------------------------
# Dublês das portas
# ---------------------------------------------------------------------------


@dataclass
class RepositorioEspiao:
    """Repositório que registra as chamadas e delega (ou falha com ``erro``)."""

    base: Any
    erro: BaseException | None = None
    chamadas: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def __getattr__(self, nome: str) -> Any:
        alvo = getattr(self.base, nome)

        def chamada(*args: Any, **kwargs: Any) -> Any:
            self.chamadas.append((nome, args + tuple(kwargs.values())))
            if self.erro is not None and nome != "usuario_existe":
                raise self.erro
            return alvo(*args, **kwargs)

        return chamada


@dataclass
class BuscadorEspiao:
    """Buscador que registra os argumentos recebidos e devolve ``trechos`` (ou falha)."""

    trechos: list[Trecho] = field(default_factory=list)
    erro: BaseException | None = None
    chamadas: list[dict[str, Any]] = field(default_factory=list)

    def buscar(self, pergunta: str, k: int, tema: TemaConhecimento | None = None) -> list[Trecho]:
        self.chamadas.append({"pergunta": pergunta, "k": k, "tema": tema})
        if self.erro is not None:
            raise self.erro
        return self.trechos[:k]


@dataclass
class CalculosFixos:
    """``FinancialComputations`` que devolve ``resultado`` (ou levanta ``erro``) e registra."""

    resultado: Computation | None = None
    erro: BaseException | None = None
    chamadas: list[tuple[str, tuple[Any, ...]]] = field(default_factory=list)

    def _responder(self, nome: str, *args: Any) -> Computation:
        self.chamadas.append((nome, args))
        if self.erro is not None:
            raise self.erro
        assert self.resultado is not None
        return self.resultado

    def perfil_financeiro(self, *args: Any) -> Computation:
        return self._responder("perfil_financeiro", *args)

    def capacidade_poupanca(self, *args: Any) -> Computation:
        return self._responder("capacidade_poupanca", *args)

    def oportunidades_corte(self, *args: Any) -> Computation:
        return self._responder("oportunidades_corte", *args)

    def dividas_e_parcelas(self, *args: Any) -> Computation:
        return self._responder("dividas_e_parcelas", *args)

    def simular_objetivo(self, *args: Any) -> Computation:
        return self._responder("simular_objetivo", *args)

    def comparar_cenarios(self, *args: Any) -> Computation:
        return self._responder("comparar_cenarios", *args)

    def resumo_mes(self, *args: Any) -> Computation:
        return self._responder("resumo_mes", *args)

    def referencia_coorte(self, *args: Any) -> Computation:
        return self._responder("referencia_coorte", *args)


class RepositorioSempreExiste:
    """Repositório mínimo: todo cliente existe e nenhuma leitura é esperada."""

    def usuario_existe(self, id_usuario: str) -> bool:
        return True


def periodo(inicio: int = 202501, fim: int = 202512) -> Periodo:
    return Periodo(inicio=inicio, fim=fim)
