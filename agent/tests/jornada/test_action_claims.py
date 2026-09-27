"""Ação afirmada em texto sem nenhuma ferramenta no turno (BUG-04, camada b)."""

import logging
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.events import Event
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bussola_agent.jornada import number_check
from bussola_agent.jornada.action_claims import (
    METADATA_KEY,
    ORDER,
    check_action_claims,
    claimed_tool,
)

# Texto do relato do BUG-04 (João Paulo), como o modelo escreveu na demo.
BUG_TEXT = (
    "Seu objetivo foi registrado com sucesso: Objetivo: comprar um apartamento. "
    "Valor alvo: R$ 500.000,00. Prazo: 24 meses."
)


def _answer(value: str, **extra: Any) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=value)]), **extra)


def _tool_event(name: str, invocation: str = "inv-1") -> Event:
    part = types.Part(
        function_response=types.FunctionResponse(name=name, response={"dados": {}, "fonte": {}})
    )
    return Event(
        author="bussola",
        invocation_id=invocation,
        content=types.Content(role="user", parts=[part]),
    )


def _ctx(*events: Event, invocation_id: str = "inv-1") -> SimpleNamespace:
    return SimpleNamespace(
        state={"estado_jornada": "OBJETIVO"},
        invocation_id=invocation_id,
        session=SimpleNamespace(id="sess-1", events=list(events)),
    )


def test_order_is_between_the_number_check_and_the_annotations() -> None:
    from bussola_agent.jornada import annotations

    assert number_check.ORDER < ORDER < annotations.ORDER


@pytest.mark.parametrize(
    ("answer", "tool"),
    [
        (BUG_TEXT, "registrar_objetivo"),
        ("Registrei o seu objetivo de comprar um apartamento.", "registrar_objetivo"),
        ("Sua meta foi salva.", "registrar_objetivo"),
        ("Pronto, criei o seu plano.", "criar_plano"),
        ("Seu plano foi criado e você já pode acompanhar mês a mês.", "criar_plano"),
        ("Seu plano está ativo.", "criar_plano"),
        ("Ajustei o seu plano para o novo aporte.", "ajustar_plano"),
        ("Os lembretes foram ativados.", "ativar_lembretes"),
        ("O caminho equilibrado foi registrado.", "escolher_cenario"),
        ("Comparei os três caminhos para você.", "comparar_cenarios"),
        ("Simulei o seu objetivo com esse aporte.", "simular_objetivo"),
        ("A simulação está pronta.", "simular_objetivo"),
    ],
)
def test_claims_are_recognized(answer: str, tool: str) -> None:
    assert claimed_tool(answer) == tool


@pytest.mark.parametrize(
    "answer",
    [
        "Para registrar o seu objetivo, me diga em quantos meses você quer chegar lá.",
        "Posso registrar o seu objetivo agora?",
        "Vou registrar o seu objetivo assim que você me disser o prazo.",
        "Ainda não registrei nada: preciso do prazo.",
        "Não consegui registrar o seu objetivo agora.",
        "Criar o plano ainda não está disponível nesta versão.",
        "Quer que eu crie o seu plano com o caminho equilibrado?",
        "Você gastou R$ 1.230,00 com mercado em junho.",
        "Qual desses caminhos você prefere: conservador, equilibrado ou acelerado?",
    ],
)
def test_offers_and_questions_are_not_claims(answer: str) -> None:
    assert claimed_tool(answer) is None


def test_flags_the_claim_and_logs_without_the_text(caplog: pytest.LogCaptureFixture) -> None:
    response = _answer(BUG_TEXT)
    with caplog.at_level(logging.WARNING, logger="bussola_agent.jornada.action_claims"):
        assert check_action_claims(_ctx(), response) is None
    assert response.custom_metadata == {"bussola": {METADATA_KEY: "registrar_objetivo"}}
    record = caplog.records[-1]
    assert record.evento == "acao_sem_ferramenta"
    assert record.erro_codigo == "ACAO_SEM_FERRAMENTA"
    assert record.ferramenta == "registrar_objetivo"
    assert record.estado_jornada == "OBJETIVO"
    assert record.session_id == "sess-1"
    assert "apartamento" not in record.getMessage()
    assert "500" not in record.getMessage()


def test_a_tool_answer_in_the_turn_clears_the_claim() -> None:
    response = _answer(BUG_TEXT)
    assert check_action_claims(_ctx(_tool_event("registrar_objetivo")), response) is None
    assert response.custom_metadata is None


def test_a_tool_answer_of_another_invocation_does_not_count() -> None:
    response = _answer(BUG_TEXT)
    check_action_claims(_ctx(_tool_event("registrar_objetivo", invocation="inv-0")), response)
    assert response.custom_metadata == {"bussola": {METADATA_KEY: "registrar_objetivo"}}


def test_partials_function_calls_and_errors_are_ignored() -> None:
    partial = _answer(BUG_TEXT, partial=True)
    check_action_claims(_ctx(), partial)
    assert partial.custom_metadata is None

    with_call = LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(text=BUG_TEXT),
                types.Part(function_call=types.FunctionCall(name="registrar_objetivo", args={})),
            ],
        )
    )
    check_action_claims(_ctx(), with_call)
    assert with_call.custom_metadata is None

    failed = LlmResponse(error_code="SAFETY", error_message="bloqueado")
    assert check_action_claims(_ctx(), failed) is None


def test_keeps_metadata_written_by_another_callback() -> None:
    response = _answer(BUG_TEXT)
    response.custom_metadata = {"bussola": {"tag": "acao", METADATA_KEY: "criar_plano"}}
    check_action_claims(_ctx(), response)
    assert response.custom_metadata["bussola"] == {"tag": "acao", METADATA_KEY: "criar_plano"}
