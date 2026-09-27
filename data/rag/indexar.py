"""Gera o índice do RAG a partir do corpus (ciclo 002, contratos §4).

Uso (a partir da raiz do repositório)::

    # só trechos + manifesto (basta para RAG_BACKEND=lexico, sem GCP)
    uv run --project mcp_server python data/rag/indexar.py --sem-embeddings

    # com embeddings (RAG_BACKEND=numpy). Plano B: Gemini API com chave inline,
    # nunca impressa nem gravada:
    GOOGLE_GENAI_USE_VERTEXAI=FALSE GOOGLE_API_KEY="$(gcloud secrets versions access \
        latest --secret=gemini-api-key --project batalha-time-07-lkbv)" \
        uv run --project mcp_server python data/rag/indexar.py

Grava em ``mcp_server/bussola_mcp/rag/indice/``: ``trechos.jsonl``,
``embeddings.npy`` (``RETRIEVAL_DOCUMENT``) e ``manifesto.json``.

**Idempotente:** se o corpus não mudou (``hash_corpus``) e o índice já tem o
que foi pedido, não chama o modelo e não reescreve nada. Com
``--sem-embeddings`` e corpus alterado, o ``embeddings.npy`` antigo é
removido (ficaria desalinhado) e o manifesto registra ``modelo_embedding``
nulo.
"""

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from bussola_mcp import config
from bussola_mcp.contratos import ProdutoCatalogo
from bussola_mcp.rag.corpus import load_corpus, validate_corpus
from bussola_mcp.rag.embedding import (
    DEFAULT_DIMENSION,
    DEFAULT_MODEL,
    TASK_DOCUMENT,
    Embedder,
    EmbeddingUnavailableError,
    GeminiEmbedder,
    embedding_model_from_env,
)
from bussola_mcp.rag.index import (
    CHUNKS_FILE,
    EMBEDDINGS_FILE,
    INDEX_DIR,
    MANIFEST_FILE,
    InvalidIndexError,
    Manifest,
    corpus_hash,
    document_text,
    load_manifest,
    serialize_chunks,
    serialize_manifest,
)

# A raiz do repositório tem um dono só: ``bussola_mcp.config``.
REPO_ROOT = config.RAIZ_REPOSITORIO
DEFAULT_CORPUS = REPO_ROOT / "data" / "rag" / "corpus"
DEFAULT_CATALOG = REPO_ROOT / "contracts" / "catalogo_produtos.json"


class CorpusInvalidError(ValueError):
    """O corpus não passou em ``validate_corpus``; o índice não é gerado."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__(f"corpus inválido: {len(problems)} problema(s)")
        self.problems = problems


@dataclass(frozen=True)
class BuildResult:
    written: bool
    embedded: bool
    chunk_count: int
    hash_corpus: str
    reason: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _read_manifest(out_dir: Path) -> Manifest | None:
    try:
        return load_manifest(out_dir)
    except InvalidIndexError:
        return None


def _embeddings_match(out_dir: Path, manifest: Manifest, embedder: Embedder) -> bool:
    if manifest.modelo_embedding != embedder.model or manifest.dimensao != embedder.dimension:
        return False
    try:
        matrix = np.load(out_dir / EMBEDDINGS_FILE, allow_pickle=False)
    except (OSError, ValueError):
        return False
    return matrix.dtype == np.float32 and matrix.shape == (
        manifest.qtd_trechos,
        manifest.dimensao,
    )


def _write_atomic(path: Path, data: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _write_embeddings(path: Path, matrix: np.ndarray) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        np.save(handle, matrix.astype(np.float32), allow_pickle=False)
    os.replace(temporary, path)


def build_index(
    corpus_dir: Path,
    out_dir: Path,
    *,
    embedder: Embedder | None,
    catalog: Sequence[ProdutoCatalogo] | None = None,
    now: Callable[[], datetime] = _utc_now,
) -> BuildResult:
    """Valida o corpus e grava o índice em ``out_dir`` só se algo mudou.

    ``embedder=None`` equivale a ``--sem-embeddings``. Levanta
    :class:`CorpusInvalidError` se o corpus for inválido e
    :class:`EmbeddingUnavailableError` se o embedding falhar (nada é gravado).
    """
    problems = validate_corpus(corpus_dir, catalog)
    if problems:
        raise CorpusInvalidError(problems)
    chunks = load_corpus(corpus_dir)
    content = serialize_chunks(chunks)
    digest = corpus_hash(chunks)
    previous = _read_manifest(out_dir)
    chunks_path = out_dir / CHUNKS_FILE
    same_corpus = (
        previous is not None
        and previous.hash_corpus == digest
        and chunks_path.is_file()
        and chunks_path.read_text(encoding="utf-8") == content
    )

    if same_corpus and previous is not None:
        if embedder is None:
            return BuildResult(False, previous.has_embeddings, len(chunks), digest, "sem mudança")
        if _embeddings_match(out_dir, previous, embedder):
            return BuildResult(False, True, len(chunks), digest, "sem mudança")

    matrix: np.ndarray | None = None
    if embedder is not None:
        matrix = embedder.embed([document_text(c) for c in chunks], TASK_DOCUMENT)
        if matrix.shape != (len(chunks), embedder.dimension):
            raise EmbeddingUnavailableError("InvalidResponse")

    manifest = Manifest(
        modelo_embedding=embedder.model if embedder is not None else None,
        dimensao=embedder.dimension if embedder is not None else None,
        qtd_trechos=len(chunks),
        hash_corpus=digest,
        gerado_em=now().astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(chunks_path, content.encode("utf-8"))
    embeddings_path = out_dir / EMBEDDINGS_FILE
    if matrix is not None:
        _write_embeddings(embeddings_path, matrix)
    elif embeddings_path.exists():
        embeddings_path.unlink()
    _write_atomic(out_dir / MANIFEST_FILE, serialize_manifest(manifest).encode("utf-8"))
    reason = "corpus alterado" if not same_corpus else "embeddings gerados"
    return BuildResult(True, matrix is not None, len(chunks), digest, reason)


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gera o índice do RAG a partir do corpus.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--saida", type=Path, default=INDEX_DIR)
    parser.add_argument("--catalogo", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument(
        "--sem-embeddings",
        action="store_true",
        help="grava só trechos.jsonl e manifesto.json (backend lexico, sem GCP)",
    )
    parser.add_argument("--modelo", default=embedding_model_from_env() or DEFAULT_MODEL)
    parser.add_argument("--dimensao", type=int, default=DEFAULT_DIMENSION)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    catalog = [
        ProdutoCatalogo.model_validate(item)
        for item in json.loads(args.catalogo.read_text(encoding="utf-8"))
    ]
    embedder = (
        None if args.sem_embeddings else GeminiEmbedder(args.modelo, args.dimensao, retries=3)
    )
    try:
        result = build_index(args.corpus, args.saida, embedder=embedder, catalog=catalog)
    except CorpusInvalidError as error:
        for problem in error.problems:
            print(problem, file=sys.stderr)
        print(str(error), file=sys.stderr)
        return 1
    except EmbeddingUnavailableError as error:
        cause = f" (causa: {error.cause})" if error.cause else ""
        print(f"falha no embedding{cause}; índice não alterado", file=sys.stderr)
        return 2
    state = "gravado" if result.written else "inalterado"
    embeddings = "com embeddings" if result.embedded else "sem embeddings"
    print(
        f"índice {state} ({result.reason}): {result.chunk_count} trechos, {embeddings}, "
        f"hash_corpus={result.hash_corpus[:12]}…"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
