"""Valida o corpus do RAG de conhecimento (ciclo 002, contratos §4).

Uso (a partir da raiz do repositório)::

    uv run --project mcp_server python data/rag/validar_corpus.py

Regras (implementadas em ``bussola_mcp.rag.corpus.validate_corpus``):

- cabeçalho completo e tema válido (igual ao nome da pasta);
- ``doc_id`` único e nenhuma seção vazia;
- nenhum UUID, CPF, CNPJ, e-mail ou número longo no texto;
- tema ``produto``: ``fonte_url`` igual à fonte oficial do catálogo, um
  documento por ``produto_id`` e nenhum ``%``, ``a.a.``, ``a.m.`` ou ``R$``.

Sai com código 1 e lista ``<arquivo>: <problema>`` quando algo falha.
"""

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from bussola_mcp.contratos import ProdutoCatalogo
from bussola_mcp.rag.corpus import load_corpus, validate_corpus

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO_ROOT / "data" / "rag" / "corpus"
DEFAULT_CATALOG = REPO_ROOT / "contracts" / "catalogo_produtos.json"


def load_catalog(path: Path) -> list[ProdutoCatalogo]:
    return [ProdutoCatalogo.model_validate(item) for item in json.loads(path.read_text("utf-8"))]


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida o corpus do RAG.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--catalogo", type=Path, default=DEFAULT_CATALOG)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    problems = validate_corpus(args.corpus, load_catalog(args.catalogo))
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"corpus inválido: {len(problems)} problema(s)", file=sys.stderr)
        return 1
    chunks = load_corpus(args.corpus)
    by_topic = Counter(chunk.tema.value for chunk in chunks)
    documents = len({chunk.doc_id for chunk in chunks})
    summary = ", ".join(f"{topic}={count}" for topic, count in sorted(by_topic.items()))
    print(f"corpus válido: {documents} documentos, {len(chunks)} trechos ({summary})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
