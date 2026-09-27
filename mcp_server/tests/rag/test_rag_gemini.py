"""Chamada real ao Gemini (fora do ``make test``): ``make test-gemini``.

Roda só com ``BUSSOLA_TESTE_GEMINI=TRUE`` e credencial no ambiente
(plano B: ``GOOGLE_API_KEY`` passado inline; plano A: Vertex com ADC). A
chave nunca é lida nem exibida pelo teste.
"""

import os

import pytest

from bussola_mcp.rag import BuscadorNumpy
from bussola_mcp.rag.embedding import DEFAULT_DIMENSION, DEFAULT_MODEL, TASK_QUERY, GeminiEmbedder

pytestmark = [
    pytest.mark.gemini,
    pytest.mark.skipif(
        os.environ.get("BUSSOLA_TESTE_GEMINI", "").upper() != "TRUE",
        reason="teste com a API real do Gemini: use make test-gemini",
    ),
    pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY")
        and os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() != "TRUE",
        reason="sem credencial do Gemini no ambiente",
    ),
]


@pytest.fixture(autouse=True)
def _allow_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Desfaz a guarda de rede do conftest raiz, só para este módulo."""
    monkeypatch.undo()


def test_embedding_real_da_pergunta() -> None:
    embedder = GeminiEmbedder(DEFAULT_MODEL, DEFAULT_DIMENSION, retries=2)
    matrix = embedder.embed(["Onde guardo o dinheiro da entrada?"], TASK_QUERY)
    assert matrix.shape == (1, DEFAULT_DIMENSION)


def test_busca_real_com_numpy() -> None:
    result = BuscadorNumpy().buscar("Onde guardo o dinheiro da entrada?", 3)
    assert "reserva_objetivo#1" in [t.trecho_id for t in result]
