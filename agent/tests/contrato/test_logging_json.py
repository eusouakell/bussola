"""Logger JSON do agente (contratos §9; FR-011)."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from bussola_agent import logging_json
from bussola_agent.logging_json import (
    CAMPOS_PERMITIDOS,
    JsonFormatter,
    configurar_logging,
    obter_logger,
)


@pytest.fixture
def saida() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    configurar_logging(nivel="DEBUG", stream=buffer)
    yield buffer
    configurar_logging()


def _linhas(buffer: io.StringIO) -> list[dict]:
    return [json.loads(linha) for linha in buffer.getvalue().splitlines() if linha.strip()]


def test_linha_json_com_campos_base(saida: io.StringIO) -> None:
    obter_logger("teste").info("Olá %s", "mundo")
    (linha,) = _linhas(saida)
    assert linha["severity"] == "INFO"
    assert linha["message"] == "Olá mundo"
    assert linha["servico"] == "bussola-agent"
    assert linha["timestamp"].endswith("Z")


def test_so_campos_permitidos(saida: io.StringIO) -> None:
    extras = {campo: f"v_{campo}" for campo in CAMPOS_PERMITIDOS}
    extras.update({"prompt": "texto do usuário", "token": "abc", "lancamentos": ["x"]})
    obter_logger("teste").info("evento", extra=extras)
    (linha,) = _linhas(saida)
    permitidos = {"severity", "message", "servico", "timestamp", *CAMPOS_PERMITIDOS}
    assert set(linha) <= permitidos | {"excecao"}
    for campo in CAMPOS_PERMITIDOS:
        assert linha[campo] == f"v_{campo}"
    assert "prompt" not in linha and "token" not in linha and "lancamentos" not in linha


def test_campos_do_contrato() -> None:
    assert set(CAMPOS_PERMITIDOS) == {
        "session_id",
        "estado_jornada",
        "ferramenta",
        "evento",
        "consentimento",
        "ate_anomes",
        "latencia_ms",
        "erro_codigo",
        "id_usuario",
    }


def test_excecao_so_com_nome_da_classe(saida: io.StringIO) -> None:
    try:
        raise ValueError("segredo-no-texto-da-excecao")
    except ValueError:
        obter_logger("teste").exception("Falhou.")
    texto = saida.getvalue()
    (linha,) = _linhas(saida)
    assert linha["excecao"] == "ValueError"
    assert linha["severity"] == "ERROR"
    assert "segredo-no-texto-da-excecao" not in texto
    assert "Traceback" not in texto


def test_tipos_preservados_e_valores_nao_serializaveis(saida: io.StringIO) -> None:
    obter_logger("teste").info(
        "tipos", extra={"latencia_ms": 12, "ate_anomes": 202506, "consentimento": object()}
    )
    (linha,) = _linhas(saida)
    assert linha["latencia_ms"] == 12
    assert linha["ate_anomes"] == 202506
    assert isinstance(linha["consentimento"], str)


def test_configurar_e_idempotente(saida: io.StringIO) -> None:
    configurar_logging(nivel="DEBUG", stream=saida)
    configurar_logging(nivel="DEBUG", stream=saida)
    obter_logger("teste").info("uma vez")
    assert len(_linhas(saida)) == 1
    assert logging.getLogger(logging_json.LOGGER_RAIZ).propagate is False


def test_nivel_por_variavel_de_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.StringIO()
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    try:
        configurar_logging(stream=buffer)
        log = obter_logger("teste")
        log.info("some")
        log.warning("fica")
        assert [linha["message"] for linha in _linhas(buffer)] == ["fica"]
    finally:
        monkeypatch.delenv("LOG_LEVEL")
        configurar_logging()


def test_obter_logger_fica_no_namespace() -> None:
    assert obter_logger("x").name == "bussola_agent.x"
    assert obter_logger("bussola_agent.y").name == "bussola_agent.y"
    assert obter_logger().name == "bussola_agent"


def test_saida_padrao_e_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configurar_logging()
    obter_logger("teste").warning("para stdout")
    capturado = capsys.readouterr().out.strip().splitlines()
    assert json.loads(capturado[-1])["message"] == "para stdout"


def test_formatter_isolado() -> None:
    registro = logging.LogRecord("bussola_agent.t", logging.INFO, __file__, 1, "m", None, None)
    registro.ferramenta = "perfil_financeiro"
    registro.segredo = "nao"
    linha = json.loads(JsonFormatter(servico="outro").format(registro))
    assert linha["servico"] == "outro"
    assert linha["ferramenta"] == "perfil_financeiro"
    assert "segredo" not in linha
