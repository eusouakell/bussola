"""Wiring through the extension points only (``agent.py`` is not edited)."""

import importlib
import sys
from collections.abc import Callable
from types import ModuleType

import pytest

import bussola_agent
from bussola_agent import callbacks, extensoes
from bussola_agent.governanca import (
    SENSITIVE_TOOLS,
    acoes,
    audit,
    consent,
    guardrails,
    instructions,
    register,
)
from bussola_agent.jornada import respostas_rapidas

ACTIONS = ["criar_plano", "ativar_lembretes", "simular_contratacao", "compartilhar_dados"]


def _names(tools: list) -> list[str]:
    return [getattr(t, "__name__", getattr(t, "name", "")) for t in tools]


def test_register_uses_the_documented_orders() -> None:
    assert callbacks.registrados("before_model") == [
        audit.record_session_start,
        guardrails.screen_input,
        consent.read_reply,
    ]
    assert callbacks.registrados("before_tool") == [consent.gate, audit.remember_tool_call]
    assert callbacks.registrados("after_tool") == [audit.record_tool_call]
    assert callbacks.registrados("after_model") == [guardrails.screen_output]
    assert _names(extensoes.ferramentas()) == ["solicitar_consentimento", *ACTIONS]
    assert extensoes.ferramentas_sensiveis() == set(ACTIONS)
    assert set(_names(SENSITIVE_TOOLS)) == set(ACTIONS)


def test_register_is_idempotent() -> None:
    register()
    register()
    assert len(extensoes.ferramentas()) == 5
    assert len(callbacks.registrados("before_model")) == 3


def test_instructions_in_the_005_range() -> None:
    text = extensoes.instrucoes()
    assert 50 <= instructions.ORDER_CONSENT < instructions.ORDER_ACTIONS < 70
    assert 50 <= instructions.ORDER_LIMITS < 70
    assert "solicitar_consentimento" in text
    assert "credito_imobiliario" in text  # simulable products listed for the model


def test_action_tools_do_not_take_scope_arguments() -> None:
    """id_usuario and ate_anomes come from the session, never from the model."""
    import inspect

    for tool in (acoes.criar_plano, acoes.ativar_lembretes, acoes.simular_contratacao):
        params = set(inspect.signature(tool).parameters)
        assert not params & {"id_usuario", "ate_anomes", "valor_alvo", "aporte_mensal"}


@pytest.fixture
def fresh_agent(monkeypatch: pytest.MonkeyPatch) -> Callable[[], ModuleType]:
    """Imports ``bussola_agent.agent`` and the real extension packages from scratch."""
    monkeypatch.setenv("ADK_DISABLE_LOAD_DOTENV", "TRUE")
    for key in ("BUSSOLA_MODEL", "MCP_URL", "ANCHOR_USER_ID", "REPLAY_START_ANOMES"):
        monkeypatch.delenv(key, raising=False)

    def load() -> ModuleType:
        callbacks.limpar()
        extensoes.limpar()
        for name in extensoes.PACOTES_EXTENSAO:
            monkeypatch.delitem(sys.modules, name, raising=False)
        monkeypatch.delitem(sys.modules, "bussola_agent.agent", raising=False)
        monkeypatch.delattr(bussola_agent, "agent", raising=False)
        return importlib.import_module("bussola_agent.agent")

    return load


def test_real_agent_loads_the_governance_package(fresh_agent: Callable[[], ModuleType]) -> None:
    """Integrated with the 004 journey (first) and the 006 follow-up (last)."""
    agent = fresh_agent().root_agent
    names = _names(agent.tools[1:])
    assert names == [
        "registrar_objetivo",
        "escolher_cenario",
        "solicitar_consentimento",
        *ACTIONS,
        "avancar_mes",
        "status_plano",
        "ajustar_plano",
    ]
    assert extensoes.ferramentas_sensiveis() == {*ACTIONS, "ajustar_plano"}
    assert "solicitar_consentimento" in agent.instruction
    after_model = callbacks.registrados("after_model")
    assert after_model[0].__name__ == "screen_output"
    assert after_model[-1] is respostas_rapidas.anexar
    assert [f.__name__ for f in callbacks.registrados("before_tool")] == [
        "enforce_scope",
        "gate",
        "remember_tool_call",
    ]
    assert [f.__name__ for f in callbacks.registrados("after_tool")] == [
        "record_tool_result",
        # Ordem 30 (009): grava `marcos` no state a partir de `planejar_marcos`.
        "gravar_marcos",
        "record_tool_call",
    ]
