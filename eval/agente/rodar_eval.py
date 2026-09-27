"""Eval do agente Bússola (ciclo 004; spec FR-017, AC-08).

Roda os casos de ``perguntas.yaml`` no ``root_agent`` real (ferramentas,
instrução e callbacks) num ``InMemoryRunner``, contra o MCP local em modo fake
(o mock do 000 com ``contracts/fixtures/``, iniciado aqui em ``127.0.0.1``).
Para cada resposta final, confere se **todo número** aparece no retorno das
ferramentas do turno ou no que o cliente disse na sessão, com a mesma leitura
de números do ``after_model`` 50 (:mod:`bussola_agent.jornada.number_check`).

Modos:

- ``offline``: o modelo é o roteiro de cada turno; sem Gemini e sem rede fora
  de loopback. Falha em qualquer número sem fonte ou expectativa não cumprida.
- ``ao-vivo``: o Gemini real (``GOOGLE_API_KEY`` com
  ``GOOGLE_GENAI_USE_VERTEXAI=FALSE``, ou ADC da Vertex) decide as chamadas.
  Só casos ``ao_vivo: true``, todos com perguntas comuns de cliente. Falha
  apenas em número sem fonte; expectativas de ferramenta e etapa são
  relatadas.

O resultado de cada modo substitui só a sua seção em ``RESULTADOS.md``. O
arquivo não guarda o texto das respostas (``--mostrar`` as imprime no
terminal) nem segredos.

Uso (a partir de ``agent/``)::

    uv run python ../eval/agente/rodar_eval.py --modo offline
    GOOGLE_GENAI_USE_VERTEXAI=FALSE GOOGLE_API_KEY=... \\
        uv run python ../eval/agente/rodar_eval.py --modo ao-vivo

``--mcp-url`` usa um MCP já no ar (por exemplo, o real do 003 via
``make mcp``) em vez de iniciar o mock.
"""

import argparse
import asyncio
import contextlib
import importlib
import io
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import AsyncGenerator, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import PrivateAttr

from bussola_agent.estado import (
    CHAVE_ATE_ANOMES,
    CHAVE_ESTADO_JORNADA,
    CHAVE_OBJETIVO,
    EstadoJornada,
)
from bussola_agent.jornada.number_check import (
    checked_numbers,
    cites_source,
    evidence_from,
    is_supported,
)
from bussola_agent.jornada.tool_results import tool_outcomes
from bussola_agent.logging_json import configurar_logging
from bussola_agent.resilient_model import CAPACITY_MESSAGE

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MCP_DIR = ROOT / "mcp_server"
FIXTURES_DIR = ROOT / "contracts" / "fixtures"
DEFAULT_QUESTIONS = HERE / "perguntas.yaml"
DEFAULT_OUTPUT = HERE / "RESULTADOS.md"
APP = "bussola_agent"
AGENT_AUTHOR = "bussola"
USER = "eval"
ANCHOR = "36a21505-d6d4-42d3-b319-d51a133c7269"
SERVER_WAIT_S = 90.0
MODE_OFFLINE = "offline"
MODE_LIVE = "ao-vivo"
BLOCKS = ("Diagnóstico", "Simulação", "Recomendação")
STAGES = [stage.value for stage in EstadoJornada]
REPORT_HEADER = """# Resultados do eval do agente

Gerado por `eval/agente/rodar_eval.py` a partir de `eval/agente/perguntas.yaml`
(ciclo 004, FR-017 e AC-08). Cada modo reescreve só a sua seção. O texto das
respostas não é gravado aqui.
"""


# ---------------------------------------------------------------------------
# Casos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Turn:
    client: str
    expect: Mapping[str, Any]
    script: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    live: bool
    state: Mapping[str, Any]
    turns: Sequence[Turn]


def load_cases(path: Path) -> tuple[int, list[Case]]:
    """``ate_anomes`` e os casos de ``perguntas.yaml``."""
    data = yaml.safe_load(path.read_text("utf-8"))
    cases = [
        Case(
            id=str(item["id"]),
            title=str(item.get("titulo") or item["id"]),
            live=bool(item.get("ao_vivo", False)),
            state=dict(item.get("estado") or {}),
            turns=[
                Turn(
                    client=str(turn["cliente"]),
                    expect=dict(turn.get("espera") or {}),
                    script=list(turn.get("roteiro") or []),
                )
                for turn in item["turnos"]
            ],
        )
        for item in data["casos"]
    ]
    return int(data["ate_anomes"]), cases


