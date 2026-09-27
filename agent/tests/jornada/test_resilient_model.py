"""Erro de capacidade do Gemini (429/5xx) não derruba o turno (``resilient_model``).

Reproduz a falha do Cloud Run: com ``/run_sse`` o modelo é chamado com
``stream=True``; o 429 do primeiro Flash caía para o segundo, e o 503 levantado
pelo streaming do segundo depois do primeiro pedaço matava o turno.

Os turnos rodam pelo ``InMemoryRunner`` do ADK em ``StreamingMode.SSE``, com
modelos roteirizados (``BaseLlm`` fake) ou com o ``Gemini`` real sobre um
cliente genai fake. Nada acessa a rede.
"""

from collections.abc import AsyncGenerator, Callable
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.agents import Agent, RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.events import Event
from google.adk.models import BaseLlm, FallbackModel, Gemini, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import errors, types
from pydantic import Field

from bussola_agent import resilient_model
from bussola_agent.resilient_model import (
    CAPACITY_MESSAGE,
    NonStreamingModel,
    build_fallback_chain,
    capacity_error_response,
    capacity_status,
)

APP = "teste_resiliencia"
USUARIO = "fernando"


def _erro(status: int) -> errors.APIError:
    corpo = {"error": {"code": status, "message": "high demand", "status": "UNAVAILABLE"}}
    return errors.ServerError(status, corpo) if status >= 500 else errors.ClientError(status, corpo)


def _texto(texto: str, partial: bool | None = None) -> LlmResponse:
    conteudo = types.Content(role="model", parts=[types.Part(text=texto)])
    return LlmResponse(content=conteudo, partial=partial)


class ScriptedModel(BaseLlm):
    """Modelo fake: falha com ``fail_status`` ou responde ``text``.

    ``fail_mid_stream`` imita o Gemini em ``stream=True``: entrega um pedaço
    parcial e só então levanta o erro. Sem streaming, a falha vem antes de
    qualquer resposta, como no ``generate_content`` do genai.
    """

    text: str = "Resposta completa."
    fail_status: int | None = None
    fail_mid_stream: bool = False
    streams: list[bool] = Field(default_factory=list)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        self.streams.append(stream)
        if self.fail_status is not None:
            if stream and self.fail_mid_stream:
                yield _texto("Começando a ", partial=True)
            raise _erro(self.fail_status)
        if stream:
            yield _texto(self.text[:5], partial=True)
        yield _texto(self.text)


def _agente(modelo: BaseLlm) -> Agent:
    return Agent(
        name="agente_teste",
        model=modelo,
        instruction="Responda em pt-BR.",
        on_model_error_callback=capacity_error_response,
    )


async def _turno(agente: Agent) -> list[Event]:
    runner = InMemoryRunner(agent=agente, app_name=APP)
    sessao = await runner.session_service.create_session(app_name=APP, user_id=USUARIO)
    mensagem = types.Content(role="user", parts=[types.Part(text="Como foi meu último mês?")])
    return [
        evento
        async for evento in runner.run_async(
            user_id=USUARIO,
            session_id=sessao.id,
            new_message=mensagem,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    ]


def _texto_final(eventos: list[Event]) -> str:
    finais = [e for e in eventos if not e.partial and e.content and e.content.parts]
    assert finais, "o turno terminou sem evento final"
    return "".join(p.text or "" for p in finais[-1].content.parts)


# ---------------------------------------------------------------------------
# Modelos roteirizados
# ---------------------------------------------------------------------------


async def test_sem_o_embrulho_o_503_no_meio_do_streaming_derruba_o_turno() -> None:
    """Premissa do bug: o ``FallbackModel`` sozinho relança depois do 1º pedaço."""
    cadeia = FallbackModel(
        models=[
            ScriptedModel(model="flash-a", fail_status=429),
            ScriptedModel(model="flash-b", fail_status=503, fail_mid_stream=True),
            ScriptedModel(model="flash-c"),
        ]
    )
    agente = Agent(name="agente_teste", model=cadeia, instruction="Responda.")
    with pytest.raises(errors.ServerError):
        await _turno(agente)


async def test_503_no_meio_do_streaming_cai_para_o_proximo_modelo() -> None:
    a = ScriptedModel(model="flash-a", fail_status=429)
    b = ScriptedModel(model="flash-b", fail_status=503, fail_mid_stream=True)
    c = ScriptedModel(model="flash-c", text="Seu mês fechou com sobra.")

    eventos = await _turno(_agente(build_fallback_chain([a, b, c])))

    assert _texto_final(eventos) == "Seu mês fechou com sobra."
    assert (a.streams, b.streams, c.streams) == ([False], [False], [False])
    assert not any(e.partial for e in eventos)


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_erro_de_capacidade_antes_da_resposta_cai_para_o_proximo(status: int) -> None:
    a = ScriptedModel(model="flash-a", fail_status=status)
    b = ScriptedModel(model="flash-b", text="Pronto.")
    eventos = await _turno(_agente(build_fallback_chain([a, b])))
    assert _texto_final(eventos) == "Pronto."


async def test_cadeia_esgotada_vira_mensagem_amigavel_sem_detalhe_interno() -> None:
    cadeia = build_fallback_chain(
        [
            ScriptedModel(model="flash-a", fail_status=429),
            ScriptedModel(model="flash-b", fail_status=503, fail_mid_stream=True),
        ]
    )
    eventos = await _turno(_agente(cadeia))

    final = _texto_final(eventos)
    assert final == CAPACITY_MESSAGE
    for interno in ("503", "429", "UNAVAILABLE", "flash-", "high demand", "Gemini"):
        assert interno not in final


async def test_erro_que_nao_e_de_capacidade_nao_e_mascarado() -> None:
    cadeia = build_fallback_chain(
        [ScriptedModel(model="flash-a", fail_status=400), ScriptedModel(model="flash-b")]
    )
    with pytest.raises(errors.ClientError):
        await _turno(_agente(cadeia))


async def test_resposta_amigavel_registra_log_sem_mensagem_do_provedor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    capsys.readouterr()
    contexto = SimpleNamespace(session=SimpleNamespace(id="sessao-1"))
    resposta = capacity_error_response(contexto, None, _erro(503))
    assert resposta is not None and resposta.content.parts[0].text == CAPACITY_MESSAGE
    saida = capsys.readouterr().out
    assert '"evento": "modelo_sem_capacidade"' in saida
    assert '"erro_codigo": "HTTP_503"' in saida
    assert '"excecao": "ServerError"' in saida
    assert "high demand" not in saida and "UNAVAILABLE" not in saida


@pytest.mark.parametrize(
    ("erro", "esperado"),
    [
        (_erro(429), 429),
        (_erro(503), 503),
        (_erro(504), 504),
        (_erro(400), None),
        (_erro(404), None),
        (RuntimeError("falha local"), None),
        (SimpleNamespace(status_code=502), 502),
    ],
)
def test_capacity_status(erro: Any, esperado: int | None) -> None:
    assert capacity_status(erro) == esperado


def test_embrulho_herda_nome_e_capacidades_do_delegado() -> None:
    gemini = Gemini(model="gemini-3.8-flash")
    embrulho = NonStreamingModel(delegate=gemini)
    assert embrulho.model == "gemini-3.8-flash"
    assert embrulho.capabilities == gemini.capabilities
    cadeia = build_fallback_chain([gemini])
    assert cadeia.model == "gemini-3.8-flash"
    assert {429, 503} <= cadeia.retriable_status_codes
    assert resilient_model.CAPACITY_STATUS_CODES == FallbackModel.DEFAULT_STATUS_CODES


async def test_embrulho_so_entrega_depois_que_o_delegado_termina() -> None:
    """Uma falha do delegado depois de uma resposta ainda sai antes da 1ª entrega."""

    class DuasPartesDepoisFalha(BaseLlm):
        async def generate_content_async(
            self, llm_request: LlmRequest, stream: bool = False
        ) -> AsyncGenerator[LlmResponse, None]:
            yield _texto("parte")
            raise _erro(503)

    entregues: list[LlmResponse] = []
    embrulho = NonStreamingModel(delegate=DuasPartesDepoisFalha(model="flash-x"))
    with pytest.raises(errors.ServerError):
        async for resposta in embrulho.generate_content_async(LlmRequest(), stream=True):
            entregues.append(resposta)
    assert entregues == []


# ---------------------------------------------------------------------------
# Gemini real do ADK sobre um cliente genai fake (o caminho de produção)
# ---------------------------------------------------------------------------


def _resposta_genai(texto: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=texto)]),
                finish_reason=types.FinishReason.STOP,
            )
        ]
    )


