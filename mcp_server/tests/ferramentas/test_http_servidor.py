"""Servidor real em subprocess, via streamable HTTP em ``/mcp`` (ciclo §3.1, ``make mcp``).

Sobe ``python -m bussola_mcp.server`` em ``127.0.0.1`` numa porta livre e conversa
com ele pelo cliente do SDK oficial. Não sai do loopback.
"""

import json
import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from bussola_mcp.contratos import FERRAMENTAS, ID_ANCORA, arquivo_golden

DIR_MCP_SERVER = Path(__file__).resolve().parents[2]
HOST = "127.0.0.1"
ESPERA_SUBIDA_S = 30.0
ESPERA_DESCIDA_S = 10.0


def _porta_livre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _esperar_porta(processo: subprocess.Popen, porta: int, log: Path) -> None:
    limite = time.monotonic() + ESPERA_SUBIDA_S
    while time.monotonic() < limite:
        if processo.poll() is not None:
            pytest.fail(f"o servidor encerrou ao subir:\n{log.read_text(encoding='utf-8')}")
        try:
            with socket.create_connection((HOST, porta), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    pytest.fail(f"o servidor não abriu a porta em {ESPERA_SUBIDA_S:.0f}s")


@contextmanager
def _subir(argumentos_extra: list[str], ambiente: dict[str, str], log: Path) -> Iterator[None]:
    with log.open("w", encoding="utf-8") as saida:
        processo = subprocess.Popen(
            [sys.executable, "-m", "bussola_mcp.server", "--host", HOST, *argumentos_extra],
            cwd=DIR_MCP_SERVER,
            env=ambiente,
            stdout=saida,
            stderr=subprocess.STDOUT,
        )
        try:
            yield processo
        finally:
            processo.terminate()
            try:
                processo.wait(timeout=ESPERA_DESCIDA_S)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait()


@pytest.fixture
def servidor_http(fixtures_sinteticas: Path, tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """Servidor com ``--fixtures`` sintéticas: URL do MCP e arquivo de saída."""
    porta = _porta_livre()
    log = tmp_path / "servidor.log"
    argumentos = ["--port", str(porta), "--fixtures", str(fixtures_sinteticas)]
    with _subir(argumentos, dict(os.environ), log) as processo:
        _esperar_porta(processo, porta, log)
        yield f"http://{HOST}:{porta}/mcp", log


async def _conversar(url: str, chamadas: list[tuple[str, dict]]):
    async with httpx.AsyncClient(trust_env=False, timeout=30.0) as http:
        async with streamable_http_client(url, http_client=http) as (leitura, escrita, _):
            async with ClientSession(leitura, escrita) as sessao:
                inicio = await sessao.initialize()
                ferramentas = (await sessao.list_tools()).tools
                resultados = [await sessao.call_tool(nome, args) for nome, args in chamadas]
    return inicio, ferramentas, resultados


async def test_list_tools_e_chamada_via_streamable_http(servidor_http, fixtures_sinteticas):
    url, _ = servidor_http
    inicio, ferramentas, (resultado,) = await _conversar(
        url, [("perfil_financeiro", {"id_usuario": ID_ANCORA, "ate_anomes": 202512})]
    )
    assert inicio.serverInfo.name == "bussola-mcp"
    assert {f.name for f in ferramentas} == set(FERRAMENTAS)
    assert len(ferramentas) == 9
    assert resultado.isError is False
    arquivo = fixtures_sinteticas / "ferramentas" / arquivo_golden("perfil_financeiro", 202512)
    assert resultado.structuredContent == json.loads(arquivo.read_text(encoding="utf-8"))


async def test_erro_de_negocio_via_http_nao_e_is_error(servidor_http):
    url, _ = servidor_http
    _, _, (resultado,) = await _conversar(
        url, [("perfil_financeiro", {"id_usuario": "nao-e-uuid", "ate_anomes": 202512})]
    )
    assert resultado.isError is False
    assert resultado.structuredContent["erro"]["codigo"] == "ENTRADA_INVALIDA"


async def test_logs_do_subprocess_sao_json_sem_ids(servidor_http):
    url, log = servidor_http
    await _conversar(
        url,
        [
            ("resumo_mes", {"id_usuario": ID_ANCORA, "ate_anomes": 202512, "anomes": 202503}),
            (
                "buscar_contexto_financeiro",
                {"id_usuario": ID_ANCORA, "ate_anomes": 202512, "pergunta": "pergunta secreta"},
            ),
        ],
    )
    texto = log.read_text(encoding="utf-8")
    registros = [json.loads(linha) for linha in texto.splitlines() if linha.strip()]
    eventos = {registro.get("evento") for registro in registros}
    assert {"servidor_iniciado", "ferramenta_chamada"} <= eventos
    assert all(registro["servico"] == "bussola-mcp" for registro in registros)
    assert ID_ANCORA not in texto
    assert "pergunta secreta" not in texto


async def test_como_no_make_mcp_fakes_e_port_sem_fixtures(tmp_path):
    """Equivalente a ``make mcp``: ``BUSSOLA_FAKES=TRUE``, ``PORT`` e fixtures oficiais."""
    porta = _porta_livre()
    log = tmp_path / "make_mcp.log"
    ambiente = {**os.environ, "BUSSOLA_FAKES": "TRUE", "PORT": str(porta)}
    with _subir([], ambiente, log) as processo:
        _esperar_porta(processo, porta, log)
        _, ferramentas, (resultado,) = await _conversar(
            f"http://{HOST}:{porta}/mcp",
            [("capacidade_poupanca", {"id_usuario": ID_ANCORA, "ate_anomes": 202506})],
        )
    assert len(ferramentas) == 9
    assert resultado.structuredContent["fonte"]["periodo"]["fim"] == 202506
