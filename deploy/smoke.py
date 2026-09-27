"""Smoke de produção da Bússola (ciclo 007). Só lê: nada muda no GCP.

Três checagens independentes:

1. ``mcp``: ``initialize`` + ``tools/list`` no MCP privado, com ID token;
   ``perfil_financeiro`` precisa estar na lista;
2. ``agent``: sessão ADK nova, pergunta "qual é o meu perfil financeiro?" e
   exige a chamada de ``perfil_financeiro`` nos eventos, sem envelope de erro.
   A citação no texto vira aviso (a redação é do LLM). A sessão é apagada no
   fim;
3. ``bff``: ``GET /`` (200, HTML) e ``GET /auth/me`` (401 ``NAO_AUTENTICADO``).
   O Cloud Run reserva ``/healthz`` (404 antes do contêiner).

ID token: ``gcloud auth print-identity-token --impersonate-service-account=<SA>
--audiences=<URL principal>``. A URL da tag como audience dá 401, por isso a
audience é sempre a URL principal, mesmo com ``--tag``. O token fica só na
memória do processo: nunca é impresso, gravado ou posto em mensagem de erro.
Quem roda precisa de ``roles/iam.serviceAccountTokenCreator`` na SA.

Padrão: o caminho da demo (BFF público → agente na tag ``main`` → MCP
principal), igual a ``deploy/helm/bussola/values.yaml``.

Uso::

    make smoke
    make smoke SMOKE_ARGS="--tag c007"          # revisão com tag, 0% de tráfego
    make smoke SMOKE_ARGS="--only bff"          # sem token
    uv run --project agent python deploy/smoke.py --principal <sa> --json

Saída 0 só com todas as checagens OK; 1 se alguma falhou.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

PROJECT_NUMBER = "1061873050224"
DEFAULT_PRINCIPAL = f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
DEFAULT_MCP_URL = "https://bussola-mcp-wimifi56uq-uc.a.run.app/mcp"
DEFAULT_AGENT_URL = "https://main---bussola-agent-wimifi56uq-uc.a.run.app"
DEFAULT_BFF_URL = "https://bussola-bff-wimifi56uq-uc.a.run.app"
DEFAULT_QUESTION = "qual é o meu perfil financeiro?"
AGENT_APP = "bussola_agent"
EXPECTED_TOOL = "perfil_financeiro"
MCP_PROTOCOL = "2025-06-18"
CHECKS = ("mcp", "agent", "bff")
TAG_PATTERN = re.compile(r"^(main|c[0-9]{3}(-[a-z]{1,10})?)$")
REDACTED = "<redigido>"
_TOKEN_LIKE = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+|ya29\.[\w-]+")


class SmokeError(Exception):
    """Falha de uma checagem, com mensagem pronta para o operador."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes = b""

    def header(self, name: str) -> str:
        return self.headers.get(name.lower(), "")

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except ValueError as exc:
            raise SmokeError(f"resposta {self.status} sem JSON válido") from exc


class Transport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    """HTTP pela stdlib. Status de erro vira resposta, não exceção."""

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ) -> HttpResponse:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                return HttpResponse(resp.status, _lower(resp.headers.items()), resp.read())
        except urllib.error.HTTPError as exc:
            return HttpResponse(exc.code, _lower(exc.headers.items()), exc.read())
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            host = urllib.parse.urlsplit(url).netloc
            raise SmokeError(f"sem resposta de {host}: {reason}") from exc


def _lower(items: Iterable[tuple[str, str]]) -> dict[str, str]:
    return {name.lower(): value for name, value in items}


class TokenProvider(Protocol):
    def token(self, audience: str) -> str: ...


Runner = Callable[..., subprocess.CompletedProcess]


class GcloudTokenProvider:
    """ID token pelo ``gcloud``, direto para a memória (um por audience)."""

    def __init__(self, principal: str, runner: Runner = subprocess.run) -> None:
        self.principal = principal
        self._runner = runner
        self._cache: dict[str, str] = {}

    def command(self, audience: str) -> list[str]:
        return [
            "gcloud",
            "auth",
            "print-identity-token",
            f"--impersonate-service-account={self.principal}",
            f"--audiences={audience}",
            "--quiet",
        ]

    def token(self, audience: str) -> str:
        if audience not in self._cache:
            try:
                result = self._runner(
                    self.command(audience), capture_output=True, text=True, check=False
                )
            except FileNotFoundError as exc:
                raise SmokeError("gcloud não encontrado no PATH") from exc
            token = result.stdout.strip()
            if result.returncode != 0 or not token:
                raise SmokeError(
                    f"gcloud não gerou o ID token para {audience}. Confira `gcloud auth login` "
                    f"e roles/iam.serviceAccountTokenCreator em {self.principal}"
                )
            self._cache[audience] = token
        return self._cache[audience]

    def issued(self) -> list[str]:
        return list(self._cache.values())


