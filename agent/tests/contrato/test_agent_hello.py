"""Agente hello do 000 (FR-019): ``root_agent`` importável sem rede.

Importar ``bussola_agent.agent`` não abre conexão nem chama modelos (a guarda
de rede do conftest falha o teste se isso acontecer).
"""

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from google.adk.agents import Agent
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.sessions.state import State
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

import bussola_agent
from bussola_agent import callbacks, extensoes
from bussola_agent.estado import CHAVES
from bussola_agent.mcp_conexao import URL_PADRAO

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"
CONTROLE = "31e94f2f-1463-49f9-a41a-b3f220ed976a"
DIR_AGENTES = Path(__file__).resolve().parents[2]  # agent/


@pytest.fixture
def importar_de_novo(monkeypatch: pytest.MonkeyPatch) -> Callable[[], ModuleType]:
    """Importa ``bussola_agent.agent`` do zero; o módulo original volta no fim."""
    monkeypatch.setenv("ADK_DISABLE_LOAD_DOTENV", "TRUE")
    for chave in ("BUSSOLA_MODEL", "MCP_URL", "ANCHOR_USER_ID", "REPLAY_START_ANOMES"):
        monkeypatch.delenv(chave, raising=False)

    def importar() -> ModuleType:
        monkeypatch.delitem(sys.modules, "bussola_agent.agent", raising=False)
        monkeypatch.delattr(bussola_agent, "agent", raising=False)
        return importlib.import_module("bussola_agent.agent")

    return importar


def test_root_agent_padrao(importar_de_novo: Callable[[], ModuleType]) -> None:
    modulo = importar_de_novo()
    agente = modulo.root_agent
    assert isinstance(agente, Agent)
    assert agente.name == "bussola_hello"
    assert agente.model == "gemini-3.5-flash"
    [toolset] = agente.tools
    assert isinstance(toolset, McpToolset)
    assert toolset.connection_params.url == URL_PADRAO
    assert toolset.header_provider is None
    assert "{id_usuario?}" in agente.instruction
    assert "{ate_anomes?}" in agente.instruction


def test_callbacks_instalados(importar_de_novo: Callable[[], ModuleType]) -> None:
    modulo = importar_de_novo()
    agente = modulo.root_agent
    assert agente.before_model_callback is callbacks.before_model
    assert agente.after_model_callback is callbacks.after_model
    assert agente.before_tool_callback is callbacks.before_tool
    assert agente.after_tool_callback is callbacks.after_tool
    assert agente.before_agent_callback is modulo.inicializar_sessao


