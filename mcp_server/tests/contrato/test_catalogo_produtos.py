"""Catálogo de produtos (``contracts/catalogo_produtos.json``) e tema ``produto`` do RAG.

Contratos §3 e §4: recorte de 8 produtos de ``docs/catalogo/``, sem taxa nem condição
comercial, com ``fonte_oficial``. Os trechos ``produto`` do corpus apontam para o catálogo.
"""

import json
from pathlib import Path

import pytest

from bussola_mcp.contratos import (
    MARCADORES_TAXA,
    ProdutoCatalogo,
    TemaConhecimento,
    TrechoCorpus,
    contem_taxa,
)

DIR_CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"

# produto_id → acao_simulada (docs/catalogo/ §2, recorte do MVP).
PRODUTOS_MVP: dict[str, bool] = {
    "reserva_objetivo": True,
    "controle_gastos": True,
    "credito_imobiliario": True,
    "consorcio_imoveis": True,
    "consorcio_veiculos": True,
    "renegociacao": True,
    "cdb_renda_fixa": False,
    "lci_lca": False,
}


def _ler(relativo: str):
    return json.loads((DIR_CONTRATOS / relativo).read_text("utf-8"))


@pytest.fixture(scope="module")
def catalogo() -> list[ProdutoCatalogo]:
    return [ProdutoCatalogo.model_validate(p) for p in _ler("catalogo_produtos.json")]


@pytest.fixture(scope="module")
def trechos_produto() -> list[TrechoCorpus]:
    trechos = [TrechoCorpus.model_validate(t) for t in _ler("fixtures/rag/trechos_exemplo.json")]
    return [t for t in trechos if t.tema is TemaConhecimento.PRODUTO]


def test_catalogo_tem_os_8_produtos_do_mvp(catalogo):
    ids = [p.produto_id for p in catalogo]
    assert len(ids) == len(set(ids))
    assert {p.produto_id: p.acao_simulada for p in catalogo} == PRODUTOS_MVP


def test_catalogo_cita_fonte_oficial(catalogo):
    for produto in catalogo:
        assert produto.fonte_oficial.startswith("https://"), produto.produto_id
        assert produto.nome.strip() and produto.uso.strip() and produto.cuidado.strip()


@pytest.mark.parametrize("marcador", MARCADORES_TAXA)
def test_contem_taxa(marcador):
    assert contem_taxa(f"rende 1 {marcador}")
    assert not contem_taxa("sem condição comercial")


def test_catalogo_sem_taxas_nem_condicoes():
    texto = (DIR_CONTRATOS / "catalogo_produtos.json").read_text("utf-8")
    assert not contem_taxa(texto)


def test_trechos_produto_apontam_para_o_catalogo(catalogo, trechos_produto):
    fontes = {p.produto_id: p.fonte_oficial for p in catalogo}
    assert trechos_produto, "o corpus precisa de ao menos um trecho produto (contratos §8)"
    for trecho in trechos_produto:
        assert trecho.doc_id in fontes, trecho.trecho_id
        assert trecho.fonte.url == fontes[trecho.doc_id], trecho.trecho_id
        assert not contem_taxa(trecho.texto), trecho.trecho_id
