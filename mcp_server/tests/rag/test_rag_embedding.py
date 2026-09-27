"""``GeminiEmbedder`` com cliente falso: lotes, configuração, retentativa e erro genérico."""

from types import SimpleNamespace

import numpy as np
import pytest

from bussola_mcp.rag.embedding import (
    TASK_DOCUMENT,
    TASK_QUERY,
    Embedder,
    EmbeddingUnavailableError,
    GeminiEmbedder,
    embedding_model_from_env,
)


class FakeModels:
    def __init__(self, dimension: int, failures: list[Exception] | None = None) -> None:
        self.dimension = dimension
        self.failures = list(failures or [])
        self.calls: list[dict] = []
        self.count_delta = 0

    def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": list(contents), "config": config})
        if self.failures:
            raise self.failures.pop(0)
        embeddings = [
            SimpleNamespace(values=[float(len(text))] * self.dimension)
            for text in list(contents)[: len(contents) + self.count_delta]
        ]
        return SimpleNamespace(embeddings=embeddings)


def _client(dimension: int = 4, *, vertexai: bool = False, failures=None) -> SimpleNamespace:
    return SimpleNamespace(vertexai=vertexai, models=FakeModels(dimension, failures))


def test_e_um_embedder() -> None:
    assert isinstance(GeminiEmbedder(client=_client()), Embedder)


@pytest.mark.parametrize(("vertexai", "batches"), [(True, 25), (False, 2)])
def test_tamanho_do_lote_depende_do_modo(vertexai: bool, batches: int) -> None:
    client = _client(vertexai=vertexai)
    embedder = GeminiEmbedder("gemini-embedding-001", 4, client=client)
    matrix = embedder.embed([f"texto {i}" for i in range(25)], TASK_DOCUMENT)
    assert matrix.shape == (25, 4) and matrix.dtype == np.float32
    assert len(client.models.calls) == batches


def test_passa_modelo_tarefa_e_dimensao() -> None:
    client = _client(dimension=8)
    GeminiEmbedder("gemini-embedding-001", 8, client=client).embed(["pergunta"], TASK_QUERY)
    call = client.models.calls[0]
    assert call["model"] == "gemini-embedding-001"
    assert call["contents"] == ["pergunta"]
    assert call["config"].task_type == TASK_QUERY
    assert call["config"].output_dimensionality == 8


def test_retenta_antes_de_desistir() -> None:
    client = _client(failures=[ConnectionError("x"), TimeoutError("y")])
    embedder = GeminiEmbedder(client=client, dimension=4, retries=2, backoff_s=0)
    assert embedder.embed(["a"], TASK_QUERY).shape == (1, 4)
    assert len(client.models.calls) == 3


def test_falha_vira_erro_generico_sem_detalhe_do_provedor() -> None:
    detail = "403 PERMISSION_DENIED no projeto batalha chave=xyz"
    client = _client(failures=[PermissionError(detail)] * 2)
    embedder = GeminiEmbedder(client=client, dimension=4, retries=1, backoff_s=0)
    with pytest.raises(EmbeddingUnavailableError) as caught:
        embedder.embed(["a"], TASK_QUERY)
    assert caught.value.cause == "PermissionError"
    assert str(caught.value) == "serviço de embedding indisponível no momento"
    assert detail not in repr(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__


def test_quantidade_ou_dimensao_errada_na_resposta() -> None:
    client = _client(dimension=4)
    client.models.count_delta = -1
    with pytest.raises(EmbeddingUnavailableError) as caught:
        GeminiEmbedder(client=client, dimension=4).embed(["a", "b"], TASK_DOCUMENT)
    assert caught.value.cause == "ValueError"

    with pytest.raises(EmbeddingUnavailableError) as caught:
        GeminiEmbedder(client=_client(dimension=3), dimension=4).embed(["a"], TASK_DOCUMENT)
    assert caught.value.cause == "InvalidResponse"


def test_lista_vazia_nao_chama_o_cliente() -> None:
    client = _client()
    matrix = GeminiEmbedder(client=client, dimension=4).embed([], TASK_QUERY)
    assert matrix.shape == (0, 4)
    assert client.models.calls == []


def test_dimensao_invalida() -> None:
    with pytest.raises(ValueError):
        GeminiEmbedder(dimension=0)


def test_modelo_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "  gemini-embedding-001 ")
    assert embedding_model_from_env() == "gemini-embedding-001"
    monkeypatch.setenv("EMBEDDING_MODEL", "")
    assert embedding_model_from_env() is None
    monkeypatch.delenv("EMBEDDING_MODEL")
    assert embedding_model_from_env() is None