# ---------------------------------------------------------------------------
# Mock MCP do 000 em subprocesso
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, sig)
        try:
            process.wait(timeout=10)
            return
        except subprocess.TimeoutExpired:
            continue


@contextlib.contextmanager
def mock_mcp() -> Iterator[str]:
    """Inicia o mock em ``127.0.0.1`` numa porta livre e devolve a URL ``/mcp``."""
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("O eval precisa do uv para iniciar o mock MCP.")
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONUNBUFFERED"] = "1"
    with tempfile.TemporaryDirectory(prefix="bussola_eval_") as tmp:
        log = Path(tmp) / "mock.log"
        with log.open("wb") as out:
            process = subprocess.Popen(
                [
                    uv,
                    "run",
                    "--frozen",
                    "--project",
                    str(MCP_DIR),
                    "python",
                    "-m",
                    "bussola_mcp.server",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--fixtures",
                    str(FIXTURES_DIR),
                ],
                cwd=MCP_DIR,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            deadline = time.monotonic() + SERVER_WAIT_S
            while True:
                if process.poll() is not None:
                    raise SystemExit("O mock MCP encerrou antes de abrir a porta.")
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise SystemExit("O mock MCP não abriu a porta a tempo.") from None
                    time.sleep(0.1)
            yield f"http://127.0.0.1:{port}/mcp"
        finally:
            _stop(process)


# ---------------------------------------------------------------------------
# Modelo roteirizado (modo offline)
# ---------------------------------------------------------------------------

SCRIPT_EXHAUSTED = "[roteiro esgotado]"
# Uso zerado: o roteiro não consome tokens (e a telemetria do ADK não reclama).
NO_USAGE = types.GenerateContentResponseUsageMetadata(
    prompt_token_count=0, candidates_token_count=0, total_token_count=0
)


def script_responses(script: Sequence[Mapping[str, Any]]) -> list[LlmResponse]:
    """Passos ``chamar`` (chamadas paralelas) e ``responder`` (texto final)."""
    responses = []
    for step in script:
        if "chamar" in step:
            parts = [
                types.Part(function_call=types.FunctionCall(name=name, args=dict(args or {})))
                for call in step["chamar"]
                for name, args in call.items()
            ]
        else:
            parts = [types.Part(text=str(step["responder"]).strip())]
        responses.append(
            LlmResponse(content=types.Content(role="model", parts=parts), usage_metadata=NO_USAGE)
        )
    return responses


class ScriptedLlm(BaseLlm):
    """Devolve o roteiro do turno em ordem; esgotado, responde ``SCRIPT_EXHAUSTED``."""

    model: str = "roteiro"
    _script: list[LlmResponse] = PrivateAttr(default_factory=list)

    def load(self, responses: Sequence[LlmResponse]) -> None:
        self._script = list(responses)

    @property
    def pending(self) -> int:
        return len(self._script)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if not self._script:
            text = types.Part(text=SCRIPT_EXHAUSTED)
            content = types.Content(role="model", parts=[text])
            yield LlmResponse(content=content, usage_metadata=NO_USAGE)
            return
        yield self._script.pop(0)


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------


@dataclass
class TurnResult:
    client: str
    tools_ok: list[str] = field(default_factory=list)
    tools_failed: list[str] = field(default_factory=list)
    stage: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    checked: int = 0
    from_tools: int = 0
    from_session: int = 0
    unsupported: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    cites_source: bool = False
    expectations: list[tuple[str, bool]] = field(default_factory=list)
    events: Counter[str] = field(default_factory=Counter)
    latency_ms: int = 0
    unavailable: bool = False
    text: str = ""

    @property
    def expectations_ok(self) -> bool:
        return all(ok for _, ok in self.expectations)


@dataclass
class CaseResult:
    case: Case
    turns: list[TurnResult] = field(default_factory=list)


def _final_text(events: list[Event]) -> str:
    finals = [
        e
        for e in events
        if e.author == AGENT_AUTHOR
        and not e.partial
        and e.content
        and any(p.text and not p.thought for p in e.content.parts or [])
    ]
    if not finals:
        return ""
    parts = finals[-1].content.parts or []
    return "".join(p.text for p in parts if p.text and not p.thought)


def _final_metadata(events: list[Event]) -> dict[str, Any]:
    for event in reversed(events):
        if event.author == AGENT_AUTHOR and not event.partial and event.custom_metadata:
            bussola = event.custom_metadata.get("bussola")
            return dict(bussola) if isinstance(bussola, Mapping) else {}
    return {}


def _reached(stage: str | None, expected: str) -> bool:
    if stage not in STAGES or expected not in STAGES:
        return False
    return STAGES.index(stage) >= STAGES.index(expected)


def check_expectations(
    expect: Mapping[str, Any], result: TurnResult, case_tools_ok: set[str], live: bool
) -> list[tuple[str, bool]]:
    """Cada expectativa do turno e se foi cumprida."""
    checks: list[tuple[str, bool]] = []
    answered = case_tools_ok if live else set(result.tools_ok)
    for tool in expect.get("ferramentas") or ():
        checks.append((f"{tool} respondeu", tool in answered))
    any_of = list(expect.get("alguma_de") or ())
    if any_of:
        checks.append((f"uma de {', '.join(any_of)}", bool(answered & set(any_of))))
    if expect.get("sem_ferramentas"):
        checks.append(("sem ferramentas", not result.tools_ok and not result.tools_failed))
    stage = expect.get("estado_jornada")
    if stage:
        ok = _reached(result.stage, stage) if live else result.stage == stage
        checks.append((f"etapa {stage}", ok))
    recommended = expect.get("recomendado")
    if recommended:
        checks.append(
            (f"recomendado {recommended}", result.metadata.get("recomendado") == recommended)
        )
    return checks


class Harness:
    """``root_agent`` num ``InMemoryRunner``, com o roteiro no lugar do modelo no offline."""

    def __init__(self, mode: str, mcp_url: str, ate_anomes: int) -> None:
        # Sem GOOGLE_API_USE_CLIENT_CERTIFICATE=false, o McpToolset chama
        # google.auth.default() na primeira conexão para tentar mTLS.
        os.environ.update(
            {
                "ADK_DISABLE_LOAD_DOTENV": "TRUE",
                "BUSSOLA_FAKES": "TRUE",
                "GOOGLE_API_USE_CLIENT_CERTIFICATE": "false",
                "MCP_URL": mcp_url,
                "ANCHOR_USER_ID": ANCHOR,
                "REPLAY_START_ANOMES": str(ate_anomes),
            }
        )
        sys.modules.pop("bussola_agent.agent", None)
        agent = importlib.import_module("bussola_agent.agent").root_agent
        self.logs = io.StringIO()
        configurar_logging("INFO", stream=self.logs)
        self.mode = mode
        self.scripted = ScriptedLlm() if mode == MODE_OFFLINE else None
        if self.scripted is not None:
            agent = agent.model_copy(update={"model": self.scripted})
        self.runner = InMemoryRunner(agent=agent, app_name=APP)
        self.model_versions: set[str] = set()

    def _log_events(self) -> Counter[str]:
        counter: Counter[str] = Counter()
        for line in self.logs.getvalue().splitlines():
            with contextlib.suppress(ValueError):
                item = json.loads(line)
                if isinstance(item, dict) and item.get("evento"):
                    code = item.get("erro_codigo")
                    counter[f"{item['evento']}:{code}" if code else item["evento"]] += 1
        self.logs.seek(0)
        self.logs.truncate()
        return counter

    async def run_case(self, case: Case) -> CaseResult:
        session = await self.runner.session_service.create_session(
            app_name=APP, user_id=USER, state=dict(case.state)
        )
        result = CaseResult(case)
        client_texts: list[str] = []
        case_tools_ok: set[str] = set()
        live = self.mode == MODE_LIVE
        for turn in case.turns:
            if self.scripted is not None:
                self.scripted.load(script_responses(turn.script))
            client_texts.append(turn.client)
            started = time.monotonic()
            events = [
                e
                async for e in self.runner.run_async(
                    user_id=USER,
                    session_id=session.id,
                    new_message=types.Content(role="user", parts=[types.Part(text=turn.client)]),
                    run_config=RunConfig(streaming_mode=StreamingMode.SSE),
                )
            ]
            turn_result = TurnResult(client=turn.client)
            turn_result.latency_ms = int((time.monotonic() - started) * 1000)
            self.model_versions.update(e.model_version for e in events if e.model_version)
            stored = await self.runner.session_service.get_session(
                app_name=APP, user_id=USER, session_id=session.id
            )
            state = dict(stored.state) if stored else {}
            outcomes = list(tool_outcomes(events))
            turn_result.tools_ok = [o.name for o in outcomes if o.ok]
            turn_result.tools_failed = [o.name for o in outcomes if not o.ok]
            case_tools_ok.update(turn_result.tools_ok)
            turn_result.stage = state.get(CHAVE_ESTADO_JORNADA)
            turn_result.metadata = _final_metadata(events)
            text = _final_text(events)
            turn_result.text = text
            turn_result.unavailable = text.strip() == CAPACITY_MESSAGE
            tool_evidence = evidence_from(
                [o.envelope if o.envelope is not None else o.response for o in outcomes]
            )
            session_evidence = evidence_from(
                client_texts, state.get(CHAVE_OBJETIVO), state.get(CHAVE_ATE_ANOMES)
            )
            for claim in checked_numbers(text):
                turn_result.checked += 1
                if is_supported(claim, tool_evidence):
                    turn_result.from_tools += 1
                elif is_supported(claim, session_evidence):
                    turn_result.from_session += 1
                else:
                    turn_result.unsupported.append(claim.token)
            turn_result.blocks = [b for b in BLOCKS if re.search(rf"\b{b}\b", text)]
            turn_result.cites_source = cites_source(text)
            turn_result.events = self._log_events()
            turn_result.expectations = check_expectations(
                turn.expect, turn_result, case_tools_ok, live
            )
            if self.scripted is not None:
                if self.scripted.pending or SCRIPT_EXHAUSTED in text:
                    turn_result.expectations.append(("roteiro consumido por inteiro", False))
            result.turns.append(turn_result)
        return result


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


@dataclass
class Summary:
    cases: int
    turns: int
    checked: int
    from_tools: int
    from_session: int
    unsupported: int
    expectations: int
    expectations_ok: int
    unavailable: int

    @property
    def numbers_ok(self) -> bool:
        return self.unsupported == 0


def summarize(results: Sequence[CaseResult]) -> Summary:
    turns = [t for r in results for t in r.turns]
    expectations = [ok for t in turns for _, ok in t.expectations]
    return Summary(
        cases=len(results),
        turns=len(turns),
        checked=sum(t.checked for t in turns),
        from_tools=sum(t.from_tools for t in turns),
        from_session=sum(t.from_session for t in turns),
        unsupported=sum(len(t.unsupported) for t in turns),
        expectations=len(expectations),
        expectations_ok=sum(expectations),
        unavailable=sum(t.unavailable for t in turns),
    )


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def render_section(
    mode: str, results: Sequence[CaseResult], model_versions: set[str], mcp_label: str
) -> str:
    summary = summarize(results)
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    supported = summary.checked - summary.unsupported
    pct = 100.0 * supported / summary.checked if summary.checked else 100.0
    unavailable = (
        f"; turnos sem resposta do modelo (alta demanda): {summary.unavailable}"
        if summary.unavailable
        else ""
    )
    model = (
        "roteiro de cada turno (`ScriptedLlm`)"
        if mode == MODE_OFFLINE
        else ", ".join(f"`{v}`" for v in sorted(model_versions)) or "Gemini (versão não informada)"
    )
    lines = [
        f"## Modo {mode}",
        "",
        f"- Execução: {now}; modelo: {model}; MCP: {mcp_label}.",
        f"- Casos: {summary.cases}; turnos: {summary.turns}{unavailable}.",
        f"- Números verificados: {summary.checked}; com fonte na ferramenta do turno: "
        f"{summary.from_tools}; ditos pelo cliente ou no objetivo: {summary.from_session}; "
        f"**sem fonte: {summary.unsupported}** ({pct:.0f}% com fonte).",
        f"- Expectativas cumpridas: {summary.expectations_ok} de {summary.expectations}"
        + (" (no ao vivo, relatadas sem reprovar o eval)." if mode == MODE_LIVE else "."),
        f"- Resultado: **{'aprovado' if passed(mode, summary) else 'reprovado'}**.",
        "",
        "| Caso | Turno | Ferramentas (ok) | Etapa | Números (ferr./sessão/sem fonte) "
        "| Blocos | Fonte | Expectativas não cumpridas |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        for index, turn in enumerate(result.turns, start=1):
            tools = ", ".join(turn.tools_ok) or "nenhuma"
            if turn.tools_failed:
                tools += f"; com erro: {', '.join(turn.tools_failed)}"
            numbers = f"{turn.from_tools}/{turn.from_session}/{len(turn.unsupported)}"
            if turn.unsupported:
                numbers += f" ({', '.join(turn.unsupported)})"
            missed = [name for name, ok in turn.expectations if not ok]
            if turn.unavailable:
                missed.insert(0, "modelo indisponível")
            lines.append(
                "| "
                + " | ".join(
                    _cell(v)
                    for v in (
                        result.case.id,
                        str(index),
                        tools,
                        turn.stage or "",
                        numbers,
                        ", ".join(turn.blocks) or "",
                        "sim" if turn.cites_source else "não",
                        "; ".join(missed) or "nenhuma",
                    )
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def passed(mode: str, summary: Summary) -> bool:
    if mode == MODE_LIVE:
        return summary.numbers_ok
    return summary.numbers_ok and summary.expectations_ok == summary.expectations


def write_section(path: Path, mode: str, section: str) -> None:
    """Substitui a seção do modo em ``path``, criando o arquivo se preciso."""
    start, end = f"<!-- eval:{mode}:inicio -->", f"<!-- eval:{mode}:fim -->"
    block = f"{start}\n{section}{end}\n"
    current = path.read_text("utf-8") if path.exists() else REPORT_HEADER
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.DOTALL)
    if pattern.search(current):
        updated = pattern.sub(lambda _: block, current)
    else:
        updated = current.rstrip("\n") + "\n\n" + block
    path.write_text(updated, "utf-8")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


def _live_credentials_ok() -> bool:
    vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").upper() in {"TRUE", "1"}
    return vertex or bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))


async def run_eval(
    mode: str,
    questions: Path = DEFAULT_QUESTIONS,
    output: Path | None = DEFAULT_OUTPUT,
    mcp_url: str | None = None,
    only: Sequence[str] = (),
    show: bool = False,
) -> tuple[Summary, list[CaseResult]]:
    """Roda o eval e grava a seção do modo em ``output`` (quando informado)."""
    ate_anomes, cases = load_cases(questions)
    selected = [c for c in cases if (mode == MODE_OFFLINE or c.live) and (not only or c.id in only)]
    with contextlib.ExitStack() as stack:
        if mcp_url is None:
            os.environ["MCP_USE_OIDC"] = "FALSE"  # o mock local não pede ID token
        url = mcp_url or stack.enter_context(mock_mcp())
        label = "informado em `--mcp-url`" if mcp_url else "mock do 000 com `contracts/fixtures/`"
        harness = Harness(mode, url, ate_anomes)
        results = []
        for case in selected:
            print(f"[eval] {case.id}", file=sys.stderr)
            result = await harness.run_case(case)
            results.append(result)
            if show:
                for index, turn in enumerate(result.turns, start=1):
                    print(f"\n### {case.id} / turno {index}\n> {turn.client}\n\n{turn.text}\n")
        section = render_section(mode, results, harness.model_versions, label)
    if output is not None:
        write_section(output, mode, section)
    return summarize(results), results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Eval de números do agente Bússola.")
    parser.add_argument("--modo", choices=(MODE_OFFLINE, MODE_LIVE), default=MODE_OFFLINE)
    parser.add_argument("--perguntas", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mcp-url", default=None)
    parser.add_argument("--casos", default="", help="ids separados por vírgula")
    parser.add_argument(
        "--mostrar", action="store_true", help="imprime as respostas (não vão para o arquivo)"
    )
    args = parser.parse_args(argv)
    if args.modo == MODE_LIVE and not _live_credentials_ok():
        print(
            "Modo ao vivo sem credencial: defina GOOGLE_API_KEY (com "
            "GOOGLE_GENAI_USE_VERTEXAI=FALSE) ou use a Vertex.",
            file=sys.stderr,
        )
        return 2
    only = [c.strip() for c in args.casos.split(",") if c.strip()]
    summary, _ = asyncio.run(
        run_eval(args.modo, args.perguntas, args.saida, args.mcp_url, only, args.mostrar)
    )
    print(
        f"[eval] {args.modo}: {summary.checked} números, {summary.unsupported} sem fonte; "
        f"expectativas {summary.expectations_ok}/{summary.expectations}.",
        file=sys.stderr,
    )
    return 0 if passed(args.modo, summary) else 1


if __name__ == "__main__":
    sys.exit(main())
