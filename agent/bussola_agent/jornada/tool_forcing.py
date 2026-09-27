"""Forces the tool call the customer already authorized (BUG-04, layer a).

``before_model`` order 30, right after the consent reader (005, order 20).
When the customer answers "sim" to a consent request,
:func:`bussola_agent.governanca.consent.read_reply` appends
``INSTRUCTION_ACCEPTED`` ("Chame a ferramenta <acao> agora, uma única vez") to
the request. That is only text, and a model that ignores it answers "pronto,
criei o seu plano" without calling anything: no ``functionResponse`` reaches
the front, so no card is drawn.

This callback turns that instruction into a constraint of the request:
``tool_config`` with ``FunctionCallingConfig(mode=ANY,
allowed_function_names=[acao])``, so the only thing the model can produce in
that call is the authorized function call.

It is deliberately narrow:

- it only fires when the consent reader appended the instruction in **this**
  request (the next call of the same invocation, the one that writes the text
  after the tool answered, builds a fresh request without it);
- the action must be a tool declared in the request (``tools_dict``), so an
  unknown name never reaches the API;
- an existing ``tool_config`` (set by the agent or another callback) is kept.

In every other state the model stays free to answer text and ask its
clarifying questions. The request is changed in place and the callback returns
``None``, so the chain goes on.
"""

from typing import Any

from google.genai import types

from bussola_agent.logging_json import obter_logger

ORDER = 30
EVENT_FORCED_TOOL = "ferramenta_obrigatoria"

_log = obter_logger(__name__)


def _accepted_template() -> str | None:
    """``INSTRUCTION_ACCEPTED`` of cycle 005, or ``None`` without the extension.

    Imported lazily: the journey (004) must keep working when the governance
    package is absent (``extensoes.PACOTES_EXTENSAO``).
    """
    try:
        from bussola_agent.governanca.consent import INSTRUCTION_ACCEPTED
    except ImportError:
        return None
    return INSTRUCTION_ACCEPTED


def _system_instruction(llm_request: Any) -> str:
    config = getattr(llm_request, "config", None)
    instruction = getattr(config, "system_instruction", None)
    return instruction if isinstance(instruction, str) else ""


def authorized_action(llm_request: Any) -> str | None:
    """Tool of the request the consent reader just told the model to call, or ``None``."""
    instruction = _system_instruction(llm_request)
    template = _accepted_template() if instruction else None
    if not template:
        return None
    for name in getattr(llm_request, "tools_dict", None) or {}:
        if template.format(acao=name) in instruction:
            return name
    return None


def force_authorized_action(callback_context: Any, llm_request: Any) -> None:
    """``before_model`` order 30: only the authorized tool may come out of this call."""
    config = getattr(llm_request, "config", None)
    if config is None or getattr(config, "tool_config", None) is not None:
        return None
    action = authorized_action(llm_request)
    if action is None:
        return None
    config.tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.ANY, allowed_function_names=[action]
        )
    )
    _log.info(
        "Chamada de ferramenta obrigatória no turno da autorização.",
        extra={
            "evento": EVENT_FORCED_TOOL,
            "ferramenta": action,
            "session_id": getattr(getattr(callback_context, "session", None), "id", None),
        },
    )
    return None
