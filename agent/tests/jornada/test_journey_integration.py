"""Jornada roteirizada OBJETIVO → ENTENDER → ANTECIPAR → ORIENTAR → AGIR (AC-07).

O ``root_agent`` real (ferramentas, instrução, callbacks) roda num
``InMemoryRunner`` em modo SSE, falando MCP com o mock do 000 em subprocesso
(``127.0.0.1``, porta livre, ``contracts/fixtures/``). Só o modelo é trocado
por um roteiro determinístico (:class:`ScriptedLlm`): nenhuma chamada ao
Gemini, nenhum acesso fora de loopback.
"""

import asyncio
import contextlib
import importlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import PrivateAttr

import bussola_agent
from bussola_agent import callbacks, escopo
from bussola_agent.jornada.tools import registrar_objetivo

ROOT = Path(__file__).resolve().parents[3]
MCP_DIR = ROOT / "mcp_server"
FIXTURES_DIR = ROOT / "contracts" / "fixtures"
SERVER_WAIT_S = 90.0
APP = "bussola_agent"
ANCHOR = "36a21505-d6d4-42d3-b319-d51a133c7269"
CONTROL = "31e94f2f-1463-49f9-a41a-b3f220ed976a"


# ---------------------------------------------------------------------------
# Mock MCP em subprocesso
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _tail(path: Path, lines: int = 30) -> str:
    try:
        return "\n".join(path.read_text("utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(sem saída)"


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


@pytest.fixture(scope="module")
def mcp_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """URL ``/mcp`` do mock do 000 servindo ``contracts/fixtures/``."""
    uv = shutil.which("uv")
    if uv is None or not (MCP_DIR / "bussola_mcp" / "server.py").is_file():
        pytest.skip("mock MCP indisponível: falta o uv ou mcp_server/bussola_mcp/server.py")
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["PYTHONUNBUFFERED"] = "1"
    log = tmp_path_factory.mktemp("mock_jornada") / "mock.log"
    command = [
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
    ]
    with log.open("wb") as out:
        process = subprocess.Popen(
            command,
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
                pytest.fail(f"O mock MCP encerrou antes de abrir a porta:\n{_tail(log)}")
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                break
            except OSError:
                if time.monotonic() > deadline:
                    pytest.fail(f"O mock MCP não abriu a porta a tempo:\n{_tail(log)}")
                time.sleep(0.1)
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        _stop(process)


# ---------------------------------------------------------------------------
# Modelo roteirizado
# ---------------------------------------------------------------------------


def call(*calls: tuple[str, dict[str, Any]]) -> LlmResponse:
    """Resposta do modelo com uma ou mais chamadas de ferramenta (paralelas)."""
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in calls]
    return LlmResponse(content=types.Content(role="model", parts=parts))


def text(value: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=value)]))


class ScriptedLlm(BaseLlm):
    """Devolve as respostas do roteiro em ordem e guarda cada ``LlmRequest``.

    Em streaming, o texto final sai antes como um parcial, como no SSE real.
    """

    model: str = "roteiro"
    _script: list[LlmResponse] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    def load(self, *responses: LlmResponse) -> None:
        self._script.extend(responses)

    @property
    def requests(self) -> list[LlmRequest]:
        return self._requests

    @property
    def pending(self) -> int:
        return len(self._script)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request)
        response = self._script.pop(0)
        parts = response.content.parts if response.content else []
        if stream and parts and parts[0].text:
            yield LlmResponse(
                content=types.Content(role="model", parts=[types.Part(text=parts[0].text[:8])]),
                partial=True,
            )
        yield response


def system_text(request: LlmRequest) -> str:
    instruction = request.config.system_instruction if request.config else None
    if isinstance(instruction, str):
        return instruction
    parts = getattr(instruction, "parts", None) or []
    return "".join(p.text or "" for p in parts)


# ---------------------------------------------------------------------------
# Agente real com o modelo roteirizado
# ---------------------------------------------------------------------------


