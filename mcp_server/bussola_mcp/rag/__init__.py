"""RAG de conhecimento financeiro da Bússola (ciclo 002, contratos §4).

Ponto de entrada para o ``server.py`` (003)::

    from bussola_mcp.rag import criar_buscador

    buscador = criar_buscador(os.environ.get("RAG_BACKEND", "lexico"))
    trechos = buscador.buscar(pergunta, k, tema)   # list[Trecho]

- ``lexico`` (padrão): :class:`BuscadorLexico`, BM25 puro Python, sem GCP.
- ``numpy``: :class:`BuscadorNumpy`, cosseno sobre ``embeddings.npy``; embute
  só a pergunta com ``EMBEDDING_MODEL``.

Os dois carregam o índice versionado (``bussola_mcp/rag/indice/``) uma vez,
no construtor. Erros de montagem são ``ValueError`` (``InvalidIndexError``);
uma falha de embedding na busca é :class:`EmbeddingUnavailableError`.
"""

import os
from pathlib import Path

from bussola_mcp.dominio.interfaces import BuscadorContexto
from bussola_mcp.rag.embedding import Embedder, EmbeddingUnavailableError
from bussola_mcp.rag.index import INDEX_DIR, InvalidIndexError
from bussola_mcp.rag.lexical import BuscadorLexico
from bussola_mcp.rag.vector import BuscadorNumpy

BACKEND_LEXICO = "lexico"
BACKEND_NUMPY = "numpy"
BACKENDS: tuple[str, ...] = (BACKEND_LEXICO, BACKEND_NUMPY)

__all__ = [
    "BACKENDS",
    "BACKEND_LEXICO",
    "BACKEND_NUMPY",
    "INDEX_DIR",
    "BuscadorLexico",
    "BuscadorNumpy",
    "Embedder",
    "EmbeddingUnavailableError",
    "InvalidIndexError",
    "criar_buscador",
]


def criar_buscador(
    backend: str | None = None,
    *,
    index_dir: Path | None = None,
    embedder: Embedder | None = None,
) -> BuscadorContexto:
    """Monta o buscador do ``backend`` (``lexico`` | ``numpy``).

    ``None`` ou vazio lê ``RAG_BACKEND`` e, sem ele, usa ``lexico``. Um valor
    desconhecido levanta ``ValueError``. ``index_dir`` e ``embedder`` servem
    aos testes; em produção ficam nos padrões (índice versionado e Gemini).
    """
    name = (backend if backend is not None else os.environ.get("RAG_BACKEND", "")).strip()
    name = name.lower() or BACKEND_LEXICO
    directory = index_dir if index_dir is not None else INDEX_DIR
    if name == BACKEND_LEXICO:
        return BuscadorLexico(directory)
    if name == BACKEND_NUMPY:
        return BuscadorNumpy(directory, embedder=embedder)
    raise ValueError(f"RAG_BACKEND inválido: use {' ou '.join(BACKENDS)}")
