"""Cadeia de modelos que sobrevive a erro de capacidade do Gemini (429/5xx).

Falha vista no Cloud Run: o front chama ``/run_sse``, então o fluxo do ADK
chama o modelo com ``stream=True``. O ``FallbackModel`` só troca de modelo
antes da primeira resposta entregue, e as ``HttpRetryOptions`` do genai só
repetem a requisição HTTP. Um ``503 UNAVAILABLE`` levantado pelo gerador do
streaming depois do primeiro pedaço derrubava o turno inteiro, mesmo com outro
modelo livre para responder.

Desenho:

- :class:`NonStreamingModel` embrulha cada modelo da cadeia, sempre o chama com
  ``stream=False`` e só entrega a resposta completa. Toda falha acontece antes
  da primeira entrega, onde as ``retry_options`` do modelo (mesmo modelo) e o
  ``FallbackModel`` (próximo modelo) já atuam. As respostas são curtas, então
  perder o streaming por token é aceitável: o front fecha a mensagem no evento
  sem ``partial`` (``specs/008-front-web/contracts/eventos-agente.md`` §2).
- :func:`capacity_error_response` é o ``on_model_error_callback`` do agente:
  quando todos os modelos se esgotam por capacidade, troca o erro por uma
  mensagem em pt-BR, sem detalhe interno.
"""

from collections.abc import AsyncGenerator, AsyncIterator, Sequence
from contextlib import aclosing, asynccontextmanager
from typing import Any

from google.adk.models import BaseLlm, FallbackModel, LlmRequest, LlmResponse
from google.genai import errors, types
from pydantic import model_validator

from bussola_agent.logging_json import obter_logger

CAPACITY_STATUS_CODES: frozenset[int] = FallbackModel.DEFAULT_STATUS_CODES
"""429 e 5xx: os mesmos códigos com que o ``FallbackModel`` passa ao próximo modelo."""

CAPACITY_MESSAGE = "O serviço de IA está com alta demanda agora. Tente de novo em alguns segundos."
"""Texto ao cliente quando nenhum modelo da cadeia conseguiu responder."""

_log = obter_logger(__name__)


class NonStreamingModel(BaseLlm):
    """Chama ``delegate`` sempre com ``stream=False`` e entrega a resposta completa.

    As respostas do delegado são juntadas antes da primeira entrega. Assim uma
    falha no meio da geração nunca chega depois de uma resposta parcial, e o
    ``FallbackModel`` continua livre para tentar o próximo modelo.
    """

    delegate: BaseLlm
    model: str = ""
    """Nome do delegado; o ``FallbackModel`` o copia para ``LlmRequest.model``."""

    @model_validator(mode="after")
    def _model_name_from_delegate(self) -> "NonStreamingModel":
        self.model = self.delegate.model
        return self

    @property
    def capabilities(self) -> Any:
        return self.delegate.capabilities

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        del stream  # sempre completa: ver a docstring do módulo
        async with aclosing(self.delegate.generate_content_async(llm_request, False)) as gerador:
            respostas = [resposta async for resposta in gerador]
        for resposta in respostas:
            yield resposta

    @asynccontextmanager
    async def connect(self, llm_request: LlmRequest) -> AsyncIterator[Any]:
        async with self.delegate.connect(llm_request) as conexao:
            yield conexao


def build_fallback_chain(models: Sequence[BaseLlm]) -> FallbackModel:
    """``FallbackModel`` com cada modelo, na ordem, embrulhado em :class:`NonStreamingModel`."""
    return FallbackModel(models=[NonStreamingModel(delegate=m) for m in models])


def capacity_status(error: BaseException) -> int | None:
    """Status HTTP do erro quando ele é de capacidade (429 ou 5xx); senão ``None``."""
    status = error.code if isinstance(error, errors.APIError) else None
    if status is None:
        candidato = getattr(error, "status_code", None)
        status = candidato if isinstance(candidato, int) else None
    return status if status in CAPACITY_STATUS_CODES else None


def capacity_error_response(
    callback_context: Any, llm_request: Any, error: Exception
) -> LlmResponse | None:
    """``on_model_error_callback``: erro de capacidade esgotado vira mensagem ao cliente.

    Outros erros devolvem ``None`` e seguem para o ADK, para não esconder
    falhas de configuração. O log leva só o código HTTP e o nome da classe.
    """
    del llm_request
    status = capacity_status(error)
    if status is None:
        return None
    sessao = getattr(callback_context, "session", None)
    _log.warning(
        "Nenhum modelo da cadeia respondeu por falta de capacidade.",
        exc_info=error,
        extra={
            "evento": "modelo_sem_capacidade",
            "erro_codigo": f"HTTP_{status}",
            "session_id": getattr(sessao, "id", None),
        },
    )
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=CAPACITY_MESSAGE)])
    )