class Journey:
    """Uma sessão do ``root_agent`` no ``InMemoryRunner``."""

    def __init__(self, agent: Any, model: ScriptedLlm) -> None:
        self.model = model
        self.runner = InMemoryRunner(agent=agent, app_name=APP)
        self.session_id = ""

    async def start(self) -> None:
        session = await self.runner.session_service.create_session(app_name=APP, user_id="u")
        self.session_id = session.id

    async def turn(self, message: str, *responses: LlmResponse) -> list[Event]:
        self.model.load(*responses)
        content = types.Content(role="user", parts=[types.Part(text=message)])
        events = [
            e
            async for e in self.runner.run_async(
                user_id="u",
                session_id=self.session_id,
                new_message=content,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            )
        ]
        assert self.model.pending == 0
        return events

    async def state(self) -> dict[str, Any]:
        session = await self.runner.session_service.get_session(
            app_name=APP, user_id="u", session_id=self.session_id
        )
        assert session is not None
        return dict(session.state)


@pytest.fixture
def journey(mcp_url: str, monkeypatch: pytest.MonkeyPatch) -> Callable[[], Journey]:
    monkeypatch.setenv("ADK_DISABLE_LOAD_DOTENV", "TRUE")
    monkeypatch.setenv("MCP_URL", mcp_url)
    for key in ("BUSSOLA_MODEL", "ANCHOR_USER_ID", "REPLAY_START_ANOMES"):
        monkeypatch.delenv(key, raising=False)

    def build() -> Journey:
        monkeypatch.delitem(sys.modules, "bussola_agent.agent", raising=False)
        monkeypatch.delattr(bussola_agent, "agent", raising=False)
        agent = importlib.import_module("bussola_agent.agent").root_agent
        model = ScriptedLlm()
        return Journey(agent.model_copy(update={"model": model}), model)

    return build


def final_message(events: list[Event]) -> Event:
    finals = [e for e in events if e.author == "bussola" and not e.partial and e.content]
    last = finals[-1]
    assert last.content is not None and last.content.parts and last.content.parts[0].text
    return last


def sent_to_front(event: Event) -> dict[str, Any]:
    """Como o front recebe o evento (alias em camelCase)."""
    return json.loads(event.model_dump_json(by_alias=True, exclude_none=True))


def json_logs(output: str) -> list[dict[str, Any]]:
    logs = []
    for line in output.splitlines():
        with contextlib.suppress(ValueError):
            item = json.loads(line)
            if isinstance(item, dict):
                logs.append(item)
    return logs


def response_of(events: list[Event], tool: str) -> dict[str, Any]:
    for event in events:
        for response in event.get_function_responses():
            if response.name == tool:
                return response.response or {}
    raise AssertionError(f"{tool} não respondeu")


# ---------------------------------------------------------------------------
# Jornada completa
# ---------------------------------------------------------------------------


