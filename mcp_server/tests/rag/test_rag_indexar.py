"""``data/rag/indexar.py``: construção idempotente do índice e CLI."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from bussola_mcp.rag.embedding import TASK_DOCUMENT, EmbeddingUnavailableError
from bussola_mcp.rag.index import (
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    MANIFEST_FILE,
    load_chunks,
    load_embeddings,
    load_manifest,
)

MakeDoc = Callable[..., str]
AddDoc = Callable[[Path, str, str, str], Path]
FILES = (CHUNKS_FILE, EMBEDDINGS_FILE, MANIFEST_FILE)


def _clock(hour: int) -> Callable[[], datetime]:
    return lambda: datetime(2026, 1, 1, hour, 0, 0, tzinfo=UTC)


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def test_gera_os_tres_arquivos(indexar, small_corpus: Path, tmp_path: Path, fake_embedder) -> None:
    out = tmp_path / "indice"
    embedder = fake_embedder()
    result = indexar.build_index(small_corpus, out, embedder=embedder, now=_clock(10))

    assert result.written and result.embedded and result.chunk_count == 5
    assert sorted(p.name for p in out.iterdir()) == sorted(FILES)
    manifest = load_manifest(out)
    assert manifest.modelo_embedding == "modelo-falso"
    assert manifest.dimensao == 64
    assert manifest.qtd_trechos == 5
    assert manifest.hash_corpus == result.hash_corpus
    assert manifest.gerado_em == "2026-01-01T10:00:00Z"
    assert len(load_chunks(out)) == 5
    matrix = load_embeddings(out, manifest)
    assert matrix.dtype == np.float32 and matrix.shape == (5, 64)
    assert [task for _, task in embedder.calls] == [TASK_DOCUMENT]
    assert embedder.calls[0][0][0].startswith("Reserva de emergência\n\n")


def test_corpus_inalterado_nao_chama_o_modelo_nem_reescreve(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder
) -> None:
    out = tmp_path / "indice"
    embedder = fake_embedder()
    indexar.build_index(small_corpus, out, embedder=embedder, now=_clock(10))
    before = _snapshot(out)
    mtimes = {p.name: p.stat().st_mtime_ns for p in out.iterdir()}

    again = indexar.build_index(small_corpus, out, embedder=embedder, now=_clock(11))
    assert not again.written and again.reason == "sem mudança"
    assert len(embedder.calls) == 1
    assert _snapshot(out) == before
    assert {p.name: p.stat().st_mtime_ns for p in out.iterdir()} == mtimes

    only_chunks = indexar.build_index(small_corpus, out, embedder=None, now=_clock(12))
    assert not only_chunks.written and only_chunks.embedded
    assert _snapshot(out) == before


def test_sem_embeddings_grava_so_trechos_e_manifesto(
    indexar, small_corpus: Path, tmp_path: Path
) -> None:
    out = tmp_path / "indice"
    result = indexar.build_index(small_corpus, out, embedder=None, now=_clock(10))
    assert result.written and not result.embedded
    assert sorted(p.name for p in out.iterdir()) == sorted([CHUNKS_FILE, MANIFEST_FILE])
    manifest = load_manifest(out)
    assert manifest.modelo_embedding is None and manifest.dimensao is None


def test_corpus_alterado_regrava_e_remove_embeddings_velhos(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder, document: MakeDoc, add_doc: AddDoc
) -> None:
    out = tmp_path / "indice"
    indexar.build_index(small_corpus, out, embedder=fake_embedder(), now=_clock(10))
    first_hash = load_manifest(out).hash_corpus

    add_doc(small_corpus, "credito", "novo", document(sections=[("Nova seção", "Novo texto.")]))
    result = indexar.build_index(small_corpus, out, embedder=None, now=_clock(11))
    assert result.written and result.reason == "corpus alterado"
    assert load_manifest(out).hash_corpus != first_hash
    assert not (out / EMBEDDINGS_FILE).exists()
    assert load_manifest(out).qtd_trechos == 6


def test_troca_de_modelo_regera_embeddings(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder
) -> None:
    out = tmp_path / "indice"
    indexar.build_index(small_corpus, out, embedder=fake_embedder(), now=_clock(10))
    other = fake_embedder("outro-modelo", 32)
    result = indexar.build_index(small_corpus, out, embedder=other, now=_clock(11))
    assert result.written and result.reason == "embeddings gerados"
    assert len(other.calls) == 1
    assert load_embeddings(out, load_manifest(out)).shape == (5, 32)


def test_corpus_invalido_nao_grava_nada(
    indexar, small_corpus: Path, tmp_path: Path, fake_embedder, document: MakeDoc, add_doc: AddDoc
) -> None:
    add_doc(small_corpus, "credito", "sem-fonte", document(source_reference=None))
    out = tmp_path / "indice"
    embedder = fake_embedder()
    with pytest.raises(indexar.CorpusInvalidError) as caught:
        indexar.build_index(small_corpus, out, embedder=embedder)
    assert any("credito/sem-fonte.md" in p for p in caught.value.problems)
    assert not out.exists()
    assert embedder.calls == []


@pytest.mark.parametrize(
    "embedder_kwargs",
    [
        {"error": EmbeddingUnavailableError("ServerError")},
        {"override": lambda texts: np.zeros((len(texts), 3), dtype=np.float32)},
    ],
)
def test_falha_no_embedding_mantem_o_indice_anterior(
    indexar,
    small_corpus: Path,
    tmp_path: Path,
    fake_embedder,
    document: MakeDoc,
    add_doc: AddDoc,
    embedder_kwargs: dict,
) -> None:
    out = tmp_path / "indice"
    indexar.build_index(small_corpus, out, embedder=fake_embedder(), now=_clock(10))
    before = _snapshot(out)
    add_doc(small_corpus, "credito", "novo", document())
    with pytest.raises(EmbeddingUnavailableError):
        indexar.build_index(small_corpus, out, embedder=fake_embedder(**embedder_kwargs))
    assert _snapshot(out) == before


def test_cli_codigos_de_saida(
    indexar,
    small_corpus: Path,
    tmp_path: Path,
    document: MakeDoc,
    add_doc: AddDoc,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = tmp_path / "catalogo.json"
    catalog.write_text("[]", encoding="utf-8")
    out = tmp_path / "indice"
    base = ["--corpus", str(small_corpus), "--saida", str(out), "--catalogo", str(catalog)]

    assert indexar.main([*base, "--sem-embeddings"]) == 0
    assert "índice gravado (corpus alterado): 5 trechos, sem embeddings" in capsys.readouterr().out
    assert indexar.main([*base, "--sem-embeddings"]) == 0
    assert "índice inalterado" in capsys.readouterr().out

    class _BrokenEmbedder:
        def __init__(self, model: str, dimension: int, **_: object) -> None:
            self.model, self.dimension = model, dimension

        def embed(self, texts, task_type):
            raise EmbeddingUnavailableError("PermissionDenied")

    monkeypatch.setattr(indexar, "GeminiEmbedder", _BrokenEmbedder)
    before = _snapshot(out)
    assert indexar.main(base) == 2
    err = capsys.readouterr().err
    assert "falha no embedding (causa: PermissionDenied); índice não alterado" in err
    assert _snapshot(out) == before

    add_doc(small_corpus, "credito", "sem-fonte", document(source_reference=None))
    assert indexar.main([*base, "--sem-embeddings"]) == 1
    assert "credito/sem-fonte.md: campo obrigatório ausente: fonte_referencia" in (
        capsys.readouterr().err
    )


def test_modelo_padrao_vem_de_embedding_model(indexar, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-005")
    assert indexar.parse_args([]).modelo == "text-embedding-005"
    monkeypatch.delenv("EMBEDDING_MODEL")
    assert indexar.parse_args([]).modelo == "gemini-embedding-001"
    assert indexar.parse_args([]).dimensao == 768
