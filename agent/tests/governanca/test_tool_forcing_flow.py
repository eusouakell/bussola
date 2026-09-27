"""Integração: o turno da autorização não consegue responder texto (BUG-04, camada a).

Mesmo cenário do ``test_flow``: ``InMemoryRunner`` + LLM roteirizado + as
extensões do 005 registradas. Aqui o callback ``before_model`` 30 do 004 entra
na cadeia e o teste confere o ``tool_config`` que chegou ao pedido real do ADK.
"""

from google.genai import types
from governance_support import Conversation, ScriptedLlm, call, final_text, text

from bussola_agent import callbacks
from bussola_agent.jornada import tool_forcing
from bussola_agent.persistencia import RegistroEmMemoria

REQUEST = call("solicitar_consentimento", acao="criar_plano", resumo="Plano equilibrado")


def _calling(request: object) -> types.FunctionCallingConfig | None:
    config = getattr(request, "config", None)
    tool_config = getattr(config, "tool_config", None)
    return tool_config.function_calling_config if tool_config else None


async def test_the_authorized_turn_can_only_call_the_tool(registry: RegistroEmMemoria) -> None:
    callbacks.registrar("before_model", tool_forcing.force_authorized_action, tool_forcing.ORDER)
    llm = ScriptedLlm().script(
        REQUEST,
        text("Posso criar o seu plano equilibrado? Responda sim ou não."),
        # Turno do "sim": o pedido chega com tool_config, então só a chamada sai.
        call("criar_plano", cenario="equilibrado"),
        text("Pronto, criei o seu plano."),
    )
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("Quero criar meu plano")

    authorized = await conversation.say("sim")
    forced = _calling(llm.requests[2])
    assert forced is not None
    assert forced.mode is types.FunctionCallingConfigMode.ANY
    assert forced.allowed_function_names == ["criar_plano"]
    # A chamada seguinte, que redige o texto, volta a ser livre.
    assert _calling(llm.requests[3]) is None
    assert final_text(authorized) == "Pronto, criei o seu plano."
    assert len(registry.planos) == 1


async def test_a_turn_without_authorization_stays_free(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(text("Quanto você quer guardar por mês?"))
    callbacks.registrar("before_model", tool_forcing.force_authorized_action, tool_forcing.ORDER)
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("quero juntar 30 mil")
    assert _calling(llm.requests[0]) is None
    assert registry.planos == []
