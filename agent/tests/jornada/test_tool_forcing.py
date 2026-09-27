"""``tool_config`` obrigatório no turno da autorização (BUG-04, camada a).

Sem rede e sem modelo: o ``LlmRequest`` é montado à mão, como em
``test_guardrails``.
"""

from types import SimpleNamespace

from google.adk.models import LlmRequest
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

from bussola_agent.governanca.consent import INSTRUCTION_ACCEPTED
from bussola_agent.jornada.tool_forcing import (
    ORDER,
    authorized_action,
    force_authorized_action,
)

BASE = "Você é o Bússola."


def criar_plano(cenario: str) -> dict:
    """Ferramenta falsa, só para aparecer no ``tools_dict`` do pedido."""
    return {"dados": {"cenario": cenario}}


def ajustar_plano(aporte_mensal: float) -> dict:
    """Outra ferramenta falsa."""
    return {"dados": {"aporte_mensal": aporte_mensal}}


def _request(
    *instructions: str, tools: tuple[str, ...] = ("criar_plano", "ajustar_plano")
) -> LlmRequest:
    request = LlmRequest()
    request.append_instructions([BASE, *instructions])
    declared = {"criar_plano": criar_plano, "ajustar_plano": ajustar_plano}
    request.tools_dict = {name: FunctionTool(declared[name]) for name in tools}
    return request


def _ctx() -> SimpleNamespace:
    return SimpleNamespace(session=SimpleNamespace(id="sess-1"), invocation_id="inv-1")


def _config(request: LlmRequest) -> types.FunctionCallingConfig | None:
    tool_config = request.config.tool_config
    return tool_config.function_calling_config if tool_config else None


def test_order_runs_after_the_consent_reader() -> None:
    assert ORDER > 20


def test_forces_only_the_authorized_action() -> None:
    request = _request(INSTRUCTION_ACCEPTED.format(acao="criar_plano"))
    assert authorized_action(request) == "criar_plano"
    assert force_authorized_action(_ctx(), request) is None
    config = _config(request)
    assert config is not None
    assert config.mode is types.FunctionCallingConfigMode.ANY
    assert config.allowed_function_names == ["criar_plano"]


def test_no_tool_config_without_the_consent_instruction() -> None:
    """Sem o "sim" do cliente o modelo segue livre para perguntar."""
    for request in (
        _request(),
        _request("Há um pedido de autorização pendente para criar_plano."),
        LlmRequest(),
    ):
        assert authorized_action(request) is None
        assert force_authorized_action(_ctx(), request) is None
        assert request.config.tool_config is None


def test_an_action_outside_the_declared_tools_is_ignored() -> None:
    request = _request(INSTRUCTION_ACCEPTED.format(acao="criar_plano"), tools=("ajustar_plano",))
    assert authorized_action(request) is None
    force_authorized_action(_ctx(), request)
    assert request.config.tool_config is None


def test_an_existing_tool_config_is_kept() -> None:
    request = _request(INSTRUCTION_ACCEPTED.format(acao="criar_plano"))
    mine = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.NONE
        )
    )
    request.config.tool_config = mine
    force_authorized_action(_ctx(), request)
    assert request.config.tool_config is mine
