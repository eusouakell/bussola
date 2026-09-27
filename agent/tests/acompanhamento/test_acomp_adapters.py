"""Adaptadores das portas: ``McpToolGateway`` sobre ``mcp_conexao`` e o registro (integração).

O transporte MCP (``mcp_conexao._chamar_mcp``) é trocado por
:func:`fake_transport`, que responde com as fixtures no formato do
``CallToolResult`` real. Nada sai da máquina.
"""

import pytest

from bussola_agent import mcp_conexao
from bussola_agent.acompanhamento import ports
from bussola_agent.acompanhamento.fakes import (
    ANCHOR_USER_ID,
    FixtureMcp,
    fake_transport,
    plan_state,
    tool_context,
)
from bussola_agent.acompanhamento.tools import avancar_mes
from bussola_agent.persistencia import RegistroEmMemoria


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FixtureMcp:
    fixture_mcp = FixtureMcp()
    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", fake_transport(fixture_mcp))
    return fixture_mcp


async def test_the_default_gateway_goes_through_mcp_conexao(transport: FixtureMcp) -> None:
    assert isinstance(ports.get_gateway(), ports.McpToolGateway)
    state = {"id_usuario": ANCHOR_USER_ID, "ate_anomes": 202507, "outra": 1}
    envelope = await ports.get_gateway().monthly_summary(202507, state)
    assert envelope["dados"]["sobra"] == 884.53
    assert transport.calls == [
        ("resumo_mes", {"anomes": 202507, "id_usuario": ANCHOR_USER_ID, "ate_anomes": 202507})
    ]


async def test_scope_is_forced_from_the_state_by_mcp_conexao(transport: FixtureMcp) -> None:
    state = {"id_usuario": ANCHOR_USER_ID, "ate_anomes": 202506}
    envelope = await ports.McpToolGateway().simulate_goal(1000.0, state, prazo_meses=10)
    assert "dados" in envelope
    (_, args), *_ = transport.calls
    assert (args["id_usuario"], args["ate_anomes"]) == (ANCHOR_USER_ID, 202506)
    assert "aporte_mensal" not in args


async def test_invalid_scope_never_reaches_the_transport(transport: FixtureMcp) -> None:
    envelope = await ports.McpToolGateway().monthly_summary(202507, {"id_usuario": "x"})
    assert envelope["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert transport.calls == []


async def test_advance_month_through_the_real_adapter(transport: FixtureMcp) -> None:
    registry = RegistroEmMemoria()
    ports.configure_registry(registry)
    ctx = tool_context(plan_state())

    result = await avancar_mes(ctx)

    assert result["dados"]["realizado"] == 884.53
    assert [r["id"] for r in result["dados"]["rotas"]] == ["A", "B"]
    assert {args["ate_anomes"] for _, args in transport.calls} == {202507}
    assert len(registry.eventos) == 3


def test_registry_port_rejects_objects_that_are_not_a_registry() -> None:
    with pytest.raises(TypeError):
        ports.configure_registry(object())  # type: ignore[arg-type]


def test_default_registry_is_one_in_memory_instance_until_reset() -> None:
    first = ports.get_registry()
    assert isinstance(first, RegistroEmMemoria)
    assert ports.get_registry() is first
    ports.reset()
    assert ports.get_registry() is not first
