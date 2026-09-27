"""``BuscadorNumpy``: cosseno sobre um índice temporário gerado com o embedder falso."""

import logging
from pathlib import Path

import numpy as np
import pytest

from bussola_mcp.contratos import TemaConhecimento, Trecho
from bussola_mcp.rag import BuscadorNumpy, EmbeddingUnavailableError, InvalidIndexError
from bussola_mcp.rag.embedding import TASK_QUERY
from bussola_mcp.rag.index import EMBEDDINGS_FILE

MODEL = "modelo-falso"


@pytest.fixture(autouse=True)
def _no_embedding_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)


@pytest.fixture
def index_dir(indexar, small_corpus: Path, tmp_path: Path, fake_embedder) -> Path:
    out = tmp_path / "indice"
    indexar.build_index(small_corpus, out, embedder=fake_embedder(MODEL, 64))
    return out


def _searcher(index_dir: Path, embedder, **kwargs) -> BuscadorNumpy:
    return BuscadorNumpy(index_dir, embedder=embedder, **kwargs)


def test_embute_so_a_pergunta_com_retrieval_query(index_dir: Path, fake_embedder) -> None:
    embedder = fake_embedder(MODEL, 64)
    searcher = _searcher(index_dir, embedder, min_score=0.1)
    result = searcher.buscar("limite de juros do cheque especial", 3)
    assert embedder.calls == [(["limite de juros do cheque especial"], TASK_QUERY)]
    assert result[0].trecho_id == "cheque-especial#1"
    assert all(isinstance(t, Trecho) and t.score > 0.1 for t in result)
    assert [t.score for t in result] == sorted((t.score for t in result), reverse=True)


@pytest.mark.parametrize("question", ["", "   "])
def test_pergunta_vazia_nao_chama_o_modelo(index_dir: Path, fake_embedder, question: str) -> None:
    embedder = fake_embedder(MODEL, 64)
    assert _searcher(index_dir, embedder).buscar(question, 5) == []
    assert _searcher(index_dir, embedder).buscar("cheque especial", 0) == []
    assert embedder.calls == []


def test_limiar_de_relevancia(index_dir: Path, fake_embedder) -> None:
    question = "limite de juros do cheque especial"
    loose = _searcher(index_dir, fake_embedder(MODEL, 64), min_score=-1.0).buscar(question, 10)
    strict = _searcher(index_dir, fake_embedder(MODEL, 64), min_score=0.99).buscar(question, 10)
    assert loose and all(t.score > 0 for t in loose)
    assert strict == []


def test_mascara_de_tema(index_dir: Path, fake_embedder) -> None:
    searcher = _searcher(index_dir, fake_embedder(MODEL, 64), min_score=-1.0)
    result = searcher.buscar(
        "reserva de emergência e cheque especial", 10, TemaConhecimento.CREDITO
    )
    assert {t.tema for t in result} <= {TemaConhecimento.CREDITO}
    assert searcher.buscar("reserva", 10, TemaConhecimento.PRODUTO) == []


def test_empate_desfeito_por_trecho_id(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder
) -> None:
    def constant(texts):
        return np.ones((len(texts), 64), np.float32)

    out = tmp_path / "constante"
    indexar.build_index(small_corpus, out, embedder=fake_embedder(MODEL, 64, override=constant))
    searcher = _searcher(out, fake_embedder(MODEL, 64, override=constant))
    result = searcher.buscar("qualquer", 5)
    assert [t.trecho_id for t in result] == sorted(t.trecho_id for t in result)
    assert len(result) == 5 and {t.score for t in result} == {1.0}


def test_recusa_modelo_diferente_do_manifesto(
    index_dir: Path, fake_embedder, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(InvalidIndexError, match="EMBEDDING_MODEL"):
        _searcher(index_dir, fake_embedder(MODEL, 64), model="outro-modelo")
    monkeypatch.setenv("EMBEDDING_MODEL", "outro-modelo")
    with pytest.raises(InvalidIndexError, match="EMBEDDING_MODEL"):
        _searcher(index_dir, fake_embedder(MODEL, 64))
    monkeypatch.setenv("EMBEDDING_MODEL", MODEL)
    assert _searcher(index_dir, fake_embedder(MODEL, 64)).model == MODEL


@pytest.mark.parametrize(("model", "dimension"), [("outro-modelo", 64), (MODEL, 32)])
def test_recusa_embedder_incompativel(
    index_dir: Path, fake_embedder, model: str, dimension: int
) -> None:
    with pytest.raises(InvalidIndexError, match="embedder"):
        _searcher(index_dir, fake_embedder(model, dimension))


def test_recusa_indice_sem_embeddings(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder
) -> None:
    out = tmp_path / "so-trechos"
    indexar.build_index(small_corpus, out, embedder=None)
    with pytest.raises(InvalidIndexError, match="sem embeddings"):
        _searcher(out, fake_embedder(MODEL, 64))


def test_recusa_matriz_com_formato_errado(index_dir: Path, fake_embedder) -> None:
    np.save(index_dir / EMBEDDINGS_FILE, np.ones((2, 64), dtype=np.float32))
    with pytest.raises(InvalidIndexError, match="divergem"):
        _searcher(index_dir, fake_embedder(MODEL, 64))


@pytest.mark.parametrize(
    "embedder_kwargs",
    [
        {"error": RuntimeError("403 PERMISSION_DENIED projeto-secreto chave=xyz")},
        {"error": EmbeddingUnavailableError("ServerError")},
        {"override": lambda texts: np.ones((1, 8), np.float32)},
        {"override": lambda texts: np.full((1, 64), np.nan, np.float32)},
    ],
)
def test_falha_no_embedding_vira_erro_generico(
    index_dir: Path, fake_embedder, caplog: pytest.LogCaptureFixture, embedder_kwargs: dict
) -> None:
    searcher = _searcher(index_dir, fake_embedder(MODEL, 64, **embedder_kwargs))
    question = "pergunta confidencial sobre cheque especial"
    with caplog.at_level(logging.WARNING, logger="bussola_mcp.rag.vector"):
        with pytest.raises(EmbeddingUnavailableError) as caught:
            searcher.buscar(question, 3)
    message = str(caught.value)
    assert message == "serviço de embedding indisponível no momento"
    assert "PERMISSION" not in message and "projeto" not in message
    assert caught.value.__cause__ is None
    records = [r for r in caplog.records if r.name == "bussola_mcp.rag.vector"]
    assert records and getattr(records[0], "evento", None) == "rag_embedding_falhou"
    assert all(question not in r.getMessage() for r in caplog.records)
    assert all("PERMISSION" not in r.getMessage() for r in caplog.records)


def test_vetor_nulo_da_pergunta_devolve_vazio(index_dir: Path, fake_embedder) -> None:
    zero = fake_embedder(MODEL, 64, override=lambda texts: np.zeros((1, 64), np.float32))
    assert _searcher(index_dir, zero, min_score=-1.0).buscar("qualquer", 5) == []
