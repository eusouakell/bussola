"""Integração com o 003: ``criar_buscador`` pela porta ``BuscadorContexto``, como a ferramenta.

A ferramenta ``buscar_contexto_financeiro`` (003) monta o buscador uma vez,
chama ``buscar(pergunta, k, tema)`` e embrulha os trechos no envelope
``Resposta[DadosBuscarContexto]``. Uma falha de embedding vira
``INDISPONIVEL``. Estes testes reproduzem esse fluxo sem tocar no ``server.py``.
"""

import inspect
import json
from typing import Any

import numpy as np
import pytest
from rag_support import REPO_ROOT, FakeEmbedder

from bussola_mcp.contratos import (
    ANOMES_MAX,
    ANOMES_MIN,
    AVISO_CONHECIMENTO,
    AVISO_SEM_TRECHOS,
    ID_ANCORA,
    CodigoErro,
    DadosBuscarContexto,
    EntradaBuscarContexto,
    Fonte,
    FonteTrecho,
    Periodo,
    ProdutoCatalogo,
    Resposta,
    TemaConhecimento,
    Trecho,
    contem_taxa,
    envelope_erro,
)
from bussola_mcp.dominio.interfaces import BuscadorContexto
from bussola_mcp.rag import (
    BuscadorLexico,
    BuscadorNumpy,
    EmbeddingUnavailableError,
    InvalidIndexError,
    criar_buscador,
)
from bussola_mcp.rag.index import INDEX_DIR, load_chunks, load_embeddings, load_manifest

TOOL = "buscar_contexto_financeiro"


def _tool(buscador: BuscadorContexto, argumentos: dict[str, Any]) -> dict[str, Any]:
    """Réplica do que a ferramenta do 003 faz com o buscador (sem MCP)."""
    entrada = EntradaBuscarContexto.model_validate(argumentos)
    try:
        trechos = buscador.buscar(entrada.pergunta, entrada.k, entrada.tema)
    except EmbeddingUnavailableError:
        return envelope_erro(CodigoErro.INDISPONIVEL)
    avisos = [AVISO_CONHECIMENTO] if trechos else [AVISO_CONHECIMENTO, AVISO_SEM_TRECHOS]
    resposta = Resposta[DadosBuscarContexto](
        dados=DadosBuscarContexto(trechos=trechos),
        fonte=Fonte(
            ferramenta=TOOL,
            tabelas=[],
            periodo=Periodo(inicio=ANOMES_MIN, fim=entrada.ate_anomes),
        ),
        avisos=avisos,
    )
    return resposta.model_dump(mode="json")


def _args(pergunta: str, **extra: Any) -> dict[str, Any]:
    return {"id_usuario": ID_ANCORA, "ate_anomes": ANOMES_MAX, "pergunta": pergunta, **extra}


def _row_embedder(trecho_id: str) -> FakeEmbedder:
    """Embedder que devolve o vetor do próprio trecho: ele tem de sair em primeiro."""
    manifest = load_manifest(INDEX_DIR)
    ids = [c.trecho_id for c in load_chunks(INDEX_DIR, manifest)]
    row = load_embeddings(INDEX_DIR, manifest)[ids.index(trecho_id)]
    assert manifest.modelo_embedding and manifest.dimensao
    return FakeEmbedder(
        manifest.modelo_embedding,
        manifest.dimensao,
        override=lambda texts: np.tile(row, (len(texts), 1)),
    )


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    monkeypatch.delenv("EMBEDDING_MODEL", raising=False)


# --- montagem -------------------------------------------------------------------


def test_backend_padrao_e_lexico_e_implementa_a_porta() -> None:
    buscador = criar_buscador()
    assert isinstance(buscador, BuscadorLexico)
    assert isinstance(buscador, BuscadorContexto)


@pytest.mark.parametrize(
    ("env", "expected"),
    [("lexico", BuscadorLexico), (" LEXICO ", BuscadorLexico), ("", BuscadorLexico)],
)
def test_rag_backend_do_ambiente(monkeypatch: pytest.MonkeyPatch, env: str, expected: type) -> None:
    monkeypatch.setenv("RAG_BACKEND", env)
    assert isinstance(criar_buscador(None), expected)


def test_rag_backend_numpy_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAG_BACKEND", "Numpy")
    buscador = criar_buscador(embedder=_row_embedder("reserva_objetivo#1"))
    assert isinstance(buscador, BuscadorNumpy)
    assert isinstance(buscador, BuscadorContexto)


def test_rag_backend_invalido(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="RAG_BACKEND inválido"):
        criar_buscador("faiss")
    monkeypatch.setenv("RAG_BACKEND", "vertex")
    with pytest.raises(ValueError, match="RAG_BACKEND inválido"):
        criar_buscador()


