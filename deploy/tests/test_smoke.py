"""Smoke de produção (``deploy/smoke.py``), sem rede externa e sem GCP.

Unitários com transporte e token fakes; integração com o MCP mock real
(``mcp_server``) e servidores fake do ADK e do BFF em ``127.0.0.1``.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import smoke
import yaml
from helm_render import CHART, ROOT

TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJhdWQiOiJ4In0.c2lnbmF0dXJh"
MCP_TAG_URL = "https://c007---bussola-mcp-wimifi56uq-uc.a.run.app/mcp"
MCP_MAIN = "https://bussola-mcp-wimifi56uq-uc.a.run.app"
AGENT_MAIN = "https://bussola-agent-wimifi56uq-uc.a.run.app"


# --- Fakes ---


Handler = Callable[[str, dict[str, str], bytes | None], smoke.HttpResponse]


class FakeTransport:
    """Responde por ``(método, caminho)`` e guarda as requisições."""

    def __init__(self, routes: dict[tuple[str, str], Handler | smoke.HttpResponse]) -> None:
        self.routes = routes
        self.requests: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def request(self, method, url, headers, body, timeout):
        self.requests.append((method, url, dict(headers), body))
        path = urlsplit(url).path
        route = self.routes.get((method, path))
        if route is None:
            prefix = next(
                (k for k in self.routes if k[0] == method and path.startswith(k[1])), None
            )
            route = self.routes.get(prefix) if prefix else None
        if route is None:
            return smoke.HttpResponse(404, {}, b"")
        return route(url, headers, body) if callable(route) else route

    def paths(self, method: str | None = None) -> list[str]:
        return [urlsplit(u).path for m, u, _, _ in self.requests if method in (None, m)]


class FakeTokens:
    def __init__(self, token: str = TOKEN) -> None:
        self.value = token
        self.audiences: list[str] = []

    def token(self, audience: str) -> str:
        self.audiences.append(audience)
        return self.value

    def issued(self) -> list[str]:
        return [self.value]


class ForbiddenTokens:
    def token(self, audience: str) -> str:
        raise AssertionError("o BFF é público: nenhum token deveria ser pedido")


def json_response(status: int, payload, headers: dict[str, str] | None = None):
    return smoke.HttpResponse(
        status,
        {"content-type": "application/json", **(headers or {})},
        json.dumps(payload).encode(),
    )


def sse_response(payload, session: str = "sessao-1"):
    body = f"event: message\ndata: {json.dumps(payload)}\n\n".encode()
    return smoke.HttpResponse(
        200, {"content-type": "text/event-stream", "mcp-session-id": session}, body
    )


TOOLS = ["perfil_financeiro", "capacidade_poupanca", "comparar_cenarios"]


def mcp_routes(tools=TOOLS, init_status: int = 200) -> dict:
    def post(url, headers, body):
        message = json.loads(body)
        if message["method"] == "initialize":
            if init_status != 200:
                return json_response(init_status, {"error": "x"})
            result = {"protocolVersion": "2025-06-18", "capabilities": {}, "serverInfo": {}}
            return sse_response({"jsonrpc": "2.0", "id": 1, "result": result})
        assert headers["Mcp-Session-Id"] == "sessao-1"
        assert headers["MCP-Protocol-Version"] == "2025-06-18"
        if message["method"] == "notifications/initialized":
            return smoke.HttpResponse(202, {}, b"")
        listed = {"tools": [{"name": name, "inputSchema": {}} for name in tools]}
        return sse_response({"jsonrpc": "2.0", "id": 2, "result": listed})

    return {("POST", "/mcp"): post, ("DELETE", "/mcp"): smoke.HttpResponse(200, {}, b"")}


def tool_events(response: dict | None = None, text: str = "Fonte: perfil_financeiro.") -> list:
    call = {"functionCall": {"id": "c1", "name": "perfil_financeiro", "args": {"x": 1}}}
    result = {"functionResponse": {"id": "c1", "name": "perfil_financeiro", "response": response}}
    return [
        {"author": "bussola", "content": {"role": "model", "parts": [call]}},
        {"author": "bussola", "content": {"role": "user", "parts": [result]}},
        {"author": "bussola", "content": {"role": "model", "parts": [{"text": text}]}},
    ]


OK_RESPONSE = {"result": {"content": [{"type": "text", "text": '{"dados": {}, "avisos": []}'}]}}


def agent_routes(events=None, run_status: int = 200) -> dict:
    events = tool_events(OK_RESPONSE) if events is None else events
    return {
        ("POST", "/apps/bussola_agent/users/"): json_response(200, {"id": "s-1", "state": {}}),
        ("POST", "/run"): json_response(run_status, events if run_status == 200 else {}),
        ("DELETE", "/apps/bussola_agent/users/"): smoke.HttpResponse(200, {}, b""),
    }


def bff_routes(me_status: int = 401, home_status: int = 200) -> dict:
    return {
        ("GET", "/"): smoke.HttpResponse(
            home_status, {"content-type": "text/html; charset=utf-8"}, b"<!doctype html>"
        ),
        ("GET", "/auth/me"): json_response(
            me_status, {"erro": {"codigo": "NAO_AUTENTICADO", "mensagem": "Entre."}}
        ),
    }


MCP = smoke.target(smoke.DEFAULT_MCP_URL)
AGENT = smoke.target(smoke.DEFAULT_AGENT_URL)


# --- URLs e defaults ---


def test_tag_url_rewrites_host_and_keeps_path():
    assert smoke.tag_url(smoke.DEFAULT_MCP_URL, "c007") == MCP_TAG_URL
    assert smoke.tag_url(smoke.DEFAULT_AGENT_URL, "c007-bad") == (
        "https://c007-bad---bussola-agent-wimifi56uq-uc.a.run.app"
    )


def test_audience_is_always_the_main_url():
    assert smoke.main_url(MCP_TAG_URL) == MCP_MAIN
    assert smoke.main_url(smoke.DEFAULT_AGENT_URL) == AGENT_MAIN
    assert smoke.target(smoke.DEFAULT_MCP_URL, "c007") == smoke.Target(MCP_TAG_URL, MCP_MAIN)


def test_defaults_follow_the_demo_path_in_chart_values():
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    agent_env = values["services"]["agent"]["env"]
    bff = values["services"]["bff"]

    assert smoke.DEFAULT_MCP_URL == agent_env["MCP_URL"]
    assert smoke.DEFAULT_AGENT_URL == bff["env"]["AGENT_URL"]
    assert smoke.main_url(smoke.DEFAULT_AGENT_URL) == bff["env"]["AGENT_AUDIENCE"]
    assert smoke.AGENT_APP == bff["env"]["AGENT_APP"]
    assert smoke.DEFAULT_PRINCIPAL == values["serviceAccount"]
    assert smoke.DEFAULT_BFF_URL == smoke.main_url(smoke.DEFAULT_MCP_URL).replace(
        values["services"]["mcp"]["name"], bff["name"]
    )
    assert bff["public"] is True


def test_tag_option_moves_all_hosts_but_not_audiences():
    config = smoke.build_config(smoke.parse_args(["--tag", "c007"]))

    assert config.mcp == smoke.Target(MCP_TAG_URL, MCP_MAIN)
    assert config.agent.url.startswith("https://c007---bussola-agent-")
    assert config.agent.audience == AGENT_MAIN
    assert config.bff_url == "https://c007---bussola-bff-wimifi56uq-uc.a.run.app"


@pytest.mark.parametrize(
    "argv", [["--tag", "v7"], ["--tag", "main---x"], ["--only", "web"], ["--only", ","]]
)
def test_invalid_arguments_exit_with_usage_error(argv):
    with pytest.raises(SystemExit) as exc:
        smoke.parse_args(argv)
    assert exc.value.code == 2


# --- Token ---


def test_gcloud_token_impersonates_with_audience_and_caches():
    calls = []

    def runner(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=f"{TOKEN}\n", stderr="")

    tokens = smoke.GcloudTokenProvider("sa@p.iam.gserviceaccount.com", runner=runner)

    assert tokens.token(MCP_MAIN) == TOKEN
    assert tokens.token(MCP_MAIN) == TOKEN
    assert calls == [
        [
            "gcloud",
            "auth",
            "print-identity-token",
            "--impersonate-service-account=sa@p.iam.gserviceaccount.com",
            f"--audiences={MCP_MAIN}",
            "--quiet",
        ]
    ]


def test_gcloud_token_failure_does_not_echo_gcloud_output():
    def runner(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout=TOKEN, stderr="ERROR: detalhe")

    tokens = smoke.GcloudTokenProvider("sa@p", runner=runner)

    with pytest.raises(smoke.SmokeError) as exc:
        tokens.token(MCP_MAIN)
    assert TOKEN not in str(exc.value)
    assert "detalhe" not in str(exc.value)
    assert "serviceAccountTokenCreator" in str(exc.value)


# --- MCP ---


def test_parse_jsonrpc_reads_sse_and_json():
    message = {"jsonrpc": "2.0", "id": 2, "result": {"tools": []}}
    noise = {"jsonrpc": "2.0", "method": "notifications/message", "params": {}}
    sse = smoke.HttpResponse(
        200,
        {"content-type": "text/event-stream"},
        f"event: message\ndata: {json.dumps(noise)}\n\ndata: {json.dumps(message)}\n\n".encode(),
    )

    assert smoke.parse_jsonrpc(sse, 2) == message
    assert smoke.parse_jsonrpc(json_response(200, message), 2) == message
    with pytest.raises(smoke.SmokeError, match="JSON-RPC 3"):
        error = {"jsonrpc": "2.0", "id": 3, "error": {"message": "boom"}}
        smoke.parse_jsonrpc(json_response(200, error), 3)


def test_check_mcp_lists_tools_with_main_audience_token():
    transport = FakeTransport(mcp_routes())
    tokens = FakeTokens()

    result = smoke.check_mcp(transport, tokens, smoke.target(smoke.DEFAULT_MCP_URL, "c007"), 5)

    assert result.ok and "perfil_financeiro presente" in result.detail
    assert tokens.audiences == [MCP_MAIN]
    assert all(h["Authorization"] == f"Bearer {TOKEN}" for _, _, h, _ in transport.requests)
    assert [u for _, u, _, _ in transport.requests][0] == MCP_TAG_URL
    assert transport.paths("DELETE") == ["/mcp"]


def test_check_mcp_without_expected_tool_fails():
    transport = FakeTransport(mcp_routes(tools=["resumo_mes"]))

    with pytest.raises(smoke.SmokeError, match="perfil_financeiro fora do tools/list"):
        smoke.check_mcp(transport, FakeTokens(), MCP, 5)


@pytest.mark.parametrize(
    ("status", "hint"),
    [(401, "audience deve ser a URL principal"), (403, "roles/run.invoker"), (404, "/healthz")],
)
def test_check_mcp_explains_http_errors(status, hint):
    transport = FakeTransport(mcp_routes(init_status=status))

    with pytest.raises(smoke.SmokeError, match=f"initialize deu {status}.*{hint}"):
        smoke.check_mcp(transport, FakeTokens(), MCP, 5)


# --- Agente ---


def test_check_agent_requires_the_tool_call_and_deletes_the_session():
    transport = FakeTransport(agent_routes())
    tokens = FakeTokens()

    result = smoke.check_agent(transport, tokens, AGENT, 5)

    assert result.ok and result.warnings == []
    assert tokens.audiences == [AGENT_MAIN]
    run_body = json.loads(next(b for m, u, _, b in transport.requests if u.endswith("/run")))
    assert run_body["appName"] == "bussola_agent"
    assert run_body["sessionId"] == "s-1"
    assert run_body["newMessage"]["parts"] == [{"text": "qual é o meu perfil financeiro?"}]
    deleted = transport.paths("DELETE")
    assert len(deleted) == 1 and deleted[0].endswith("/sessions/s-1")


def test_check_agent_without_tool_call_fails():
    events = [{"content": {"role": "model", "parts": [{"text": "Seu perfil é ótimo."}]}}]
    transport = FakeTransport(agent_routes(events))

    with pytest.raises(smoke.SmokeError, match="não chamou perfil_financeiro .chamou: nenhuma"):
        smoke.check_agent(transport, FakeTokens(), AGENT, 5)


def test_check_agent_fails_on_tool_error_envelope():
    envelope = {"erro": {"codigo": "INDISPONIVEL", "mensagem": "Dados indisponíveis."}}
    response = {"result": {"content": [{"type": "text", "text": json.dumps(envelope)}]}}
    transport = FakeTransport(agent_routes(tool_events(response)))

    with pytest.raises(smoke.SmokeError, match="respondeu erro INDISPONIVEL"):
        smoke.check_agent(transport, FakeTokens(), AGENT, 5)


def test_check_agent_warns_when_text_does_not_cite_the_source():
    transport = FakeTransport(agent_routes(tool_events(OK_RESPONSE, text="Sobra de R$ 1.901,47.")))

    result = smoke.check_agent(transport, FakeTokens(), AGENT, 5)

    assert result.ok
    assert result.warnings == ["o texto não cita perfil_financeiro (a redação é do LLM)"]


@pytest.mark.parametrize(("status", "hint"), [(429, "Plano B"), (503, "demanda alta")])
def test_check_agent_explains_gemini_errors_and_still_deletes_session(status, hint):
    transport = FakeTransport(agent_routes(run_status=status))

    with pytest.raises(smoke.SmokeError, match=f"run deu {status}: .*{hint}"):
        smoke.check_agent(transport, FakeTokens(), AGENT, 5)
    assert len(transport.paths("DELETE")) == 1


# --- BFF ---


def test_check_bff_uses_public_routes_without_token():
    transport = FakeTransport(bff_routes())

    results = smoke.run_checks(
        smoke.Config(MCP, AGENT, smoke.DEFAULT_BFF_URL, only=("bff",)), transport, ForbiddenTokens()
    )

    assert [(r.name, r.ok) for r in results] == [("bff", True)]
    assert transport.paths() == ["/", "/auth/me"]
    assert all("Authorization" not in h for _, _, h, _ in transport.requests)


@pytest.mark.parametrize(
    ("routes", "message"),
    [
        (bff_routes(me_status=200), "GET /auth/me deu 200, esperado 401"),
        (bff_routes(home_status=404), "GET / deu 404"),
    ],
)
def test_check_bff_failures(routes, message):
    with pytest.raises(smoke.SmokeError, match=message):
        smoke.check_bff(FakeTransport(routes), smoke.DEFAULT_BFF_URL, 5)


# --- Relatório e saída ---


def all_routes() -> dict:
    return {**mcp_routes(), **agent_routes(), **bff_routes()}


def test_main_returns_zero_only_when_every_check_passes():
    lines: list[str] = []

    code = smoke.main(
        [], transport=FakeTransport(all_routes()), tokens=FakeTokens(), out=lines.append
    )

    assert code == 0
    assert lines[0].splitlines()[-1] == "3/3 checagens OK"


def test_main_returns_one_when_a_check_fails():
    routes = {**all_routes(), **bff_routes(me_status=500)}

    code = smoke.main([], transport=FakeTransport(routes), tokens=FakeTokens(), out=lambda _: None)

    assert code == 1


def test_token_never_appears_in_the_report():
    def leaky(url, headers, body):  # um servidor que devolvesse o cabeçalho no corpo
        return json_response(500, {"eco": headers.get("Authorization")})

    routes = {("POST", "/mcp"): leaky, **agent_routes(run_status=401), **bff_routes()}
    for as_json in ([], ["--json"]):
        lines: list[str] = []
        smoke.main(as_json, transport=FakeTransport(routes), tokens=FakeTokens(), out=lines.append)
        output = "\n".join(lines)
        assert TOKEN not in output
        assert "Bearer" not in output


def test_redact_hides_issued_and_token_like_values():
    access_token = "ya29." + "a" * 30  # montado em tempo de execução (política de segredos)
    text = f"a {TOKEN} b {access_token} c segredo"

    redacted = smoke.redact(text, ["segredo"])

    assert redacted == "a <redigido> b <redigido> c <redigido>"


def test_json_report_lists_each_check():
    lines: list[str] = []

    smoke.main(
        ["--json", "--only", "bff,mcp"],
        transport=FakeTransport(all_routes()),
        tokens=FakeTokens(),
        out=lines.append,
    )

    report = json.loads(lines[0])
    assert [item["name"] for item in report] == ["mcp", "bff"]
    assert all(item["ok"] for item in report)


# --- Integração: MCP mock real e fakes HTTP do ADK e do BFF ---

MCP_PYTHON = ROOT / "mcp_server" / ".venv" / "bin" / "python"
needs_mcp_env = pytest.mark.skipif(
    not MCP_PYTHON.exists(), reason="ambiente do mcp_server ausente (rode make test ou uv sync)"
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_port(port: int, process: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"o MCP mock saiu com código {process.returncode}")
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError("o MCP mock não abriu a porta a tempo")


@pytest.fixture(scope="module")
def mcp_mock_url() -> Iterator[str]:
    if not MCP_PYTHON.exists():
        pytest.skip("ambiente do mcp_server ausente")
    port = free_port()
    env = {**os.environ, "BUSSOLA_FAKES": "TRUE"}
    process = subprocess.Popen(
        [str(MCP_PYTHON), "-m", "bussola_mcp.server", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT / "mcp_server",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port(port, process)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(timeout=10)


class _FakeServices(BaseHTTPRequestHandler):
    """ADK e BFF fake: rotas mínimas que o smoke usa."""

    events: list = tool_events(OK_RESPONSE)
    seen: list[tuple[str, str, str]] = []

    def log_message(self, *args) -> None:  # silencia o http.server
        pass

    def _send(self, status: int, payload, content_type: str = "application/json") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _record(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.seen.append((self.command, self.path, self.headers.get("Authorization", "")))
        return body

    def do_GET(self) -> None:  # noqa: N802
        self._record()
        if self.path == "/":
            self._send(200, b"<!doctype html><title>Bussola</title>", "text/html; charset=utf-8")
        elif self.path == "/auth/me":
            self._send(401, {"erro": {"codigo": "NAO_AUTENTICADO", "mensagem": "Entre."}})
        else:
            self._send(404, {})

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self._record() or b"{}")
        if self.path.startswith("/apps/bussola_agent/users/") and self.path.endswith("/sessions"):
            self._send(200, {"id": "s-int", "state": body.get("state", {})})
        elif self.path == "/run" and body["newMessage"]["parts"][0]["text"]:
            self._send(200, self.events)
        else:
            self._send(404, {})

    def do_DELETE(self) -> None:  # noqa: N802
        self._record()
        self._send(200, {})


@contextmanager
def fake_services() -> Iterator[str]:
    _FakeServices.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FakeServices)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@needs_mcp_env
def test_integration_check_mcp_against_local_mock(mcp_mock_url):
    result = smoke.check_mcp(
        smoke.UrllibTransport(), smoke.NoTokenProvider(), smoke.target(mcp_mock_url), 10
    )

    assert result.ok, result.detail
    assert "perfil_financeiro presente" in result.detail


@needs_mcp_env
def test_integration_full_cli_run(mcp_mock_url):
    with fake_services() as base:
        lines: list[str] = []
        argv = [
            "--no-token",
            "--json",
            "--timeout",
            "10",
            "--mcp-url",
            mcp_mock_url,
            "--agent-url",
            base,
            "--bff-url",
            base,
        ]

        code = smoke.main(argv, out=lines.append)

    report = json.loads(lines[0])
    assert code == 0, report
    assert [(item["name"], item["ok"]) for item in report] == [
        ("mcp", True),
        ("agent", True),
        ("bff", True),
    ]
    methods = [method for method, _, _ in _FakeServices.seen]
    assert methods.count("DELETE") == 1  # sessão ADK apagada
    assert all(auth == "" for _, _, auth in _FakeServices.seen)


def test_integration_cli_entry_point_reports_failure_exit_code():
    with fake_services() as base:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(smoke.__file__)),
                "--only",
                "bff,agent",
                "--no-token",
                "--timeout",
                "10",
                "--agent-url",
                f"{base}/nada",
                "--bff-url",
                base,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    assert result.returncode == 1
    assert "[FALHA] agent: criar sessão deu 404" in result.stdout
    assert "[OK] bff:" in result.stdout
    assert result.stdout.strip().endswith("1/2 checagens OK")
