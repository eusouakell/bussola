"""Scope and bookkeeping callbacks (FR-011–FR-013; AC-06)."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.sessions.state import State
from google.adk.tools.mcp_tool.mcp_session_manager import (
    MCPSessionManager,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_tool import McpTool
from mcp.types import Tool

from bussola_agent.escopo import (
    enforce_scope,
    initialize_session,
    is_mcp_tool,
    record_tool_result,
)
from bussola_agent.estado import CHAVES, estado_inicial

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"
CONTROLE = "31e94f2f-1463-49f9-a41a-b3f220ed976a"
FONTE = {
    "ferramenta": "perfil_financeiro",
    "tabelas": ["bussola_dados.perfil_mensal"],
    "periodo": {"inicio": 202501, "fim": 202506},
}


def _tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def _ctx(state: Any) -> SimpleNamespace:
    return SimpleNamespace(state=state, session=SimpleNamespace(id="s1", events=[]))


def _logs(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


def _mcp_result(envelope: dict, *, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(envelope)}],
        "structuredContent": envelope,
        "isError": is_error,
    }


# ---------------------------------------------------------------------------
# initialize_session (before_agent)
# ---------------------------------------------------------------------------


async def test_initialize_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANCHOR_USER_ID", raising=False)
    monkeypatch.delenv("REPLAY_START_ANOMES", raising=False)
    state: dict = {}
    assert await initialize_session(callback_context=_ctx(state)) is None
    assert set(state) == set(CHAVES)
    assert state["id_usuario"] == ANCORA
    assert state["ate_anomes"] == 202506
    assert state["estado_jornada"] == "OBJETIVO"


async def test_initialize_keeps_existing_journey(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANCHOR_USER_ID", ANCORA)
    state = {"id_usuario": ANCORA, "ate_anomes": 202509, "estado_jornada": "ORIENTAR"}
    await initialize_session(callback_context=_ctx(state))
    assert state["estado_jornada"] == "ORIENTAR"
    assert state["ate_anomes"] == 202509


# ---------------------------------------------------------------------------
# enforce_scope (before_tool 10)
# ---------------------------------------------------------------------------


def test_control_id_leaves_as_anchor_id(capsys: pytest.CaptureFixture[str]) -> None:
    """AC-06: o modelo pede o controle; a chamada sai com o âncora do state."""
    state = estado_inicial(ANCORA, 202506)
    args = {"id_usuario": CONTROLE, "ate_anomes": 202512, "valor_alvo": 30000}
    capsys.readouterr()
    assert (
        enforce_scope(tool=_tool("perfil_financeiro"), args=args, tool_context=_ctx(state)) is None
    )
    assert args == {"id_usuario": ANCORA, "ate_anomes": 202506, "valor_alvo": 30000}
    logs = _logs(capsys)
    codes = {log["erro_codigo"] for log in logs}
    assert codes == {"ID_USUARIO_DIVERGENTE", "ATE_ANOMES_DIVERGENTE"}
    assert all(log["evento"] == "escopo_sobrescrito" for log in logs)
    assert CONTROLE not in json.dumps(logs)
    assert [log["severity"] for log in logs if log["erro_codigo"] == "ID_USUARIO_DIVERGENTE"] == [
        "WARNING"
    ]


def test_missing_scope_is_filled_silently(capsys: pytest.CaptureFixture[str]) -> None:
    state = estado_inicial(ANCORA, 202506)
    args: dict = {}
    capsys.readouterr()
    enforce_scope(tool=_tool("capacidade_poupanca"), args=args, tool_context=_ctx(state))
    assert args == {"id_usuario": ANCORA, "ate_anomes": 202506}
    assert _logs(capsys) == []


def test_same_scope_in_other_case_is_not_an_alert(capsys: pytest.CaptureFixture[str]) -> None:
    state = estado_inicial(ANCORA, 202506)
    args = {"id_usuario": ANCORA.upper(), "ate_anomes": "202506"}
    capsys.readouterr()
    enforce_scope(tool=_tool("resumo_mes"), args=args, tool_context=_ctx(state))
    assert args["id_usuario"] == ANCORA
    assert args["ate_anomes"] == 202506
    assert _logs(capsys) == []


def _com_objetivo(valor_alvo: Any) -> dict:
    state = estado_inicial(ANCORA, 202506)
    state["objetivo"] = {"tipo": "imovel", "descricao": "Entrada", "valor_alvo": valor_alvo}
    return state


@pytest.mark.parametrize("ferramenta", ["simular_objetivo", "comparar_cenarios", "planejar_marcos"])
def test_other_target_value_leaves_as_the_registered_goal(
    ferramenta: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """O modelo simula outro valor; a chamada sai com o objetivo registrado."""
    state = _com_objetivo(18000.0)
    args = {"valor_alvo": 30000.0, "prazo_meses": 24}
    capsys.readouterr()
    assert enforce_scope(tool=_tool(ferramenta), args=args, tool_context=_ctx(state)) is None
    assert args["valor_alvo"] == 18000.0
    assert args["prazo_meses"] == 24
    [log] = _logs(capsys)
    assert log["evento"] == "escopo_sobrescrito"
    assert log["erro_codigo"] == "VALOR_ALVO_DIVERGENTE"
    assert "30000" not in json.dumps(log) and "18000" not in json.dumps(log)


def test_missing_target_value_is_filled_silently(capsys: pytest.CaptureFixture[str]) -> None:
    state = _com_objetivo(18000.0)
    args: dict = {"prazo_meses": 24}
    capsys.readouterr()
    enforce_scope(tool=_tool("simular_objetivo"), args=args, tool_context=_ctx(state))
    assert args["valor_alvo"] == 18000.0
    assert _logs(capsys) == []


def test_same_target_value_as_text_is_not_an_alert(capsys: pytest.CaptureFixture[str]) -> None:
    state = _com_objetivo(18000)
    args = {"valor_alvo": "18000.00", "prazo_meses": 24}
    capsys.readouterr()
    enforce_scope(tool=_tool("comparar_cenarios"), args=args, tool_context=_ctx(state))
    assert args["valor_alvo"] == 18000.0
    assert _logs(capsys) == []


@pytest.mark.parametrize("objetivo", [None, 0, -1, True, "muito"])
def test_goal_without_a_valid_amount_keeps_what_the_model_sent(objetivo: Any) -> None:
    """Antes de ``registrar_objetivo`` fechar o valor, o argumento do modelo vale."""
    state = _com_objetivo(objetivo)
    args = {"valor_alvo": 30000.0, "prazo_meses": 24}
    enforce_scope(tool=_tool("simular_objetivo"), args=args, tool_context=_ctx(state))
    assert args["valor_alvo"] == 30000.0


def test_local_tools_are_not_touched() -> None:
    args = {"id_usuario": CONTROLE, "nome": "acelerado"}
    state = estado_inicial(ANCORA, 202506)
    assert (
        enforce_scope(tool=_tool("escolher_cenario"), args=args, tool_context=_ctx(state)) is None
    )
    assert args == {"id_usuario": CONTROLE, "nome": "acelerado"}


def test_invalid_state_scope_skips_the_tool(capsys: pytest.CaptureFixture[str]) -> None:
    args = {"id_usuario": CONTROLE, "ate_anomes": 202506}
    capsys.readouterr()
    result = enforce_scope(tool=_tool("perfil_financeiro"), args=args, tool_context=_ctx({}))
    assert result == {
        "erro": {
            "codigo": "ENTRADA_INVALIDA",
            "mensagem": "Entrada inválida: id_usuario, ate_anomes.",
        }
    }
    assert args["id_usuario"] == CONTROLE  # nada do modelo é usado
    [log] = _logs(capsys)
    assert log["evento"] == "escopo_invalido"
    assert CONTROLE not in json.dumps(log)


def test_real_mcp_tool_is_recognized_even_with_a_new_name() -> None:
    manager = MCPSessionManager(StreamableHTTPConnectionParams(url="http://127.0.0.1:1/mcp"))
    tool = McpTool(
        mcp_tool=Tool(name="ferramenta_nova_do_003", inputSchema={"type": "object"}),
        mcp_session_manager=manager,
    )
    assert is_mcp_tool(tool)
    assert is_mcp_tool(_tool("comparar_cenarios"))
    assert not is_mcp_tool(_tool("registrar_objetivo"))


# ---------------------------------------------------------------------------
# record_tool_result (after_tool 10)
# ---------------------------------------------------------------------------


def test_mcp_source_goes_to_latest_sources() -> None:
    state = estado_inicial(ANCORA, 202506)
    response = _mcp_result({"dados": {"x": 1}, "fonte": FONTE, "avisos": []})
    assert (
        record_tool_result(
            tool=_tool("perfil_financeiro"),
            args={},
            tool_context=_ctx(state),
            tool_response=response,
        )
        is None
    )
    assert state["ultimas_fontes"] == [FONTE]


@pytest.mark.parametrize(
    "response",
    [
        _mcp_result({"erro": {"codigo": "DADOS_INSUFICIENTES", "mensagem": "x"}}),
        _mcp_result({"dados": {}, "fonte": FONTE}, is_error=True),
        {"erro": {"codigo": "ENTRADA_INVALIDA", "mensagem": "x"}},
    ],
)
def test_failures_record_no_source(response: dict) -> None:
    state = estado_inicial(ANCORA, 202506)
    record_tool_result(
        tool=_tool("perfil_financeiro"), args={}, tool_context=_ctx(state), tool_response=response
    )
    assert state["ultimas_fontes"] == []


def test_local_tool_source_is_not_recorded() -> None:
    state = estado_inicial(ANCORA, 202506)
    response = {
        "dados": {"objetivo": {"valor_alvo": 60000.0, "prazo_meses": 24}, "faltando": []},
        "fonte": {"ferramenta": "registrar_objetivo", "tabelas": []},
    }
    record_tool_result(
        tool=_tool("registrar_objetivo"), args={}, tool_context=_ctx(state), tool_response=response
    )
    assert state["ultimas_fontes"] == []
    assert state["estado_jornada"] == "ENTENDER"


def test_journey_through_the_callbacks_with_adk_state() -> None:
    delta: dict = {}
    state = State(value=estado_inicial(ANCORA, 202506), delta=delta)
    ctx = _ctx(state)
    goal = {
        "dados": {"objetivo": {"valor_alvo": 60000.0, "prazo_meses": 24}, "faltando": []},
        "fonte": {"ferramenta": "registrar_objetivo", "tabelas": []},
    }
    record_tool_result(
        tool=_tool("registrar_objetivo"), args={}, tool_context=ctx, tool_response=goal
    )
    for name in ("perfil_financeiro", "capacidade_poupanca"):
        response = _mcp_result({"dados": {}, "fonte": {**FONTE, "ferramenta": name}})
        record_tool_result(tool=_tool(name), args={}, tool_context=ctx, tool_response=response)
    assert delta["estado_jornada"] == "ANTECIPAR"
    cenarios = {"cenarios": [{"nome": "acelerado", "viavel": True}], "regras": {}}
    response = _mcp_result(
        {"dados": cenarios, "fonte": {**FONTE, "ferramenta": "comparar_cenarios"}}
    )
    record_tool_result(
        tool=_tool("comparar_cenarios"), args={}, tool_context=ctx, tool_response=response
    )
    assert delta["estado_jornada"] == "ORIENTAR"
    assert delta["cenarios"] == cenarios
    assert [f["ferramenta"] for f in delta["ultimas_fontes"]] == [
        "perfil_financeiro",
        "capacidade_poupanca",
        "comparar_cenarios",
    ]