def test_numpy_recusa_subir_com_modelo_divergente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-005")
    with pytest.raises(InvalidIndexError):
        criar_buscador("numpy", embedder=_row_embedder("reserva_objetivo#1"))


def test_assinatura_de_buscar_segue_a_porta() -> None:
    expected = list(inspect.signature(BuscadorContexto.buscar).parameters)
    for cls in (BuscadorLexico, BuscadorNumpy):
        assert list(inspect.signature(cls.buscar).parameters) == expected


# --- fluxo da ferramenta ------------------------------------------------------------


def test_fluxo_da_ferramenta_com_lexico() -> None:
    envelope = _tool(
        criar_buscador("lexico"), _args("Existe limite para os juros do cheque especial?", k=3)
    )
    parsed = Resposta[DadosBuscarContexto].model_validate(json.loads(json.dumps(envelope)))
    assert parsed.fonte == Fonte(
        ferramenta=TOOL, tabelas=[], periodo=Periodo(inicio=ANOMES_MIN, fim=ANOMES_MAX)
    )
    assert parsed.avisos == [AVISO_CONHECIMENTO]
    ids = [t.trecho_id for t in parsed.dados.trechos]
    assert 1 <= len(ids) <= 3 and "cheque-especial#1" in ids
    assert "sql" not in json.dumps(envelope).lower()


def test_fluxo_sem_resultado_traz_aviso() -> None:
    envelope = _tool(criar_buscador("lexico"), _args("previsão do tempo"))
    assert envelope["dados"] == {"trechos": []}
    assert envelope["avisos"] == [AVISO_CONHECIMENTO, AVISO_SEM_TRECHOS]


def test_fluxo_da_ferramenta_com_numpy() -> None:
    buscador = criar_buscador("numpy", embedder=_row_embedder("reserva_objetivo#1"))
    envelope = _tool(buscador, _args("Onde guardo o dinheiro da entrada?", k=3))
    trechos = envelope["dados"]["trechos"]
    assert trechos[0]["trecho_id"] == "reserva_objetivo#1"
    assert trechos[0]["score"] == pytest.approx(1.0, abs=1e-3)

    filtered = _tool(buscador, _args("Onde guardo?", k=5, tema="norma_bacen"))
    assert {t["tema"] for t in filtered["dados"]["trechos"]} <= {"norma_bacen"}


def test_falha_de_embedding_vira_indisponivel_sem_detalhe() -> None:
    manifest = load_manifest(INDEX_DIR)
    assert manifest.modelo_embedding and manifest.dimensao
    broken = FakeEmbedder(
        manifest.modelo_embedding,
        manifest.dimensao,
        error=RuntimeError("503 UNAVAILABLE generativelanguage.googleapis.com"),
    )
    envelope = _tool(criar_buscador("numpy", embedder=broken), _args("cheque especial"))
    assert envelope == envelope_erro(CodigoErro.INDISPONIVEL)
    assert "googleapis" not in json.dumps(envelope)


# --- contrato ---------------------------------------------------------------------


@pytest.mark.parametrize("backend", ["lexico", "numpy"])
def test_trecho_devolvido_segue_o_contrato(backend: str) -> None:
    buscador = criar_buscador(backend, embedder=_row_embedder("cheque-especial#1"))
    trechos = buscador.buscar("juros do cheque especial", 5)
    assert trechos
    for trecho in trechos:
        assert type(trecho) is Trecho
        assert set(trecho.model_dump()) == set(Trecho.model_fields)
        assert isinstance(trecho.fonte, FonteTrecho)
        assert isinstance(trecho.tema, TemaConhecimento)
        assert trecho.score > 0
        assert trecho.trecho_id.startswith(f"{trecho.doc_id}#")
        assert Trecho.model_validate_json(trecho.model_dump_json()) == trecho


def test_trechos_de_produto_sem_taxa_e_com_fonte_oficial(
    catalog: list[ProdutoCatalogo],
) -> None:
    official = {p.produto_id: p.fonte_oficial for p in catalog}
    buscador = criar_buscador("lexico")
    seen: set[str] = set()
    for product in catalog:
        for trecho in buscador.buscar(
            f"{product.nome} {product.uso}", 10, TemaConhecimento.PRODUTO
        ):
            assert trecho.tema is TemaConhecimento.PRODUTO
            assert trecho.fonte.url == official[trecho.doc_id]
            assert not contem_taxa(trecho.texto) and not contem_taxa(trecho.titulo)
            seen.add(trecho.doc_id)
    assert seen == set(official)


def test_trechos_das_fixtures_do_000_existem_no_indice() -> None:
    fixture = REPO_ROOT / "contracts" / "fixtures" / "rag" / "trechos_exemplo.json"
    expected = {item["trecho_id"] for item in json.loads(fixture.read_text(encoding="utf-8"))}
    indexed = {c.trecho_id for c in load_chunks(INDEX_DIR)}
    assert expected <= indexed
