"""Porta de embedding do RAG e o adaptador Gemini (``google-genai``).

O indexador embute os trechos com ``RETRIEVAL_DOCUMENT``, e o
``BuscadorNumpy`` embute só a pergunta, com ``RETRIEVAL_QUERY``. Os testes
injetam um :class:`Embedder` falso e nunca chamam a rede.

O adaptador usa o ``genai.Client()`` padrão, que lê o ambiente:

- **Plano A (Vertex):** ``GOOGLE_GENAI_USE_VERTEXAI=TRUE``,
  ``GOOGLE_CLOUD_PROJECT`` e ``GOOGLE_CLOUD_LOCATION``.
- **Plano B (Gemini API):** ``GOOGLE_GENAI_USE_VERTEXAI=FALSE`` e
  ``GOOGLE_API_KEY``.

A chave nunca é lida, registrada ou exibida por este módulo.
"""

import time
from collections.abc import Sequence
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np

from bussola_mcp import config
from bussola_mcp.dominio.interfaces import SearcherUnavailableError

TaskType = Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
TASK_DOCUMENT: TaskType = "RETRIEVAL_DOCUMENT"
TASK_QUERY: TaskType = "RETRIEVAL_QUERY"

DEFAULT_MODEL = config.MODELO_EMBEDDING_PADRAO
DEFAULT_DIMENSION = config.DIMENSAO_EMBEDDING_PADRAO
_BATCH_VERTEX = 1  # no Vertex, o gemini-embedding-001 aceita um texto por chamada
_BATCH_API = 20


class EmbeddingUnavailableError(SearcherUnavailableError):
    """O serviço de embedding falhou. A mensagem é genérica, sem detalhe do provedor.

    Especialização de
    :class:`~bussola_mcp.dominio.interfaces.SearcherUnavailableError` (a falha da
    porta ``BuscadorContexto``), para a ferramenta tratá-la sem importar este módulo.
    """

    def __init__(self, cause: str | None = None) -> None:
        super().__init__("serviço de embedding indisponível no momento")
        # Só o nome da classe da falha original (para o log do indexador), nunca a mensagem.
        self.cause = cause


@runtime_checkable
class Embedder(Protocol):
    """Gera embeddings ``float32`` com ``dimension`` colunas, um por texto."""

    model: str
    dimension: int

    def embed(self, texts: Sequence[str], task_type: TaskType) -> np.ndarray: ...


def embedding_model_from_env() -> str | None:
    """``EMBEDDING_MODEL`` do ambiente, ou ``None`` se vazio.

    Fachada de :func:`bussola_mcp.config.modelo_embedding`, mantida porque o
    indexador (``data/rag/indexar.py``) importa este nome.
    """
    return config.modelo_embedding()


class GeminiEmbedder:
    """Adaptador de :class:`Embedder` sobre ``google-genai``.

    ``client`` pode ser injetado (testes). Sem ele, o cliente é criado na
    primeira chamada, então importar este módulo não exige credencial.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        dimension: int = DEFAULT_DIMENSION,
        *,
        client: Any | None = None,
        batch_size: int | None = None,
        retries: int = 0,
        backoff_s: float = 2.0,
    ) -> None:
        if dimension <= 0:
            raise ValueError("dimension deve ser positiva")
        self.model = model
        self.dimension = dimension
        self._client = client
        self._batch_size = batch_size
        self._retries = max(0, retries)
        self._backoff_s = backoff_s

    def _get_client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    def _batch(self, client: Any) -> int:
        if self._batch_size is not None:
            return max(1, self._batch_size)
        return _BATCH_VERTEX if getattr(client, "vertexai", False) else _BATCH_API

    def _call(self, client: Any, texts: list[str], task_type: TaskType) -> list[list[float]]:
        from google.genai import types

        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimension)
        for attempt in range(self._retries + 1):
            try:
                response = client.models.embed_content(
                    model=self.model, contents=texts, config=config
                )
                return [list(e.values or []) for e in (response.embeddings or [])]
            except Exception:
                if attempt >= self._retries:
                    raise
                time.sleep(self._backoff_s * (attempt + 1))
        raise AssertionError("inalcançável")  # pragma: no cover

    def embed(self, texts: Sequence[str], task_type: TaskType) -> np.ndarray:
        """Embeddings dos ``texts``. Qualquer falha vira :class:`EmbeddingUnavailableError`."""
        items = list(texts)
        if not items:
            return np.zeros((0, self.dimension), dtype=np.float32)
        try:
            client = self._get_client()
            size = self._batch(client)
            vectors: list[list[float]] = []
            for start in range(0, len(items), size):
                batch = items[start : start + size]
                result = self._call(client, batch, task_type)
                if len(result) != len(batch):
                    raise ValueError("quantidade de embeddings diferente da de textos")
                vectors.extend(result)
            matrix = np.asarray(vectors, dtype=np.float32)
        except Exception as error:
            raise EmbeddingUnavailableError(type(error).__name__) from None
        if matrix.shape != (len(items), self.dimension) or not np.all(np.isfinite(matrix)):
            raise EmbeddingUnavailableError("InvalidResponse")
        return matrix
