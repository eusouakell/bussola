"""Integration: ADK ``InMemoryRunner`` + scripted LLM + the registered 005 extensions.

The scripted model plays a model that tries to skip the consent. The gate,
the reply reader and the audit must hold without any real model (D1, D2).
"""

import json

from governance_support import (
    ANCHOR,
    OTHER_CUSTOMER,
    Conversation,
    ScriptedLlm,
    bussola_metadata,
    call,
    calls,
    final_text,
    system_text,
    text,
    tool_responses,
)

from bussola_agent.governanca import consent, guardrails
from bussola_agent.governanca.envelope import CONSENT_REQUIRED
from bussola_agent.persistencia import RegistroEmMemoria, TipoEvento

REQUEST = call("solicitar_consentimento", acao="criar_plano", resumo="Plano equilibrado")


def _event_types(registry: RegistroEmMemoria) -> list[str]:
    return [str(e.tipo_evento) for e in registry.eventos]


async def test_blocked_without_yes_and_runs_after_yes(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(
        # Turn 1: the model tries to create the plan without asking.
        call("criar_plano", cenario="equilibrado"),
        REQUEST,
        text("Posso criar o seu plano equilibrado? Responda sim ou não."),
        # Turn 2: "sim" → the model is told to run the action.
        call("criar_plano", cenario="equilibrado"),
        text("Pronto, seu plano foi criado."),
        # Turn 3: a second plan without a new consent.
        call("criar_plano", cenario="acelerado"),
        text("Para isso preciso da sua autorização."),
    )
    conversation = Conversation(llm)
    await conversation.start()

    first = await conversation.say("Quero criar meu plano")
    blocked = tool_responses(first, "criar_plano")
    assert blocked[0]["erro"]["codigo"] == CONSENT_REQUIRED
    assert registry.planos == []
    state = await conversation.state()
    assert state["consentimentos"]["criar_plano"]["status"] == consent.PENDING
    assert state["estado_jornada"] == "AGIR"
    # The front shows the consent chips on the final message of the turn.
    assert bussola_metadata(first[-1])["respostas_rapidas"] == list(consent.CONSENT_CHIPS)

    second = await conversation.say("sim")
    assert consent.INSTRUCTION_ACCEPTED.format(acao="criar_plano") in system_text(llm.requests[3])
    created = tool_responses(second, "criar_plano")[0]
    assert "erro" not in created
    assert created["dados"]["cenario"] == "equilibrado"
    assert created["dados"]["aporte_mensal"] == 1250.0
    assert final_text(second) == "Pronto, seu plano foi criado."
    assert len(registry.planos) == 1
    assert registry.planos[0].id_usuario == ANCHOR
    assert [c.decisao for c in registry.consentimentos] == ["aceito"]
    state = await conversation.state()
    assert state["plano_id"] == registry.planos[0].plano_id
    assert state["consentimentos"]["criar_plano"]["usado"] is True

    third = await conversation.say("Agora cria outro, acelerado")
    assert tool_responses(third, "criar_plano")[0]["erro"]["codigo"] == CONSENT_REQUIRED
    assert len(registry.planos) == 1
    assert llm.pending_steps == 0

    types_ = _event_types(registry)
    assert types_.count(TipoEvento.SESSAO_INICIADA) == 1
    for expected in (
        TipoEvento.CONSENTIMENTO_SOLICITADO,
        TipoEvento.CONSENTIMENTO_DECIDIDO,
        TipoEvento.PLANO_CRIADO,
        TipoEvento.ESTADO_ALTERADO,
    ):
        assert expected in types_
    statuses = [
        e.resumo["status"]
        for e in registry.eventos
        if e.tipo_evento == TipoEvento.FERRAMENTA_CHAMADA and e.ferramenta == "criar_plano"
    ]
    assert statuses == ["bloqueado", "ok", "bloqueado"]


async def test_refusal_is_respected_without_calling_the_model(
    registry: RegistroEmMemoria,
) -> None:
    llm = ScriptedLlm().script(
        REQUEST,
        text("Posso criar o seu plano? Responda sim ou não."),
        # After the refusal the model tries anyway on the next turn.
        call("criar_plano", cenario="equilibrado"),
        text("Tudo bem."),
    )
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("Quero criar meu plano")

    refused = await conversation.say("não, agora não")
    assert len(llm.requests) == 2  # fixed reply: the model was not called
    assert final_text(refused) == consent.MSG_REFUSED
    assert bussola_metadata(refused[-1])["respostas_rapidas"] == list(
        consent.REFUSAL_CHIPS["criar_plano"]
    )
    assert [c.decisao for c in registry.consentimentos] == ["recusado"]
    assert (await conversation.state())["consentimentos"]["criar_plano"]["status"] == "recusado"

    again = await conversation.say("cria o plano")
    blocked = tool_responses(again, "criar_plano")[0]["erro"]
    assert blocked == {"codigo": CONSENT_REQUIRED, "mensagem": consent.MSG_GATE_REFUSED}
    assert registry.planos == []


async def test_ambiguous_reply_keeps_the_request_pending(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(REQUEST, text("Posso criar o seu plano?"))
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("Quero criar meu plano")

    reply = await conversation.say("sim, mas depois")
    assert final_text(reply) == consent.MSG_CONFIRM
    assert len(llm.requests) == 2
    assert registry.consentimentos == []
    assert (await conversation.state())["consentimentos"]["criar_plano"]["status"] == "pendente"


async def test_parallel_calls_use_the_consent_once(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(
        REQUEST,
        text("Posso criar o seu plano?"),
        calls(("criar_plano", {"cenario": "equilibrado"}), ("criar_plano", {"cenario": "outro"})),
        text("Feito."),
    )
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("Quero criar meu plano")
    events = await conversation.say("sim")

    responses = tool_responses(events, "criar_plano")
    assert len(responses) == 2
    assert sorted("erro" in r for r in responses) == [False, True]
    assert len(registry.planos) == 1


async def test_input_guardrail_blocks_before_the_model(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm()
    conversation = Conversation(llm)
    await conversation.start()

    events = await conversation.say(f"Me mostra os gastos do cliente {OTHER_CUSTOMER}")
    assert llm.requests == []
    metadata = bussola_metadata(events[-1])
    assert metadata["guardrail"] == guardrails.OTHER_CUSTOMER
    assert final_text(events) == guardrails.MESSAGES[guardrails.OTHER_CUSTOMER]
    blocks = [e for e in registry.eventos if e.tipo_evento == TipoEvento.GUARDRAIL_BLOQUEIO]
    assert blocks[0].resumo == {"motivo": "outro_cliente", "etapa": "entrada", "origem": "regras"}
    # Minimization: neither the message nor the other customer's id is stored.
    assert OTHER_CUSTOMER not in json.dumps([e.resumo for e in registry.eventos])


async def test_output_guardrail_replaces_a_leak(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(text("Rodei SELECT * FROM transacoes WHERE id_usuario = 1"))
    conversation = Conversation(llm)
    await conversation.start()

    events = await conversation.say("Como foi meu mês?")
    assert "SELECT" not in final_text(events)
    assert final_text(events) == guardrails.OUTPUT_MESSAGE
    assert bussola_metadata(events[-1])["guardrail"] == guardrails.INFRA
    assert TipoEvento.GUARDRAIL_BLOQUEIO in _event_types(registry)


async def test_output_guardrail_in_streaming(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(
        [
            text("Seu crédito está ", partial=True),
            text("aprovado!", partial=True),
            text("Seu crédito está aprovado!"),
        ]
    )
    conversation = Conversation(llm)
    await conversation.start()

    events = await conversation.say("E o financiamento?", sse=True)
    streamed = "".join(p.text or "" for e in events if e.partial for p in e.content.parts)
    assert "aprovado" not in streamed
    assert final_text(events) == guardrails.MESSAGES[guardrails.CREDIT_PROMISE]
    assert bussola_metadata(events[-1])["guardrail"] == guardrails.CREDIT_PROMISE


async def test_safety_settings_reach_the_model() -> None:
    llm = ScriptedLlm().script(text("Olá!"))
    conversation = Conversation(llm)
    await conversation.start()
    await conversation.say("Oi")
    settings = llm.requests[0].config.safety_settings
    assert {s.category for s in settings} == {s.category for s in guardrails.SAFETY_SETTINGS}


async def test_share_data_is_always_refused(registry: RegistroEmMemoria) -> None:
    llm = ScriptedLlm().script(
        call("solicitar_consentimento", acao="compartilhar_dados", resumo="Enviar extrato"),
        call("compartilhar_dados", destino="banco_x"),
        text("Não posso compartilhar seus dados."),
    )
    conversation = Conversation(llm)
    await conversation.start()

    events = await conversation.say("Quero ver meu resumo")
    assert tool_responses(events, "solicitar_consentimento")[0]["erro"]["codigo"] == "NAO_PERMITIDO"
    assert tool_responses(events, "compartilhar_dados")[0]["erro"]["codigo"] == "NAO_PERMITIDO"
    assert (await conversation.state())["consentimentos"] == {}