def test_carregar_extensoes_e_chamado(
    importar_de_novo: Callable[[], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[int] = []
    original = extensoes.carregar_extensoes

    def espiao() -> None:
        chamadas.append(1)
        original()

    monkeypatch.setattr(extensoes, "carregar_extensoes", espiao)
    importar_de_novo()
    assert chamadas == [1]


def test_extensoes_entram_no_root_agent(
    importar_de_novo: Callable[[], ModuleType], criar_extensao: Callable[[str, str], Path]
) -> None:
    """Ferramentas e trechos de instrução das extensões chegam ao agente."""
    criar_extensao(
        "governanca",
        "from bussola_agent import extensoes\n"
        "def solicitar_consentimento(acao: str) -> dict:\n"
        "    return {}\n"
        "extensoes.registrar_ferramenta(solicitar_consentimento)\n"
        "extensoes.registrar_instrucao(50, 'Peça consentimento antes de agir.')\n",
    )
    agente = importar_de_novo().root_agent
    assert isinstance(agente.tools[0], McpToolset)
    assert [f.__name__ for f in agente.tools[1:]] == ["solicitar_consentimento"]
    assert agente.instruction.rstrip().endswith("Peça consentimento antes de agir.")


def test_modelo_e_url_do_ambiente(
    importar_de_novo: Callable[[], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BUSSOLA_MODEL", "gemini-modelo-teste")
    monkeypatch.setenv("MCP_URL", "http://127.0.0.1:9999/mcp")
    agente = importar_de_novo().root_agent
    assert agente.model == "gemini-modelo-teste"
    assert agente.tools[0].connection_params.url == "http://127.0.0.1:9999/mcp"


def test_agent_loader_do_adk(
    importar_de_novo: Callable[[], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mesmo caminho do ``adk web``: ``AgentLoader(agent/).load_agent('bussola_agent')``."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    importar_de_novo()
    agente = AgentLoader(str(DIR_AGENTES)).load_agent("bussola_agent")
    assert isinstance(agente, Agent)
    assert agente.name == "bussola_hello"
    assert agente is sys.modules["bussola_agent.agent"].root_agent


# ---------------------------------------------------------------------------
# inicializar_sessao (before_agent_callback)
# ---------------------------------------------------------------------------


def _contexto(state: object) -> SimpleNamespace:
    return SimpleNamespace(state=state, session=SimpleNamespace(id="sessao-teste"))


@pytest.fixture
def modulo_agente(importar_de_novo: Callable[[], ModuleType]) -> ModuleType:
    return importar_de_novo()


async def test_inicializa_state_vazio_com_padroes(modulo_agente: ModuleType) -> None:
    state: dict = {}
    assert await modulo_agente.inicializar_sessao(callback_context=_contexto(state)) is None
    assert set(state) == set(CHAVES)
    assert state["id_usuario"] == ANCORA
    assert state["ate_anomes"] == 202506
    assert state["estado_jornada"] == "OBJETIVO"


async def test_inicializa_com_valores_do_ambiente(
    modulo_agente: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANCHOR_USER_ID", CONTROLE.upper())
    monkeypatch.setenv("REPLAY_START_ANOMES", "202512")
    state: dict = {}
    await modulo_agente.inicializar_sessao(callback_context=_contexto(state))
    assert state["id_usuario"] == CONTROLE
    assert state["ate_anomes"] == 202512


async def test_nao_sobrescreve_chaves_existentes(modulo_agente: ModuleType) -> None:
    state = {"id_usuario": CONTROLE, "ate_anomes": 202509, "estado_jornada": "AGIR"}
    await modulo_agente.inicializar_sessao(callback_context=_contexto(state))
    assert state["id_usuario"] == CONTROLE
    assert state["ate_anomes"] == 202509
    assert state["estado_jornada"] == "AGIR"
    assert set(state) == set(CHAVES)


async def test_escopo_nulo_e_preenchido(modulo_agente: ModuleType) -> None:
    state = {"id_usuario": None, "ate_anomes": None, "objetivo": None}
    await modulo_agente.inicializar_sessao(callback_context=_contexto(state))
    assert state["id_usuario"] == ANCORA
    assert state["ate_anomes"] == 202506


async def test_state_do_adk_registra_delta(modulo_agente: ModuleType) -> None:
    delta: dict = {}
    state = State(value={}, delta=delta)
    await modulo_agente.inicializar_sessao(callback_context=_contexto(state))
    assert set(delta) == set(CHAVES)
    assert delta["id_usuario"] == ANCORA


@pytest.mark.parametrize(
    ("variavel", "valor"),
    [
        ("ANCHOR_USER_ID", "nao-e-uuid-secreto"),
        ("REPLAY_START_ANOMES", "nao-e-numero-secreto"),
        ("REPLAY_START_ANOMES", "202601"),
    ],
)
async def test_configuracao_invalida_nao_preenche_nem_ecoa(
    modulo_agente: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    variavel: str,
    valor: str,
) -> None:
    monkeypatch.setenv(variavel, valor)
    state: dict = {}
    capsys.readouterr()
    assert await modulo_agente.inicializar_sessao(callback_context=_contexto(state)) is None
    assert state == {}
    saida = capsys.readouterr().out
    assert "CONFIGURACAO_INVALIDA" in saida
    assert valor not in saida
