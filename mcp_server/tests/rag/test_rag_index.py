"""Formato do índice (``bussola_mcp.rag.index``) e o índice versionado em ``rag/indice/``."""

import json
import re
from pathlib import Path

import numpy as np
import pytest
from rag_support import REAL_CORPUS

from bussola_mcp.contratos import FonteTrecho, TemaConhecimento, TrechoCorpus
from bussola_mcp.rag.corpus import load_corpus
from bussola_mcp.rag.embedding import DEFAULT_DIMENSION, DEFAULT_MODEL
from bussola_mcp.rag.index import (
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    INDEX_DIR,
    MANIFEST_FILE,
    InvalidIndexError,
    Manifest,
    corpus_hash,
    document_text,
    load_chunks,
    load_embeddings,
    load_manifest,
    serialize_chunks,
    serialize_manifest,
)

HASH = "0" * 64


def _chunk(number: int, text: str = "Texto.") -> TrechoCorpus:
    return TrechoCorpus(
        doc_id="doc",
        trecho_id=f"doc#{number}",
        titulo=f"Seção {number}",
        tema=TemaConhecimento.CREDITO,
        texto=text,
        fonte=FonteTrecho(nome="Equipe Bússola", referencia="Conteúdo educativo"),
    )


def _write_index(directory: Path, chunks: list[TrechoCorpus], **manifest: object) -> Manifest:
    directory.mkdir(parents=True, exist_ok=True)
    fields = {
        "modelo_embedding": None,
        "dimensao": None,
        "qtd_trechos": len(chunks),
        "hash_corpus": corpus_hash(chunks),
        "gerado_em": "2026-01-01T00:00:00Z",
    }
    fields.update(manifest)
    parsed = Manifest.model_validate(fields)
    (directory / CHUNKS_FILE).write_text(serialize_chunks(chunks), encoding="utf-8")
    (directory / MANIFEST_FILE).write_text(serialize_manifest(parsed), encoding="utf-8")
    return parsed


# --- formato ------------------------------------------------------------------


def test_serializacao_e_hash_sao_deterministicos() -> None:
    chunks = [_chunk(1), _chunk(2)]
    content = serialize_chunks(chunks)
    assert content == serialize_chunks([_chunk(1), _chunk(2)])
    assert content.count("\n") == 2
    first = json.loads(content.splitlines()[0])
    assert list(first) == sorted(first)
    assert corpus_hash(chunks) == corpus_hash([_chunk(1), _chunk(2)])
    assert corpus_hash(chunks) != corpus_hash([_chunk(1), _chunk(2, "Outro texto.")])


def test_texto_embutido_junta_titulo_e_corpo() -> None:
    assert document_text(_chunk(3, "Corpo.")) == "Seção 3\n\nCorpo."


def test_manifesto_ausente_ou_malformado(tmp_path: Path) -> None:
    with pytest.raises(InvalidIndexError, match="sem manifesto"):
        load_manifest(tmp_path)
    (tmp_path / MANIFEST_FILE).write_text('{"qtd_trechos": 1}', encoding="utf-8")
    with pytest.raises(InvalidIndexError, match="fora do formato"):
        load_manifest(tmp_path)


def test_manifesto_rejeita_hash_invalido() -> None:
    with pytest.raises(ValueError):
        Manifest(modelo_embedding=None, qtd_trechos=0, hash_corpus="abc", gerado_em="x")


def test_trechos_divergentes_do_manifesto(tmp_path: Path) -> None:
    _write_index(tmp_path, [_chunk(1), _chunk(2)], qtd_trechos=3)
    with pytest.raises(InvalidIndexError, match="divergem"):
        load_chunks(tmp_path)


def test_trecho_id_repetido(tmp_path: Path) -> None:
    _write_index(tmp_path, [_chunk(1), _chunk(1)])
    with pytest.raises(InvalidIndexError, match="repetido"):
        load_chunks(tmp_path)


def test_embeddings_conferidos_contra_o_manifesto(tmp_path: Path) -> None:
    chunks = [_chunk(1), _chunk(2)]
    manifest = _write_index(tmp_path, chunks, modelo_embedding="m", dimensao=4)
    with pytest.raises(InvalidIndexError, match="sem embeddings.npy"):
        load_embeddings(tmp_path, manifest)

    np.save(tmp_path / EMBEDDINGS_FILE, np.ones((2, 4), dtype=np.float64))
    with pytest.raises(InvalidIndexError, match="divergem"):
        load_embeddings(tmp_path, manifest)

    np.save(tmp_path / EMBEDDINGS_FILE, np.ones((2, 3), dtype=np.float32))
    with pytest.raises(InvalidIndexError, match="divergem"):
        load_embeddings(tmp_path, manifest)

    np.save(tmp_path / EMBEDDINGS_FILE, np.full((2, 4), np.nan, dtype=np.float32))
    with pytest.raises(InvalidIndexError, match="valores inválidos"):
        load_embeddings(tmp_path, manifest)

    np.save(tmp_path / EMBEDDINGS_FILE, np.ones((2, 4), dtype=np.float32))
    assert load_embeddings(tmp_path, manifest).shape == (2, 4)


def test_indice_sem_embeddings_nao_carrega_matriz(tmp_path: Path) -> None:
    manifest = _write_index(tmp_path, [_chunk(1)])
    assert not manifest.has_embeddings
    with pytest.raises(InvalidIndexError, match="sem embeddings"):
        load_embeddings(tmp_path, manifest)


# --- índice versionado ----------------------------------------------------------


def test_indice_versionado_esta_em_dia_com_o_corpus() -> None:
    """Falha se o corpus mudou sem rodar ``make indice-embeddings`` (hash_corpus velho)."""
    chunks = load_corpus(REAL_CORPUS)
    manifest = load_manifest(INDEX_DIR)
    assert manifest.hash_corpus == corpus_hash(chunks), (
        "hash_corpus do índice está velho: rode data/rag/indexar.py"
    )
    assert (INDEX_DIR / CHUNKS_FILE).read_text(encoding="utf-8") == serialize_chunks(chunks)
    assert manifest.qtd_trechos == len(chunks)


def test_indice_versionado_tem_embeddings_do_modelo_padrao() -> None:
    manifest = load_manifest(INDEX_DIR)
    assert manifest.modelo_embedding == DEFAULT_MODEL
    assert manifest.dimensao == DEFAULT_DIMENSION
    matrix = load_embeddings(INDEX_DIR, manifest)
    assert matrix.shape == (manifest.qtd_trechos, DEFAULT_DIMENSION)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", manifest.gerado_em)


def test_indice_versionado_e_pequeno_e_sem_segredos() -> None:
    secret_patterns = [
        re.compile("AI" + r"za[0-9A-Za-z_-]{35}"),
        re.compile("ya" + r"29\.[0-9A-Za-z_-]{20,}"),
        re.compile("PRIVATE" + " KEY"),
    ]
    total = 0
    for name in (CHUNKS_FILE, EMBEDDINGS_FILE, MANIFEST_FILE):
        data = (INDEX_DIR / name).read_bytes()
        total += len(data)
        text = data.decode("latin-1")
        assert not any(p.search(text) for p in secret_patterns), name
    assert total < 1_000_000