class NoTokenProvider:
    """Sem ``Authorization`` (MCP mock local, ``--no-token``)."""

    def token(self, audience: str) -> str:
        return ""

    def issued(self) -> list[str]:
        return []


@dataclass(frozen=True)
class Target:
    url: str
    audience: str


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str
    url: str = ""
    warnings: list[str] = field(default_factory=list)


# --- URLs ---


def main_url(url: str) -> str:
    """Origem da URL principal (sem ``<tag>---`` e sem caminho): a audience."""
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.split("---", 1)[-1]
    return f"{parts.scheme}://{host}"


def tag_url(url: str, tag: str) -> str:
    """URL da revisão com tag: ``https://<tag>---<serviço>...``, mesmo caminho."""
    parts = urllib.parse.urlsplit(url)
    host = parts.netloc.split("---", 1)[-1]
    return urllib.parse.urlunsplit(parts._replace(netloc=f"{tag}---{host}"))


def target(url: str, tag: str | None = None) -> Target:
    return Target(tag_url(url, tag) if tag else url, main_url(url))


def _auth_headers(tokens: TokenProvider, audience: str) -> dict[str, str]:
    token = tokens.token(audience)
    return {"Authorization": f"Bearer {token}"} if token else {}


def http_problem(step: str, response: HttpResponse, service: str) -> str:
    hints = {
        401: "token recusado: a audience deve ser a URL principal (a da tag dá 401)",
        403: (
            "o principal não tem roles/run.invoker no serviço; mudar IAM exige "
            "confirmação humana (docs/operacao.md)"
        ),
        404: "rota não encontrada (o Cloud Run reserva /healthz)",
    }
    if service == "agent":
        hints[429] = "Gemini sem cota: espere ou use o Plano B (docs/operacao.md)"
        hints[503] = "Gemini em demanda alta ou instância reiniciando: tente de novo"
    hint = hints.get(response.status)
    if hint is None and response.status >= 500:
        hint = "erro do serviço: veja os logs (docs/operacao.md)"
    return f"{step} deu {response.status}" + (f": {hint}" if hint else "")


# --- MCP ---


def parse_jsonrpc(response: HttpResponse, request_id: int) -> dict[str, Any]:
    """Mensagem JSON-RPC ``request_id`` de uma resposta JSON ou SSE."""
    if "text/event-stream" in response.header("content-type"):
        messages = []
        for event in re.split(r"\r?\n\r?\n", response.text()):
            data = [line[5:].lstrip() for line in event.splitlines() if line.startswith("data:")]
            if data:
                messages.append(json.loads("\n".join(data)))
    else:
        payload = response.json()
        messages = payload if isinstance(payload, list) else [payload]
    for message in messages:
        if isinstance(message, dict) and message.get("id") == request_id:
            if "error" in message:
                raise SmokeError(f"JSON-RPC {request_id}: {message['error'].get('message', '?')}")
            return message
    raise SmokeError(f"resposta sem a mensagem JSON-RPC {request_id}")


def _rpc(method: str, request_id: int | None = None, params: dict | None = None) -> bytes:
    message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return json.dumps(message).encode()


def check_mcp(
    transport: Transport, tokens: TokenProvider, mcp: Target, timeout: float
) -> CheckResult:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        **_auth_headers(tokens, mcp.audience),
    }
    init = _rpc(
        "initialize",
        1,
        {
            "protocolVersion": MCP_PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "bussola-smoke", "version": "1"},
        },
    )
    response = transport.request("POST", mcp.url, headers, init, timeout)
    if response.status != 200:
        raise SmokeError(http_problem("initialize", response, "mcp"))
    result = parse_jsonrpc(response, 1)["result"]
    headers["MCP-Protocol-Version"] = result.get("protocolVersion", MCP_PROTOCOL)
    session = response.header("mcp-session-id")
    if session:
        headers["Mcp-Session-Id"] = session
    response = transport.request(
        "POST", mcp.url, headers, _rpc("notifications/initialized"), timeout
    )
    if response.status not in (200, 202):
        raise SmokeError(http_problem("notifications/initialized", response, "mcp"))
    response = transport.request("POST", mcp.url, headers, _rpc("tools/list", 2, {}), timeout)
    if response.status != 200:
        raise SmokeError(http_problem("tools/list", response, "mcp"))
    tools = sorted(tool["name"] for tool in parse_jsonrpc(response, 2)["result"]["tools"])
    if session:
        try:
            transport.request("DELETE", mcp.url, headers, None, timeout)
        except SmokeError:
            pass  # encerrar a sessão MCP é cortesia
    if EXPECTED_TOOL not in tools:
        raise SmokeError(f"{EXPECTED_TOOL} fora do tools/list ({', '.join(tools) or 'vazio'})")
    return CheckResult("mcp", True, f"{len(tools)} ferramentas, {EXPECTED_TOOL} presente")


