"""``BuscadorNumpy``: similaridade de cosseno sobre ``embeddings.npy`` (backend ``numpy``).

- Só a pergunta é embutida em tempo de execução (``RETRIEVAL_QUERY``), com o
  mesmo modelo e a mesma dimensão do manifesto. Se o modelo configurado
  (``EMBEDDING_MODEL``) divergir do manifesto, o buscador recusa subir.
- ``tema`` vira uma máscara sobre a matriz. Só entram trechos com cosseno
  acima de ``min_score`` (limiar de "nada relevante", calibrado no eval).
- Pergunta vazia devolve ``[]`` sem chamar o modelo. Uma falha do embedding
  vira :class:`EmbeddingUnavailableError`, com mensagem genérica; a
  ferramenta (003) a traduz em ``INDISPONIVEL``.
"""

import logging
from pathlib import Path

import numpy as np

from bussola_mcp.contratos import TemaConhecimento, Trecho
from bussola_mcp.rag.embedding import (
    TASK_QUERY,
    Embedder,
    EmbeddingUnavailableError,
    GeminiEmbedder,
    embedding_model_from_env,
)
from bussola_mcp.rag.index import (
    INDEX_DIR,
    InvalidIndexError,
    load_chunks,
    load_embeddings,
    load_manifest,
)

DEFAULT_MIN_SCORE = 0.64  # calibrado em eval/rag/RESULTADOS.md

logger = logging.getLogger(__name__)


class BuscadorNumpy:
    """:class:`~bussola_mcp.dominio.interfaces.BuscadorContexto` por cosseno.

    Carrega trechos e matriz uma vez, no construtor. ``embedder`` permite
    injetar a porta (testes); sem ele, usa :class:`GeminiEmbedder` com o
    modelo e a dimensão do manifesto.
    """

    def __init__(
        self,
        index_dir: Path = INDEX_DIR,
        *,
        embedder: Embedder | None = None,
        model: str | None = None,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        manifest = load_manifest(index_dir)
        if not manifest.has_embeddings:
            raise InvalidIndexError(
                "índice do RAG sem embeddings: gere com data/rag/indexar.py (sem --sem-embeddings)"
            )
        expected_model = model or embedding_model_from_env() or manifest.modelo_embedding
        if expected_model != manifest.modelo_embedding:
            raise InvalidIndexError("EMBEDDING_MODEL difere do modelo do manifesto do índice")
        assert manifest.modelo_embedding is not None and manifest.dimensao is not None
        if embedder is None:
            embedder = GeminiEmbedder(manifest.modelo_embedding, manifest.dimensao)
        elif embedder.model != manifest.modelo_embedding or embedder.dimension != manifest.dimensao:
            raise InvalidIndexError("embedder com modelo ou dimensão diferente do manifesto")

        self._chunks = load_chunks(index_dir, manifest)
        matrix = load_embeddings(index_dir, manifest)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._matrix = (matrix / norms).astype(np.float32)
        self._topics = np.array([chunk.tema.value for chunk in self._chunks], dtype=object)
        self._embedder = embedder
        self._dimension = manifest.dimensao
        self.model = manifest.modelo_embedding
        self.min_score = min_score

    def _embed_question(self, pergunta: str) -> np.ndarray:
        try:
            vector = self._embedder.embed([pergunta], TASK_QUERY)
        except EmbeddingUnavailableError:
            self._log_failure()
            raise
        except Exception as error:
            self._log_failure()
            raise EmbeddingUnavailableError(type(error).__name__) from None
        vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vector.shape != (self._dimension,) or not np.all(np.isfinite(vector)):
            self._log_failure()
            raise EmbeddingUnavailableError("InvalidResponse")
        return vector

    @staticmethod
    def _log_failure() -> None:
        logger.warning(
            "falha no embedding da pergunta do RAG",
            extra={"evento": "rag_embedding_falhou", "erro_codigo": "INDISPONIVEL"},
        )

    def buscar(self, pergunta: str, k: int, tema: TemaConhecimento | None = None) -> list[Trecho]:
        """Até ``k`` trechos mais próximos da pergunta, filtrados por ``tema``."""
        question = (pergunta or "").strip()
        if k <= 0 or not question or not self._chunks:
            return []
        vector = self._embed_question(question)
        norm = float(np.linalg.norm(vector))
        if norm == 0.0:
            return []
        scores = self._matrix @ (vector / norm)
        mask = scores > max(self.min_score, 0.0)
        if tema is not None:
            mask &= self._topics == TemaConhecimento(tema).value
        candidates = ((round(float(scores[i]), 4), self._chunks[i]) for i in np.flatnonzero(mask))
        ranked = sorted(
            (item for item in candidates if item[0] > 0),
            key=lambda item: (-item[0], item[1].trecho_id),
        )
        return [
            Trecho.model_validate({**chunk.model_dump(), "score": score})
            for score, chunk in ranked[:k]
        ]