async def test_demo_journey_from_goal_to_action(
    journey: Callable[[], Journey], capsys: pytest.CaptureFixture[str]
) -> None:
    j = journey()
    await j.start()
    capsys.readouterr()

    # OBJETIVO → ENTENDER: registrar_objetivo com valor e prazo.
    events = await j.turn(
        "Quero juntar R$ 30 mil em 2 anos para o meu primeiro apartamento",
        call(
            (
                "registrar_objetivo",
                {
                    "tipo": "imovel",
                    "descricao": "Primeiro apartamento",
                    "valor_alvo": 30000,
                    "prazo_meses": 24,
                },
            )
        ),
        text("Anotei seu objetivo: R$ 30.000,00 em 24 meses. Vou olhar seus dados."),
    )
    state = await j.state()
    assert state["estado_jornada"] == "ENTENDER"
    assert state["objetivo"]["valor_alvo"] == 30000.0
    assert state["objetivo"]["prazo_meses"] == 24
    first = final_message(events)
    assert first.content.parts[0].text.endswith("Vou olhar seus dados.")  # sem rodapé
    assert sent_to_front(first)["customMetadata"]["bussola"] == {
        "respostas_rapidas": [
            "Quanto consigo guardar por mês?",
            "Como está meu perfil financeiro?",
            "Tenho parcelas em aberto?",
        ]
    }
    assert "Etapa atual da jornada: OBJETIVO" in system_text(j.model.requests[0])
    assert "Etapa atual da jornada: ENTENDER" in system_text(j.model.requests[1])
    names = set(j.model.requests[0].tools_dict)
    assert {"perfil_financeiro", "comparar_cenarios", "registrar_objetivo"} <= names

    # ENTENDER → ANTECIPAR: perfil e capacidade em paralelo, com escopo errado do modelo.
    wrong_scope = {"id_usuario": CONTROL, "ate_anomes": 202512}
    events = await j.turn(
        "Pode olhar meus dados",
        call(("perfil_financeiro", wrong_scope), ("capacidade_poupanca", wrong_scope)),
        text("**Diagnóstico**\nSua sobra média é de R$ 1.901,47 por mês."),
    )
    # O controle receberia DADOS_INSUFICIENTES: dados vieram do âncora em 202506.
    profile = response_of(events, "perfil_financeiro")["structuredContent"]
    assert profile["dados"]["sobra_media"] == 1901.47
    assert profile["fonte"]["periodo"] == {"inicio": 202501, "fim": 202506}
    state = await j.state()
    assert state["id_usuario"] == ANCHOR and state["ate_anomes"] == 202506
    assert state["estado_jornada"] == "ANTECIPAR"
    assert {f["ferramenta"] for f in state["ultimas_fontes"]} == {
        "perfil_financeiro",
        "capacidade_poupanca",
    }
    second = final_message(events)
    assert second.content.parts[-1].text == (
        "**Diagnóstico**\nSua sobra média é de R$ 1.901,47 por mês.\n\n"
        "Fonte: perfil financeiro e capacidade de poupança, jan–jun/2025."
    )
    assert sent_to_front(second)["customMetadata"]["bussola"] == {
        "tag": "diagnostico",
        "respostas_rapidas": [
            "Me mostra os caminhos",
            "Onde posso economizar?",
            "Tenho parcelas em aberto?",
        ],
    }

    # ANTECIPAR → ORIENTAR: comparar_cenarios sem escopo (o callback completa).
    events = await j.turn(
        "Me mostra os caminhos",
        call(("comparar_cenarios", {"valor_alvo": 30000, "prazo_meses": 24})),
        text(
            "**Simulação**\nAcelerado: R$ 1.681,15 por mês em 18 meses.\n"
            "**Recomendação**\nO caminho acelerado cabe na sua sobra.\n"
            "Fonte: comparação de cenários, jan–jun/2025."
        ),
    )
    state = await j.state()
    assert state["estado_jornada"] == "ORIENTAR"
    assert [c["nome"] for c in state["cenarios"]["cenarios"]] == [
        "conservador",
        "equilibrado",
        "acelerado",
    ]
    assert sent_to_front(final_message(events))["customMetadata"]["bussola"] == {
        "tag": "recomendacao",
        "recomendado": "acelerado",
        "respostas_rapidas": [
            "Quero o caminho acelerado",
            "Quero outro caminho",
            "Onde posso economizar?",
        ],
    }

    # ORIENTAR → AGIR: escolher_cenario.
    events = await j.turn(
        "Quero o caminho acelerado",
        call(("escolher_cenario", {"nome": "acelerado"})),
        text("Caminho acelerado escolhido. Agora preparo o plano com a sua autorização."),
    )
    state = await j.state()
    assert state["estado_jornada"] == "AGIR"
    assert state["cenario_escolhido"] == "acelerado"
    assert sent_to_front(final_message(events))["customMetadata"]["bussola"] == {"tag": "acao"}

    logs = json_logs(capsys.readouterr().out)
    changes = [log["estado_jornada"] for log in logs if log.get("evento") == "estado_alterado"]
    assert changes == ["ENTENDER", "ANTECIPAR", "ORIENTAR", "AGIR"]
    overridden = [log for log in logs if log.get("evento") == "escopo_sobrescrito"]
    assert {log["erro_codigo"] for log in overridden} == {
        "ID_USUARIO_DIVERGENTE",
        "ATE_ANOMES_DIVERGENTE",
    }
    checks = [log["erro_codigo"] for log in logs if log.get("evento") == "numero_sem_fonte"]
    assert checks == ["FONTE_NAO_CITADA"]  # só o turno do diagnóstico, que ganhou rodapé
    dumped = json.dumps(logs)
    assert CONTROL not in dumped
    assert "1.901,47" not in dumped and "apartamento" not in dumped


