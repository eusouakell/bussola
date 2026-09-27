"""Fixtures dos testes do RAG (ciclo 002). O apoio fica em ``rag_support``."""

import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from rag_support import (
    CATALOG_FILE,
    REPO_ROOT,
    FakeEmbedder,
    load_module,
    make_document,
    write_doc,
)

from bussola_mcp.contratos import ProdutoCatalogo


@pytest.fixture(scope="session")
def indexar() -> ModuleType:
    return load_module("rag_indexar", REPO_ROOT / "data" / "rag" / "indexar.py")


@pytest.fixture(scope="session")
def validar_corpus() -> ModuleType:
    return load_module("rag_validar_corpus", REPO_ROOT / "data" / "rag" / "validar_corpus.py")


@pytest.fixture(scope="session")
def rodar_eval() -> ModuleType:
    return load_module("rag_rodar_eval", REPO_ROOT / "eval" / "rag" / "rodar_eval.py")


@pytest.fixture(scope="session")
def catalog() -> list[ProdutoCatalogo]:
    items = json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    return [ProdutoCatalogo.model_validate(item) for item in items]


@pytest.fixture
def fake_embedder() -> type[FakeEmbedder]:
    return FakeEmbedder


@pytest.fixture
def document() -> Callable[..., str]:
    return make_document


@pytest.fixture
def add_doc() -> Callable[[Path, str, str, str], Path]:
    return write_doc


@pytest.fixture
def small_corpus(tmp_path: Path) -> Path:
    """Corpus válido e pequeno (3 temas, 5 trechos), sem produto."""
    root = tmp_path / "corpus"
    write_doc(
        root,
        "norma_bacen",
        "cheque-especial",
        make_document(
            "Cheque especial",
            "norma_bacen",
            [
                ("Limite de juros do cheque especial", "Os juros do cheque especial têm teto."),
                ("Uso consciente", "Use o cheque especial por poucos dias."),
            ],
            source_name="Conselho Monetário Nacional",
            source_reference="Resolução CMN nº 4.765/2019",
        ),
    )
    write_doc(
        root,
        "credito",
        "portabilidade",
        make_document(
            "Portabilidade",
            "credito",
            [("Portabilidade de crédito", "Leve o empréstimo para outro banco sem tarifa.")],
        ),
    )
    write_doc(
        root,
        "boas_praticas",
        "reserva",
        make_document(
            "Reserva",
            "boas_praticas",
            [
                ("Reserva de emergência", "Guarde de três a seis meses das despesas."),
                ("Onde guardar a reserva", "Prefira liquidez diária e baixo risco."),
            ],
        ),
    )
    return root
