"""Apoio aos testes do RAG (ciclo 002): corpus temporário, embedder falso e scripts.

Os testes importam daqui (``from rag_support import ...``), e não do
``conftest``, para não depender de qual ``conftest`` está em ``sys.modules``.

Nada aqui chama a rede. O embedder falso é determinístico: um saco de
palavras (termos de :func:`bussola_mcp.rag.text.tokenize`) espalhado em
``dimension`` colunas por ``crc32``, então textos com termos em comum ficam
próximos no cosseno.
"""

import importlib.util
import zlib
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType

import numpy as np

from bussola_mcp.rag.text import tokenize

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_CORPUS = REPO_ROOT / "data" / "rag" / "corpus"
CATALOG_FILE = REPO_ROOT / "contracts" / "catalogo_produtos.json"


class FakeEmbedder:
    """:class:`~bussola_mcp.rag.embedding.Embedder` determinístico, sem rede."""

    def __init__(
        self,
        model: str = "modelo-falso",
        dimension: int = 64,
        *,
        error: Exception | None = None,
        override: Callable[[Sequence[str]], np.ndarray] | None = None,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.error = error
        self.override = override
        self.calls: list[tuple[list[str], str]] = []

    def vector(self, text: str) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float32)
        for term in tokenize(text):
            vector[zlib.crc32(term.encode()) % self.dimension] += 1.0
        return vector

    def embed(self, texts: Sequence[str], task_type: str) -> np.ndarray:
        self.calls.append((list(texts), task_type))
        if self.error is not None:
            raise self.error
        if self.override is not None:
            return self.override(texts)
        return np.stack([self.vector(t) for t in texts]).astype(np.float32)


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_document(
    title: str = "Documento de teste",
    topic: str = "credito",
    sections: Sequence[tuple[str, str]] = (("Seção um", "Texto educativo da seção um."),),
    *,
    source_name: str | None = "Equipe Bússola",
    source_reference: str | None = "Conteúdo educativo da equipe (não é norma)",
    source_url: str | None = None,
    extra_header: str = "",
) -> str:
    """Markdown de um documento do corpus, com cabeçalho e seções ``##``."""
    lines = ["---", f"titulo: {title}", f"tema: {topic}"]
    if source_name is not None:
        lines.append(f"fonte_nome: {source_name}")
    if source_reference is not None:
        lines.append(f"fonte_referencia: {source_reference}")
    if source_url is not None:
        lines.append(f"fonte_url: {source_url}")
    if extra_header:
        lines.append(extra_header)
    lines += ["---", ""]
    for section_title, text in sections:
        lines += [f"## {section_title}", "", text, ""]
    return "\n".join(lines)


def write_doc(root: Path, topic: str, doc_id: str, content: str) -> Path:
    """Grava ``<root>/<topic>/<doc_id>.md`` e devolve o caminho."""
    path = root / topic / f"{doc_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
