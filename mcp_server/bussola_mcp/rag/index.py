"""Formato do índice do RAG (contratos §4) e sua carga em memória.

``bussola_mcp/rag/indice/`` tem três arquivos, gerados por ``data/rag/indexar.py``:

- ``trechos.jsonl``: um :class:`TrechoCorpus` por linha, em JSON canônico;
- ``embeddings.npy``: ``float32``, uma linha por trecho, na mesma ordem
  (ausente quando o índice foi gerado com ``--sem-embeddings``);
- ``manifesto.json``: ``modelo_embedding``, ``dimensao``, ``qtd_trechos``,
  ``hash_corpus`` e ``gerado_em``.

``hash_corpus`` é o sha256 do conteúdo de ``trechos.jsonl``, então basta
recalcular a partir do corpus para saber se o índice versionado está em dia.
"""

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from bussola_mcp.contratos import TrechoCorpus

INDEX_DIR = Path(__file__).resolve().parent / "indice"
CHUNKS_FILE = "trechos.jsonl"
EMBEDDINGS_FILE = "embeddings.npy"
MANIFEST_FILE = "manifesto.json"


class InvalidIndexError(ValueError):
    """Índice ausente, inconsistente ou incompatível com o backend pedido."""


class Manifest(BaseModel):
    """Conteúdo de ``manifesto.json``."""

    model_config = ConfigDict(extra="forbid")

    modelo_embedding: str | None
    dimensao: int | None = Field(default=None, gt=0)
    qtd_trechos: int = Field(ge=0)
    hash_corpus: str = Field(pattern=r"^[0-9a-f]{64}$")
    gerado_em: str

    @property
    def has_embeddings(self) -> bool:
        return self.modelo_embedding is not None and self.dimensao is not None


def serialize_chunks(chunks: Sequence[TrechoCorpus]) -> str:
    """Conteúdo canônico de ``trechos.jsonl`` (chaves ordenadas, uma linha por trecho)."""
    return "".join(
        json.dumps(chunk.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n"
        for chunk in chunks
    )


def corpus_hash(chunks: Sequence[TrechoCorpus]) -> str:
    """sha256 do ``trechos.jsonl`` canônico: muda se qualquer trecho ou fonte mudar."""
    return hashlib.sha256(serialize_chunks(chunks).encode("utf-8")).hexdigest()


def serialize_manifest(manifest: Manifest) -> str:
    return json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"


def document_text(chunk: TrechoCorpus) -> str:
    """Texto embutido de cada trecho no índice: título da seção + texto."""
    return f"{chunk.titulo}\n\n{chunk.texto}"


def load_manifest(index_dir: Path = INDEX_DIR) -> Manifest:
    path = index_dir / MANIFEST_FILE
    try:
        return Manifest.model_validate_json(path.read_bytes())
    except FileNotFoundError:
        raise InvalidIndexError("índice do RAG sem manifesto.json") from None
    except ValidationError:
        raise InvalidIndexError("manifesto.json do RAG fora do formato") from None


def load_chunks(
    index_dir: Path = INDEX_DIR, manifest: Manifest | None = None
) -> list[TrechoCorpus]:
    """Trechos do índice, conferidos contra o manifesto (quantidade)."""
    manifest = manifest if manifest is not None else load_manifest(index_dir)
    path = index_dir / CHUNKS_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise InvalidIndexError("índice do RAG sem trechos.jsonl") from None
    try:
        chunks = [TrechoCorpus.model_validate_json(line) for line in lines if line.strip()]
    except ValidationError:
        raise InvalidIndexError("trechos.jsonl do RAG fora do formato") from None
    if len(chunks) != manifest.qtd_trechos:
        raise InvalidIndexError("trechos.jsonl e manifesto.json do RAG divergem")
    if len({c.trecho_id for c in chunks}) != len(chunks):
        raise InvalidIndexError("trechos.jsonl do RAG tem trecho_id repetido")
    return chunks


def load_embeddings(index_dir: Path, manifest: Manifest) -> np.ndarray:
    """Matriz ``(qtd_trechos, dimensao)`` em ``float32``, conferida contra o manifesto."""
    if not manifest.has_embeddings:
        raise InvalidIndexError(
            "índice do RAG sem embeddings: gere com data/rag/indexar.py (sem --sem-embeddings)"
        )
    path = index_dir / EMBEDDINGS_FILE
    try:
        matrix = np.load(path, allow_pickle=False)
    except FileNotFoundError:
        raise InvalidIndexError("índice do RAG sem embeddings.npy") from None
    except ValueError:
        raise InvalidIndexError("embeddings.npy do RAG ilegível") from None
    if matrix.dtype != np.float32 or matrix.shape != (manifest.qtd_trechos, manifest.dimensao):
        raise InvalidIndexError("embeddings.npy e manifesto.json do RAG divergem")
    if not np.all(np.isfinite(matrix)):
        raise InvalidIndexError("embeddings.npy do RAG tem valores inválidos")
    return matrix