async def test_invented_number_is_logged_without_echo(
    journey: Callable[[], Journey], capsys: pytest.CaptureFixture[str]
) -> None:
    j = journey()
    await j.start()
    capsys.readouterr()
    events = await j.turn(
        "Como estão minhas finanças?",
        call(("perfil_financeiro", {})),
        text("Você consegue guardar R$ 2.345,67 por mês. Fonte: perfil financeiro."),
    )
    assert final_message(events).content.parts[-1].text.endswith("Fonte: perfil financeiro.")
    logs = json_logs(capsys.readouterr().out)
    [warning] = [log for log in logs if log.get("evento") == "numero_sem_fonte"]
    assert warning["erro_codigo"] == "NUMERO_DIVERGENTE"
    assert "2.345" not in json.dumps(logs) and "2345" not in json.dumps(logs)
    state = await j.state()
    assert state["estado_jornada"] == "OBJETIVO"  # sem objetivo, dados não avançam


# ---------------------------------------------------------------------------
# Chamadas paralelas terminando fora de ordem (D-11)
# ---------------------------------------------------------------------------
# Cada chamada paralela grava num delta próprio e ``adicionar_fonte`` reatribui
# a lista. O ADK 2.10 reaplica a última escrita de listas no evento juntado
# (``_apply_latest_state_writes``); sem isso a fonte de uma das chamadas
# sumiria e o objetivo registrado depois não encadearia ANTECIPAR.


def _envelope(name: str) -> dict[str, Any]:
    return {
        "dados": {"sobra_media": 1901.47},
        "fonte": {
            "ferramenta": name,
            "tabelas": ["bussola_dados.perfil_mensal"],
            "periodo": {"inicio": 202501, "fim": 202506},
        },
        "avisos": [],
    }


async def perfil_financeiro(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
    """Dublê lento: termina depois da capacidade, embora chamado antes."""
    await asyncio.sleep(0.2)
    return _envelope("perfil_financeiro")


async def capacidade_poupanca(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
    """Dublê rápido."""
    return _envelope("capacidade_poupanca")


def _race_journey() -> Journey:
    callbacks.registrar("before_tool", escopo.enforce_scope, escopo.ORDER)
    callbacks.registrar("after_tool", escopo.record_tool_result, escopo.ORDER)
    model = ScriptedLlm()
    agent = Agent(
        name="bussola",
        model=model,
        instruction="Etapa: {estado_jornada?}",
        tools=[perfil_financeiro, capacidade_poupanca, registrar_objetivo],
        before_agent_callback=escopo.initialize_session,
        before_tool_callback=callbacks.before_tool,
        after_tool_callback=callbacks.after_tool,
        after_model_callback=callbacks.after_model,
    )
    return Journey(agent, model)


async def test_parallel_calls_keep_every_source(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("ANCHOR_USER_ID", "REPLAY_START_ANOMES"):
        monkeypatch.delenv(key, raising=False)
    j = _race_journey()
    await j.start()

    # Dados antes do objetivo: perfil (lento) e capacidade (rápida) em paralelo.
    events = await j.turn(
        "Como estão minhas finanças?",
        call(("perfil_financeiro", {}), ("capacidade_poupanca", {})),
        text("Sua sobra média é de R$ 1.901,47 por mês. Fonte: perfil financeiro."),
    )
    [merged] = [e for e in events if e.get_function_responses()]
    # A capacidade termina primeiro; o delta juntado guarda as duas, na ordem de término.
    assert [f["ferramenta"] for f in merged.actions.state_delta["ultimas_fontes"]] == [
        "capacidade_poupanca",
        "perfil_financeiro",
    ], "o ADK voltou a perder escritas paralelas em listas: rever ultimas_fontes (D-11)"
    state = await j.state()
    assert len(state["ultimas_fontes"]) == 2
    assert state["estado_jornada"] == "OBJETIVO"

    # O objetivo completo encadeia ENTENDER → ANTECIPAR com as duas fontes na sessão.
    await j.turn(
        "Quero juntar R$ 30 mil em 2 anos",
        call(
            (
                "registrar_objetivo",
                {
                    "tipo": "imovel",
                    "descricao": "Apartamento",
                    "valor_alvo": 30000,
                    "prazo_meses": 24,
                },
            )
        ),
        text("Anotei seu objetivo."),
    )
    assert (await j.state())["estado_jornada"] == "ANTECIPAR"
