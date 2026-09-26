"""Logger JSON com lista de campos permitidos (contratos §9, FR-011, research R-14)."""

import io
import json
import logging
import re

import pytest

from bussola_mcp.logging_json import CAMPOS_EXTRAS_PERMITIDOS, JsonFormatter, configurar_logging

CAMPOS_BASE = {"severity", "message", "servico", "timestamp"}


@pytest.fixture
def saida(monkeypatch: pytest.MonkeyPatch):
    """Instala o logger JSON num buffer e restaura o logger raiz ao final."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    raiz = logging.getLogger()
    handlers, nivel = list(raiz.handlers), raiz.level
    buffer = io.StringIO()
    configurar_logging("bussola-mcp", fluxo=buffer)
    yield buffer
    for handler in list(raiz.handlers):
        if handler not in handlers:
            raiz.removeHandler(handler)
    raiz.setLevel(nivel)


def _linhas(buffer: io.StringIO) -> list[dict]:
    return [json.loads(linha) for linha in buffer.getvalue().splitlines() if linha.strip()]


def test_campos_base_e_extras_permitidos(saida):
    extras = {campo: f"valor-{campo}" for campo in CAMPOS_EXTRAS_PERMITIDOS}
    extras["latencia_ms"] = 12.5
    logging.getLogger("teste").info("ferramenta chamada", extra=extras)
    (linha,) = _linhas(saida)
    assert set(linha) == CAMPOS_BASE | set(CAMPOS_EXTRAS_PERMITIDOS)
    assert linha["severity"] == "INFO"
    assert linha["message"] == "ferramenta chamada"
    assert linha["servico"] == "bussola-mcp"
    assert linha["latencia_ms"] == 12.5
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", linha["timestamp"])


def test_extras_fora_da_lista_sao_descartados(saida):
    logging.getLogger("teste").warning(
        "evento",
        extra={"prompt": "texto do usuário", "token": "segredo-123", "ferramenta": "resumo_mes"},
    )
    (linha,) = _linhas(saida)
    assert set(linha) == CAMPOS_BASE | {"ferramenta"}
    assert linha["severity"] == "WARNING"
    assert "segredo-123" not in saida.getvalue()
    assert "texto do usuário" not in saida.getvalue()


def test_extra_nulo_e_omitido(saida):
    logging.getLogger("teste").info("ok", extra={"erro_codigo": None})
    (linha,) = _linhas(saida)
    assert "erro_codigo" not in linha


def test_excecao_so_com_o_nome_da_classe(saida):
    try:
        raise ValueError("dado sensível 4111")
    except ValueError:
        logging.getLogger("teste").exception("falhou")
    (linha,) = _linhas(saida)
    assert linha["excecao"] == "ValueError"
    assert linha["severity"] == "ERROR"
    texto = saida.getvalue()
    assert "4111" not in texto and "Traceback" not in texto


def test_uma_linha_por_evento_e_idempotente(saida):
    buffer = io.StringIO()
    configurar_logging("bussola-mcp", fluxo=buffer)  # substitui o handler anterior
    logging.getLogger("teste").info("um")
    logging.getLogger("teste").info("dois")
    assert [linha["message"] for linha in _linhas(buffer)] == ["um", "dois"]
    assert saida.getvalue() == ""


def test_log_level(saida, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "warning")
    buffer = io.StringIO()
    configurar_logging("bussola-mcp", fluxo=buffer)
    logging.getLogger("teste").info("some")
    logging.getLogger("teste").warning("fica")
    assert [linha["message"] for linha in _linhas(buffer)] == ["fica"]

    monkeypatch.setenv("LOG_LEVEL", "nivel-invalido")
    configurar_logging("bussola-mcp", fluxo=buffer)
    assert logging.getLogger().level == logging.INFO


def test_formatter_isolado():
    registro = logging.LogRecord("x", logging.DEBUG, __file__, 1, "msg %s", ("a",), None)
    registro.session_id = "s1"
    registro.outro = "descartado"
    linha = json.loads(JsonFormatter("svc").format(registro))
    assert linha["message"] == "msg a"
    assert linha["session_id"] == "s1"
    assert linha["severity"] == "DEBUG"
    assert "outro" not in linha
