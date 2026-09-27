"""Number verification of the final answer (FR-014; AC-03; spec D-04)."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.events import Event
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bussola_agent.estado import estado_inicial
from bussola_agent.jornada.number_check import (
    check_numbers,
    evidence_from,
    extract_numbers,
    source_footer,
    unsupported_numbers,
)
from bussola_agent.jornada.tool_results import ToolOutcome

RAIZ = Path(__file__).resolve().parents[3]
FIXTURES = RAIZ / "contracts" / "fixtures" / "ferramentas"
ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}__ate_202506.json").read_text(encoding="utf-8"))


def _mcp(envelope: dict) -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps(envelope)}],
        "structuredContent": envelope,
        "isError": False,
    }


def _tool_event(name: str, response: dict, invocation: str = "i2") -> Event:
    part = types.Part(function_response=types.FunctionResponse(name=name, response=response))
    return Event(
        author="bussola", invocation_id=invocation, content=types.Content(role="user", parts=[part])
    )


def _user_event(text: str, invocation: str) -> Event:
    return Event(
        author="user",
        invocation_id=invocation,
        content=types.Content(role="user", parts=[types.Part(text=text)]),
    )


def _ctx(events: list[Event], state: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        state=state if state is not None else estado_inicial(ANCORA, 202506),
        session=SimpleNamespace(id="s1", events=events),
        invocation_id="i2",
        user_content=None,
    )


def _answer(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _logs(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "value", "decimals", "unit"),
    [
        ("R$ 1.250,00", 1250.0, 2, ""),
        ("R$ 1.901,47", 1901.47, 2, ""),
        ("40%", 40.0, 0, "%"),
        ("35,35 por cento", 35.35, 2, "%"),
        ("R$ 30 mil", 30.0, 0, "mil"),
        ("1,7 mil", 1.7, 1, "mil"),
        ("44 meses", 44.0, 0, ""),
        ("2 anos", 2.0, 0, "anos"),
        ("1250.5", 1250.5, 1, ""),
    ],
)
def test_extract_pt_br_numbers(text: str, value: float, decimals: int, unit: str) -> None:
    [claim] = extract_numbers(text)
    assert claim.readings[0] == (value, decimals)
    assert claim.unit == unit


def test_ambiguous_thousands_have_two_readings() -> None:
    [claim] = extract_numbers("R$ 1.250")
    assert claim.readings == ((1250.0, 0), (1.25, 3))


def test_links_ordinals_and_codes_are_ignored() -> None:
    text = "Resolução nº 8, 1º passo, F4, https://www.itau.com.br/x/2025/cdb"
    assert [c.token for c in extract_numbers(text)] == ["8"]


def test_small_bare_integers_are_exempt() -> None:
    claims = extract_numbers("3 caminhos, 2 anos, 11 meses, 5%")
    assert [c.exempt for c in claims] == [True, False, False, False]


def test_golden_answer_is_fully_supported() -> None:
    evidence = evidence_from(
        _fixture("perfil_financeiro"),
        _fixture("capacidade_poupanca"),
        _fixture("comparar_cenarios"),
    )
    text = (
        "**Diagnóstico**\nSua renda média é de R$ 6.691,39 e o gasto médio, R$ 4.789,93; "
        "sobram R$ 1.901,47 por mês (mediana R$ 1.729,00). Em 1 dos 6 meses o saldo ficou "
        "negativo. O saldo atual é R$ 17.652,15.\n"
        "**Simulação**\nConservador: R$ 691,60 por mês em 44 meses (40% da sobra). "
        "Equilibrado: R$ 1.037,40 em 29 meses. Acelerado: R$ 1.660,85 em 19 meses, "
        "cerca de 80% da sobra (R$ 1,7 mil).\n"
        "Fonte: perfil financeiro e comparação de cenários, jan–jun/2025."
    )
    assert unsupported_numbers(text, evidence) == []


@pytest.mark.parametrize(
    "text",
    [
        "Você consegue guardar R$ 2.000,00 por mês.",
        "O caminho acelerado leva 15 meses.",
        "Isso compromete 55% da sua sobra.",
        "Sua renda é de 12 mil.",
    ],
)
def test_invented_numbers_are_flagged(text: str) -> None:
    evidence = evidence_from(_fixture("perfil_financeiro"), _fixture("comparar_cenarios"))
    assert len(unsupported_numbers(text, evidence)) == 1


def test_rounding_or_truncation_in_the_last_digit() -> None:
    evidence = evidence_from({"x": 1729.0, "y": 691.6})
    assert unsupported_numbers("R$ 692, R$ 691 e R$ 1.729", evidence) == []
    assert len(unsupported_numbers("R$ 1.730", evidence)) == 1
    assert len(unsupported_numbers("R$ 690", evidence)) == 1


def test_client_numbers_and_derived_forms_count() -> None:
    evidence = evidence_from(["Quero juntar R$ 30 mil em 2 anos"], 202506)
    assert unsupported_numbers("Meta de R$ 30.000,00 em 24 meses, dados de 2025.", evidence) == []


def test_source_footer_from_the_turn_tools() -> None:
    outcomes = [
        ToolOutcome("perfil_financeiro", _mcp(_fixture("perfil_financeiro")), "i2"),
        ToolOutcome("capacidade_poupanca", _mcp(_fixture("capacidade_poupanca")), "i2"),
        ToolOutcome("registrar_objetivo", {"dados": {}, "fonte": {}}, "i2"),
        ToolOutcome("resumo_mes", {"erro": {"codigo": "X", "mensagem": "x"}}, "i2"),
    ]
    assert source_footer(outcomes) == (
        "Fonte: perfil financeiro e capacidade de poupança, jan–jun/2025."
    )
    assert source_footer(outcomes[2:]) is None


# ---------------------------------------------------------------------------
# after_model callback
# ---------------------------------------------------------------------------


def _session_with_profile() -> list[Event]:
    return [
        _user_event("Como está meu perfil?", "i1"),
        _tool_event("perfil_financeiro", _mcp(_fixture("perfil_financeiro")), "i1"),
        _user_event("E agora?", "i2"),
    ]


def test_numbers_from_an_earlier_turn_are_not_evidence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    response = _answer("Sua renda média é R$ 6.691,39. Fonte: perfil financeiro.")
    capsys.readouterr()
    assert (
        check_numbers(callback_context=_ctx(_session_with_profile()), llm_response=response) is None
    )
    [log] = _logs(capsys)
    assert log["evento"] == "numero_sem_fonte"
    assert log["erro_codigo"] == "NUMERO_DIVERGENTE"
    assert log["severity"] == "WARNING"
    assert "6.691" not in json.dumps(log) and "6691" not in json.dumps(log)


def test_supported_answer_without_source_gets_the_footer(
    capsys: pytest.CaptureFixture[str],
) -> None:
    events = [
        _user_event("Como está meu perfil?", "i2"),
        _tool_event("perfil_financeiro", _mcp(_fixture("perfil_financeiro"))),
    ]
    response = _answer("Sua renda média é R$ 6.691,39.")
    capsys.readouterr()
    check_numbers(callback_context=_ctx(events), llm_response=response)
    assert response.content.parts[-1].text == (
        "Sua renda média é R$ 6.691,39.\n\nFonte: perfil financeiro, jan–jun/2025."
    )
    [log] = _logs(capsys)
    assert log["erro_codigo"] == "FONTE_NAO_CITADA"


def test_cited_and_supported_answer_is_silent(capsys: pytest.CaptureFixture[str]) -> None:
    events = [_tool_event("perfil_financeiro", _mcp(_fixture("perfil_financeiro")))]
    text = "Sua renda média é R$ 6.691,39 (fonte: perfil financeiro, jan–jun/2025)."
    response = _answer(text)
    capsys.readouterr()
    check_numbers(callback_context=_ctx(events), llm_response=response)
    assert response.content.parts[0].text == text
    assert _logs(capsys) == []


def test_client_numbers_echoed_without_tools_are_fine(capsys: pytest.CaptureFixture[str]) -> None:
    events = [_user_event("Quero 60 mil em 2 anos", "i2")]
    state = {**estado_inicial(ANCORA, 202506), "objetivo": {"valor_alvo": 60000.0}}
    response = _answer("Anotei: R$ 60.000,00 em 24 meses.")
    capsys.readouterr()
    check_numbers(callback_context=_ctx(events, state), llm_response=response)
    assert response.content.parts[0].text == "Anotei: R$ 60.000,00 em 24 meses."
    assert _logs(capsys) == []


@pytest.mark.parametrize(
    "response",
    [
        LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="R$ 9.999,00")]),
            partial=True,
        ),
        LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part(text="Vou consultar R$ 9.999,00"),
                    types.Part(function_call=types.FunctionCall(name="perfil_financeiro")),
                ],
            )
        ),
        LlmResponse(error_code="503", error_message="alta demanda"),
    ],
)
def test_only_final_text_is_checked(
    response: LlmResponse, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    assert check_numbers(callback_context=_ctx([]), llm_response=response) is None
    assert _logs(capsys) == []
