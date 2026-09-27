"""Camada anticorrupção sobre os objetos do ADK (:mod:`bussola_agent.jornada.llm_view`).

Duas garantias: a leitura devolve o mesmo que os ``getattr`` espalhados devolviam
(comportamento preservado) e uma forma inesperada do SDK **aparece no log** em
vez de virar um no-op silencioso (R11 da varredura).
"""

import io
import json
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bussola_agent.jornada import llm_view
from bussola_agent.logging_json import CAMPOS_PERMITIDOS, configurar_logging


@pytest.fixture(autouse=True)
def sem_formas_reportadas() -> Iterator[None]:
    llm_view.reset_reported()
    yield
    llm_view.reset_reported()


@pytest.fixture
def json_logs() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    configurar_logging(nivel="DEBUG", stream=buffer)
    yield buffer
    configurar_logging()


def _lines(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


def _formas(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [line for line in _lines(buffer) if line.get("evento") == "forma_adk_inesperada"]


def _answer(*parts: types.Part, **extra: Any) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=list(parts)), **extra)


# --- leitura ----------------------------------------------------------------


def test_le_as_partes_de_texto_e_ignora_thought_e_vazio() -> None:
    response = _answer(
        types.Part(text="Olá"),
        types.Part(text="raciocínio", thought=True),
        types.Part(text=""),
        types.Part(text=", tudo bem?"),
    )
    assert len(llm_view.parts(response)) == 4
    assert [p.text for p in llm_view.text_parts(response)] == ["Olá", ", tudo bem?"]
    assert llm_view.final_text(response) == "Olá, tudo bem?"


def test_sem_conteudo_nao_ha_parte_nem_texto() -> None:
    assert llm_view.parts(None) == []
    assert llm_view.parts(LlmResponse()) == []
    assert llm_view.content_parts(None) == []
    assert llm_view.final_text(LlmResponse()) == ""


def test_has_function_call() -> None:
    call = types.Part(function_call=types.FunctionCall(name="registrar_objetivo", args={}))
    assert llm_view.has_function_call(_answer(types.Part(text="oi"), call)) is True
    assert llm_view.has_function_call(_answer(types.Part(text="oi"))) is False


@pytest.mark.parametrize(
    ("response", "esperado"),
    [
        (_answer(types.Part(text="pronto")), True),
        (_answer(types.Part(text="pensando", thought=True)), False),
        (_answer(types.Part(text="pronto"), partial=True), False),
        (LlmResponse(error_code="503", error_message="alta demanda"), False),
        (LlmResponse(), False),
        (
            _answer(
                types.Part(text="vou consultar"),
                types.Part(function_call=types.FunctionCall(name="perfil_financeiro")),
            ),
            False,
        ),
    ],
)
def test_is_final_text(response: LlmResponse, esperado: bool) -> None:
    assert llm_view.is_final_text(response) is esperado


def test_append_text_acrescenta_na_ultima_parte_de_texto() -> None:
    response = _answer(types.Part(text="primeira"), types.Part(text="segunda   \n"))
    assert llm_view.append_text(response, "Fonte: resumo_mes.") is True
    assert response.content.parts[0].text == "primeira"
    assert response.content.parts[1].text == "segunda\n\nFonte: resumo_mes."


def test_append_text_sem_parte_de_texto_nao_muda_nada() -> None:
    response = LlmResponse()
    assert llm_view.append_text(response, "Fonte: resumo_mes.") is False


# --- forma inesperada do ADK ------------------------------------------------


def test_uma_forma_inesperada_e_logada_uma_unica_vez(json_logs: io.StringIO) -> None:
    """Sem ``content``, a leitura ainda devolve ``[]`` — mas deixa rastro."""

    class RespostaDeOutroSdk:
        pass

    estranho = RespostaDeOutroSdk()
    assert llm_view.parts(estranho) == []
    assert llm_view.final_text(estranho) == ""
    assert llm_view.is_final_text(estranho) is False

    avisos = [line for line in _lines(json_logs) if line["severity"] == "ERROR"]
    formas = [line for line in avisos if line["evento"] == "forma_adk_inesperada"]
    # Um por atributo ausente (content, partial, error_code), e não um por leitura.
    assert len(formas) == 3
    assert {line["erro_codigo"] for line in formas} == {"FORMA_ADK_INESPERADA"}
    assert all("RespostaDeOutroSdk" in line["message"] for line in formas)

    llm_view.parts(estranho)
    assert len(_formas(json_logs)) == 3


def test_o_log_de_forma_inesperada_so_usa_campos_permitidos(json_logs: io.StringIO) -> None:
    llm_view.parts(SimpleNamespace())
    base = {"severity", "message", "servico", "timestamp"}
    linhas = _formas(json_logs)
    assert linhas
    assert all(set(line) <= base | set(CAMPOS_PERMITIDOS) for line in linhas)


def test_conteudo_sem_parts_cai_no_default_e_e_reportado(json_logs: io.StringIO) -> None:
    assert llm_view.content_parts(SimpleNamespace()) == []
    assert len(_formas(json_logs)) == 1


def test_none_nao_e_forma_inesperada(json_logs: io.StringIO) -> None:
    """``content=None`` e ``holder=None`` são casos normais, não drift do SDK."""
    assert llm_view.parts(None) == []
    assert llm_view.content_parts(None) == []
    assert llm_view.parts(LlmResponse()) == []
    assert _formas(json_logs) == []
