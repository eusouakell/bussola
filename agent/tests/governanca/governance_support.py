"""Test doubles of cycle 005: session data, fake contexts and a scripted LLM.

Nothing here calls a real model or Model Armor (decision D1): every model
answer is a static :class:`LlmResponse` written in the test.
"""

from collections.abc import AsyncGenerator, Callable, Iterable
from types import SimpleNamespace
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import PrivateAttr

from bussola_agent import callbacks, extensoes
from bussola_agent.estado import (
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_CENARIOS,
    CHAVE_ESTADO_JORNADA,
    CHAVE_OBJETIVO,
    estado_inicial,
)

ANCHOR = "36a21505-d6d4-42d3-b319-d51a133c7269"
OTHER_CUSTOMER = "31e94f2f-1463-49f9-a41a-b3f220ed976a"
ATE_ANOMES = 202506
APP = "bussola_agent"

GOAL = {
    "tipo": "reserva",
    "descricao": "Reserva de emergência",
    "valor_alvo": 30000.0,
    "prazo_meses": 24,
    "prioridade": "alta",
}
SCENARIOS = {
    "valor_alvo": 30000.0,
    "cenarios": [
        {"nome": "conservador", "aporte_mensal": 800.0, "prazo_meses": 38, "viavel": True},
        {"nome": "equilibrado", "aporte_mensal": 1250.0, "prazo_meses": 24, "viavel": True},
        {"nome": "acelerado", "aporte_mensal": 1666.67, "prazo_meses": 18, "viavel": True},
    ],
}


def journey_state(**overrides: Any) -> dict[str, Any]:
    """State of a session in ORIENTAR, with goal, scenarios and the chosen path."""
    state = estado_inicial(ANCHOR, ATE_ANOMES)
    state.update(
        {
            CHAVE_ESTADO_JORNADA: "ORIENTAR",
            CHAVE_OBJETIVO: dict(GOAL),
            CHAVE_CENARIOS: {**SCENARIOS, "cenarios": [dict(c) for c in SCENARIOS["cenarios"]]},
            CHAVE_CENARIO_ESCOLHIDO: "equilibrado",
        }
    )
    state.update(overrides)
    return state


def tool_ctx(
    state: dict[str, Any] | None = None,
    invocation_id: str = "inv-1",
    call_id: str = "call-1",
    session_id: str = "sess-1",
    events: Iterable[Any] = (),
) -> SimpleNamespace:
    """Minimal ``ToolContext``: ``state``, ids and ``session.events``."""
    return SimpleNamespace(
        state=journey_state() if state is None else state,
        invocation_id=invocation_id,
        function_call_id=call_id,
        session=SimpleNamespace(id=session_id, events=list(events)),
    )


def user_content(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part(text=text)])


def cb_ctx(
    state: dict[str, Any] | None = None,
    text: str = "",
    invocation_id: str = "inv-2",
    session_id: str = "sess-1",
    events: Iterable[Any] = (),
) -> SimpleNamespace:
    """Minimal ``CallbackContext``: ``state``, ``user_content``, ids and events."""
    return SimpleNamespace(
        state=journey_state() if state is None else state,
        user_content=user_content(text),
        invocation_id=invocation_id,
        session=SimpleNamespace(id=session_id, events=list(events)),
    )


def fake_tool(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def function_response_event(name: str, response: dict[str, Any], invocation: str = "i") -> Event:
    part = types.Part(function_response=types.FunctionResponse(name=name, response=response))
    return Event(
        author="bussola", invocation_id=invocation, content=types.Content(role="user", parts=[part])
    )


def text(value: str, partial: bool = False) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=value)]), partial=partial
    )


def call(name: str, **args: Any) -> LlmResponse:
    function_call = types.FunctionCall(name=name, args=args)
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(function_call=function_call)])
    )


def calls(*items: tuple[str, dict[str, Any]]) -> LlmResponse:
    """Several function calls in one model turn (parallel calls)."""
    parts = [types.Part(function_call=types.FunctionCall(name=n, args=a)) for n, a in items]
    return LlmResponse(content=types.Content(role="model", parts=parts))


Step = LlmResponse | list[LlmResponse] | Callable[[LlmRequest], LlmResponse | list[LlmResponse]]


class ScriptedLlm(BaseLlm):
    """Fake LLM: each call pops the next step of the script (no network, no model).

    A step is a response, a list of responses (partials then the final one,
    for streaming) or a function of the request. The requests are kept for
    assertions (instructions appended by callbacks, safety settings).
    """

    model: str = "roteiro"
    _steps: list[Step] = PrivateAttr(default_factory=list)
    _requests: list[LlmRequest] = PrivateAttr(default_factory=list)

    def script(self, *steps: Step) -> "ScriptedLlm":
        self._steps.extend(steps)
        return self

    @property
    def requests(self) -> list[LlmRequest]:
        return self._requests

    @property
    def pending_steps(self) -> int:
        return len(self._steps)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self._requests.append(llm_request.model_copy(deep=True))
        if not self._steps:
            raise AssertionError("O roteiro do LLM falso acabou.")
        step = self._steps.pop(0)
        produced = step(llm_request) if callable(step) else step
        for response in produced if isinstance(produced, list) else [produced]:
            if response.partial and not stream:
                continue
            yield response.model_copy(deep=True)


def system_text(request: LlmRequest) -> str:
    instruction = request.config.system_instruction if request.config else None
    if isinstance(instruction, str):
        return instruction
    parts = getattr(instruction, "parts", None) or []
    return "\n".join(p.text or "" for p in parts)


class Conversation:
    """Runs turns of an agent with the registered 005 extensions and a scripted LLM."""

    def __init__(self, llm: ScriptedLlm, extra_tools: Iterable[Any] = ()) -> None:
        self.llm = llm
        self.agent = Agent(
            name="bussola",
            model=llm,
            instruction="Você é o Bússola.\n\n" + extensoes.instrucoes(),
            tools=[*extra_tools, *extensoes.ferramentas()],
            before_model_callback=callbacks.before_model,
            after_model_callback=callbacks.after_model,
            before_tool_callback=callbacks.before_tool,
            after_tool_callback=callbacks.after_tool,
        )
        self.runner = InMemoryRunner(agent=self.agent, app_name=APP)
        self.session_id: str | None = None

    async def start(self, state: dict[str, Any] | None = None) -> str:
        session = await self.runner.session_service.create_session(
            app_name=APP, user_id="u", state=journey_state() if state is None else state
        )
        self.session_id = session.id
        return session.id

    async def say(self, message: str, sse: bool = False) -> list[Event]:
        assert self.session_id is not None
        config = RunConfig(streaming_mode=StreamingMode.SSE if sse else StreamingMode.NONE)
        return [
            event
            async for event in self.runner.run_async(
                user_id="u",
                session_id=self.session_id,
                new_message=user_content(message),
                run_config=config,
            )
        ]

    async def state(self) -> dict[str, Any]:
        session = await self.runner.session_service.get_session(
            app_name=APP, user_id="u", session_id=self.session_id
        )
        return dict(session.state)


def final_text(events: list[Event]) -> str:
    final = [e for e in events if not e.partial and e.content and e.content.parts]
    return "".join(p.text or "" for p in final[-1].content.parts)


def bussola_metadata(event: Event) -> dict[str, Any]:
    return dict((event.custom_metadata or {}).get("bussola") or {})


def tool_responses(events: list[Event], name: str) -> list[dict[str, Any]]:
    return [
        r.response
        for e in events
        for r in e.get_function_responses()
        if r.name == name and r.response is not None
    ]