# --- Agente (ADK) ---


def _parts(events: Sequence[Any]) -> Iterable[dict[str, Any]]:
    for event in events:
        if isinstance(event, dict):
            for part in (event.get("content") or {}).get("parts") or []:
                if isinstance(part, dict):
                    yield part


def function_calls(events: Sequence[Any]) -> list[str]:
    return [
        part["functionCall"].get("name", "") for part in _parts(events) if "functionCall" in part
    ]


def error_code(value: Any) -> str | None:
    """Código do primeiro envelope ``{erro: {codigo}}`` (também em texto JSON)."""
    if isinstance(value, dict):
        erro = value.get("erro")
        if isinstance(erro, dict) and erro.get("codigo"):
            return str(erro["codigo"])
        return next((c for c in map(error_code, value.values()) if c), None)
    if isinstance(value, list):
        return next((c for c in map(error_code, value) if c), None)
    if isinstance(value, str) and value.lstrip().startswith("{"):
        try:
            return error_code(json.loads(value))
        except ValueError:
            return None
    return None


def tool_error(events: Sequence[Any], tool: str) -> str | None:
    for part in _parts(events):
        response = part.get("functionResponse")
        if isinstance(response, dict) and response.get("name") == tool:
            code = error_code(response.get("response"))
            if code:
                return code
    return None


def final_text(events: Sequence[Any]) -> str:
    texts = [
        part["text"]
        for event in events
        if isinstance(event, dict) and not event.get("partial")
        for part in (event.get("content") or {}).get("parts") or []
        if isinstance(part, dict) and part.get("text") and not part.get("thought")
    ]
    return texts[-1].strip() if texts else ""


def check_agent(
    transport: Transport,
    tokens: TokenProvider,
    agent: Target,
    timeout: float,
    question: str = DEFAULT_QUESTION,
) -> CheckResult:
    base = agent.url.rstrip("/")
    user = f"smoke-{uuid.uuid4().hex[:8]}"
    sessions = f"{base}/apps/{AGENT_APP}/users/{user}/sessions"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        **_auth_headers(tokens, agent.audience),
    }
    response = transport.request("POST", sessions, headers, b'{"state": {}}', timeout)
    if response.status != 200:
        raise SmokeError(http_problem("criar sessão", response, "agent"))
    session_id = str(response.json().get("id", ""))
    if not session_id:
        raise SmokeError("criar sessão: resposta sem id")
    run = {
        "appName": AGENT_APP,
        "userId": user,
        "sessionId": session_id,
        "newMessage": {"role": "user", "parts": [{"text": question}]},
    }
    try:
        response = transport.request(
            "POST", f"{base}/run", headers, json.dumps(run).encode(), timeout
        )
        if response.status != 200:
            raise SmokeError(http_problem("run", response, "agent"))
        events = response.json()
        if not isinstance(events, list):
            raise SmokeError("run: resposta não é uma lista de eventos")
    finally:
        try:
            transport.request("DELETE", f"{sessions}/{session_id}", headers, None, timeout)
        except SmokeError:
            pass  # a sessão em memória some no restart de qualquer jeito
    calls = function_calls(events)
    if EXPECTED_TOOL not in calls:
        raise SmokeError(
            f"o agente não chamou {EXPECTED_TOOL} (chamou: {', '.join(calls) or 'nenhuma'})"
        )
    code = tool_error(events, EXPECTED_TOOL)
    if code:
        raise SmokeError(f"{EXPECTED_TOOL} respondeu erro {code} (veja os logs do MCP)")
    text = final_text(events)
    warnings = []
    if not text:
        warnings.append("resposta final sem texto")
    elif EXPECTED_TOOL not in text and "perfil financeiro" not in text.lower():
        warnings.append(f"o texto não cita {EXPECTED_TOOL} (a redação é do LLM)")
    detail = f"sessão nova, {EXPECTED_TOOL} chamado, resposta com {len(text)} caracteres"
    return CheckResult("agent", True, detail, warnings=warnings)


# --- BFF ---


