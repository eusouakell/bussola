"""MCP mock em subprocess, via streamable HTTP em ``/mcp`` (T022, FR-017).

Sobe ``python -m bussola_mcp.server`` em ``127.0.0.1`` numa porta livre e conversa com
ele pelo cliente do SDK oficial. Não sai do loopback.
"""

import json
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from bussola_mcp.contratos import FERRAMENTAS_MOCK, ID_ANCORA, arquivo_golden

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


@pytest.fixture
def servidor_http(fixtures_sinteticas: Path, tmp_path: Path) -> Iterator[tuple[str, Path]]:
    """URL do MCP em subprocess e o arquivo com a saída dele (stdout + stderr)."""
    porta = _porta_livre()
    log = tmp_path / "servidor.log"
    comando = [
        sys.executable,  # o mesmo ambiente do uv que roda os testes
        "-m",
        "bussola_mcp.server",
        "--host",
        HOST,
        "--port",
        str(porta),
        "--fixtures",
        str(fixtures_sinteticas),
    ]
    with log.open("w", encoding="utf-8") as saida:
        processo = subprocess.Popen(
            comando, cwd=DIR_MCP_SERVER, stdout=saida, stderr=subprocess.STDOUT
        )
        try:
            _esperar_porta(processo, porta, log)
            yield f"http://{HOST}:{porta}/mcp", log
        finally:
            processo.terminate()
            try:
                processo.wait(timeout=ESPERA_DESCIDA_S)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait()


async def test_list_tools_via_streamable_http(servidor_http, fixtures_sinteticas):
    url, _ = servidor_http
    async with httpx.AsyncClient(trust_env=False, timeout=30.0) as http:
        async with streamable_http_client(url, http_client=http) as (leitura, escrita, _):
            async with ClientSession(leitura, escrita) as sessao:
                inicio = await sessao.initialize()
                ferramentas = (await sessao.list_tools()).tools
                resultado = await sessao.call_tool(
                    "perfil_financeiro", {"id_usuario": ID_ANCORA, "ate_anomes": 202512}
                )

    assert inicio.serverInfo.name == "bussola-mcp"
    assert len(ferramentas) == 8
    assert {f.name for f in ferramentas} == set(FERRAMENTAS_MOCK)
    assert resultado.isError is False
    arquivo = fixtures_sinteticas / "ferramentas" / arquivo_golden("perfil_financeiro", 202512)
    golden = json.loads(arquivo.read_text(encoding="utf-8"))
    assert resultado.structuredContent == golden


async def test_logs_do_subprocess_sao_json(servidor_http):
    url, log = servidor_http
    async with httpx.AsyncClient(trust_env=False, timeout=30.0) as http:
        async with streamable_http_client(url, http_client=http) as (leitura, escrita, _):
            async with ClientSession(leitura, escrita) as sessao:
                await sessao.initialize()
                await sessao.call_tool(
                    "resumo_mes", {"id_usuario": ID_ANCORA, "ate_anomes": 202512, "anomes": 202503}
                )

    linhas = [linha for linha in log.read_text(encoding="utf-8").splitlines() if linha.strip()]
    registros = [json.loads(linha) for linha in linhas]  # falha se alguma linha não for JSON
    eventos = {registro.get("evento") for registro in registros}
    assert {"servidor_iniciado", "ferramenta_chamada"} <= eventos
    assert all(registro["servico"] == "bussola-mcp" for registro in registros)
    assert ID_ANCORA not in log.read_text(encoding="utf-8")