class _ModelosGenaiFake:
    """``client.aio.models`` com o comportamento visto em produção por modelo."""

    def __init__(self, nome: str, chamadas: list[tuple[str, bool]]) -> None:
        self.nome = nome
        self.chamadas = chamadas

    def _falha(self) -> errors.APIError | None:
        return {"gemini-3.8-flash": _erro(429), "gemini-3.7-flash": _erro(503)}.get(self.nome)

    async def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
        self.chamadas.append((model, False))
        if (erro := self._falha()) is not None:
            raise erro
        return _resposta_genai(f"Resposta do {model}.")

    async def generate_content_stream(self, *, model: str, contents: Any, config: Any) -> Any:
        self.chamadas.append((model, True))
        erro = self._falha()

        async def pedacos() -> AsyncGenerator[types.GenerateContentResponse, None]:
            if erro is not None and erro.code == 429:
                raise erro
            yield _resposta_genai("Olá, ")
            if erro is not None:
                raise erro  # 503 no meio do streaming
            yield _resposta_genai("tudo certo.")

        return pedacos()


@pytest.fixture
def genai_fake(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, bool]]:
    chamadas: list[tuple[str, bool]] = []
    clientes: dict[str, Any] = {}

    def cliente(self: Gemini) -> Any:
        if self.model not in clientes:
            modelos = _ModelosGenaiFake(self.model, chamadas)
            aio = SimpleNamespace(models=modelos)
            clientes[self.model] = SimpleNamespace(vertexai=False, aio=aio)
        return clientes[self.model]

    monkeypatch.setattr(Gemini, "api_client", property(cliente))
    return chamadas


def _cadeia_flash(montar: Callable[[list[BaseLlm]], BaseLlm]) -> BaseLlm:
    nomes = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash")
    return montar([Gemini(model=n) for n in nomes])


async def test_producao_sem_embrulho_reproduz_o_turno_derrubado(
    genai_fake: list[tuple[str, bool]],
) -> None:
    cadeia = _cadeia_flash(lambda modelos: FallbackModel(models=modelos))
    with pytest.raises(errors.ServerError):
        await _turno(Agent(name="agente_teste", model=cadeia, instruction="Responda."))
    assert genai_fake == [("gemini-3.8-flash", True), ("gemini-3.7-flash", True)]


async def test_producao_com_a_cadeia_resiliente_responde_pelo_terceiro_flash(
    genai_fake: list[tuple[str, bool]],
) -> None:
    eventos = await _turno(_agente(_cadeia_flash(build_fallback_chain)))
    assert _texto_final(eventos) == "Resposta do gemini-3.5-flash."
    assert genai_fake == [
        ("gemini-3.8-flash", False),
        ("gemini-3.7-flash", False),
        ("gemini-3.5-flash", False),
    ]