def check_bff(transport: Transport, bff_url: str, timeout: float) -> CheckResult:
    base = bff_url.rstrip("/")
    response = transport.request("GET", f"{base}/", {"Accept": "text/html"}, None, timeout)
    if response.status != 200 or "text/html" not in response.header("content-type"):
        kind = response.header("content-type") or "sem content-type"
        raise SmokeError(f"GET / deu {response.status} ({kind}), esperado 200 com HTML")
    response = transport.request(
        "GET", f"{base}/auth/me", {"Accept": "application/json"}, None, timeout
    )
    if response.status != 401:
        raise SmokeError(f"GET /auth/me deu {response.status}, esperado 401")
    code = error_code(response.json())
    if code != "NAO_AUTENTICADO":
        raise SmokeError(f"GET /auth/me sem erro NAO_AUTENTICADO (veio {code})")
    return CheckResult("bff", True, "GET / 200 (HTML), GET /auth/me 401 NAO_AUTENTICADO")


# --- Execução ---


@dataclass(frozen=True)
class Config:
    mcp: Target
    agent: Target
    bff_url: str
    only: tuple[str, ...] = CHECKS
    question: str = DEFAULT_QUESTION
    timeout: float = 90.0


def run_checks(config: Config, transport: Transport, tokens: TokenProvider) -> list[CheckResult]:
    checks: dict[str, tuple[str, Callable[[], CheckResult]]] = {
        "mcp": (config.mcp.url, lambda: check_mcp(transport, tokens, config.mcp, config.timeout)),
        "agent": (
            config.agent.url,
            lambda: check_agent(transport, tokens, config.agent, config.timeout, config.question),
        ),
        "bff": (config.bff_url, lambda: check_bff(transport, config.bff_url, config.timeout)),
    }
    results = []
    for name in CHECKS:
        if name not in config.only:
            continue
        url, check = checks[name]
        try:
            result = check()
        except SmokeError as exc:
            result = CheckResult(name, False, str(exc))
        except (KeyError, TypeError, ValueError) as exc:
            result = CheckResult(name, False, f"resposta fora do formato esperado ({exc!r})")
        result.url = url
        results.append(result)
    return results


def redact(text: str, secrets: Iterable[str]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return _TOKEN_LIKE.sub(REDACTED, text)


def report(results: Sequence[CheckResult], as_json: bool, secrets: Iterable[str]) -> str:
    secrets = list(secrets)
    if as_json:
        return redact(json.dumps([asdict(r) for r in results], ensure_ascii=False), secrets)
    lines = []
    for result in results:
        status = "OK" if result.ok else "FALHA"
        lines.append(f"[{status}] {result.name}: {result.detail} ({result.url})")
        lines.extend(f"  [AVISO] {warning}" for warning in result.warnings)
    ok = sum(r.ok for r in results)
    lines.append(f"{ok}/{len(results)} checagens OK")
    return redact("\n".join(lines), secrets)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke de produção da Bússola (só leitura; nenhum token é impresso)."
    )
    parser.add_argument("--tag", help="revisão com tag (main, cNNN, cNNN-rótulo) nos três serviços")
    parser.add_argument("--only", default=",".join(CHECKS), help="mcp,agent,bff (padrão: todos)")
    parser.add_argument(
        "--principal", default=DEFAULT_PRINCIPAL, help="SA impersonada para o ID token"
    )
    parser.add_argument("--no-token", action="store_true", help="sem Authorization (MCP local)")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    parser.add_argument("--agent-url", default=DEFAULT_AGENT_URL)
    parser.add_argument("--bff-url", default=DEFAULT_BFF_URL)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--timeout", type=float, default=90.0, help="segundos por requisição")
    parser.add_argument("--json", action="store_true", help="relatório em JSON")
    args = parser.parse_args(argv)
    if args.tag and not TAG_PATTERN.match(args.tag):
        parser.error("--tag deve ser main, cNNN ou cNNN-<rótulo>")
    only = tuple(item.strip() for item in args.only.split(",") if item.strip())
    unknown = sorted(set(only) - set(CHECKS))
    if unknown or not only:
        parser.error(f"--only aceita {', '.join(CHECKS)}")
    args.only = only
    return args


def build_config(args: argparse.Namespace) -> Config:
    return Config(
        mcp=target(args.mcp_url, args.tag),
        agent=target(args.agent_url, args.tag),
        bff_url=tag_url(args.bff_url, args.tag) if args.tag else args.bff_url,
        only=args.only,
        question=args.question,
        timeout=args.timeout,
    )


def main(
    argv: Sequence[str] | None = None,
    transport: Transport | None = None,
    tokens: TokenProvider | None = None,
    out: Callable[[str], None] = print,
) -> int:
    args = parse_args(argv)
    config = build_config(args)
    if tokens is None:
        tokens = NoTokenProvider() if args.no_token else GcloudTokenProvider(args.principal)
    results = run_checks(config, transport or UrllibTransport(), tokens)
    issued = tokens.issued() if hasattr(tokens, "issued") else []
    out(report(results, args.json, issued))
    return 0 if results and all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
