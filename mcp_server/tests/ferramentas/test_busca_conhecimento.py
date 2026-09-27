"""``buscar_contexto_financeiro`` sobre o corpus curado (sem golden, Q-17 do 000).

Integração com o servidor real e o ``BuscadorFake`` do contrato, sobre o corpus
sintético do conftest e sobre o corpus oficial de ``contracts/fixtures/rag/``.
"""

import logging

import pytest
from apoio_ferramentas import BUSCA, DIR_OFICIAL, argumentos, chamar, sessao

from bussola_mcp import server
from bussola_mcp.contratos import (
    ANOMES_MIN,
    AVISO_CONHECIMENTO,
    AVISO_SEM_TRECHOS,
    ID_ANCORA,
    CodigoErro,
    DadosBuscarContexto,
    Resposta,
)
from bussola_mcp.ferramentas.ports import ToolDependencies
from bussola_mcp.rag import BuscadorLexico, EmbeddingUnavailableError


async def _buscar(fixtures, **extra):
    async with sessao(fixtures) as cliente:
        return await chamar(cliente, BUSCA, argumentos(BUSCA, **extra))


def _ids(envelope):
    return [t["trecho_id"] for t in envelope["dados"]["trechos"]]


@pytest.mark.parametrize(
    "pergunta, tema, esperado",
    [
        ("juros do rotativo do cartão", None, ["teto-juros#1", "rotativo#1", "cet#1"]),
        ("O que é o CET?", None, ["cet#1"]),
        ("minhas dívidas", "credito", ["registrato#1"]),
        ("dinheiro da meta", "produto", ["reserva_objetivo#1"]),
    ],
)
async def test_trechos_esperados_no_corpus_sintetico(fixtures_sinteticas, pergunta, tema, esperado):
    envelope = await _buscar(fixtures_sinteticas, pergunta=pergunta, tema=tema)
    assert _ids(envelope) == esperado
    assert envelope["avisos"] == [AVISO_CONHECIMENTO]
    Resposta[DadosBuscarContexto].model_validate(envelope)


async def test_sem_trecho_relevante(fixtures_sinteticas):
    """Cenário §7: ``trechos = []`` e ``AVISO_SEM_TRECHOS``."""
    envelope = await _buscar(fixtures_sinteticas, pergunta="Quanto gasto com restaurantes?")
    assert envelope["dados"] == {"trechos": []}
    assert envelope["avisos"] == [AVISO_CONHECIMENTO, AVISO_SEM_TRECHOS]


async def test_tema_filtra_os_trechos(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, pergunta="minhas dívidas", tema="norma_bacen")
    assert envelope["dados"]["trechos"] == []
    assert AVISO_SEM_TRECHOS in envelope["avisos"]


async def test_k_limita_a_quantidade(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, pergunta="juros do rotativo do cartão", k=1)
    assert _ids(envelope) == ["teto-juros#1"]


async def test_fonte_da_busca(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, ate_anomes=202507)
    assert envelope["fonte"] == {
        "ferramenta": BUSCA,
        "tabelas": [],
        "periodo": {"inicio": ANOMES_MIN, "fim": 202507},
    }


async def test_trechos_trazem_fonte_e_score(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, pergunta="juros do rotativo do cartão")
    for trecho in envelope["dados"]["trechos"]:
        assert trecho["fonte"]["nome"] and trecho["fonte"]["referencia"]
        assert 0 < trecho["score"] <= 1


async def test_tema_produto_no_corpus_oficial_traz_url():
    """Cenário §7: ``tema="produto"`` aceito; todos os trechos do tema e com ``fonte.url``."""
    envelope = await _buscar(
        DIR_OFICIAL, pergunta="Como separar o dinheiro dos meus sonhos?", tema="produto"
    )
    trechos = envelope["dados"]["trechos"]
    assert trechos
    assert all(t["tema"] == "produto" for t in trechos)
    assert all(t["fonte"]["url"] for t in trechos)


async def test_rotativo_no_corpus_oficial():
    envelope = await _buscar(DIR_OFICIAL, pergunta="Como funciona o rotativo do cartão de crédito?")
    ids = _ids(envelope)
    assert ids and ids[0].startswith("cartao-rotativo#")
    assert all(
        t["tema"] in {"norma_bacen", "credito", "boas_praticas", "produto"}
        for t in envelope["dados"]["trechos"]
    )


async def test_pergunta_com_espacos_nas_bordas_e_aceita(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, pergunta="   O que é o CET?   ")
    assert _ids(envelope) == ["cet#1"]


async def test_pergunta_no_limite_de_500_caracteres(fixtures_sinteticas):
    envelope = await _buscar(fixtures_sinteticas, pergunta=("cet " * 125)[:500])
    assert "dados" in envelope


async def test_busca_valida_o_cliente_da_sessao(fixtures_sinteticas):
    """Mesmo sem dado de cliente, id e corte são validados (escopo da sessão)."""
    envelope = await _buscar(fixtures_sinteticas, id_usuario=ID_ANCORA, ate_anomes=202501)
    assert envelope["fonte"]["periodo"] == {"inicio": 202501, "fim": 202501}


class _BuscadorSemEmbedding:
    """Buscador cujo serviço de embedding caiu (backend ``numpy`` do 002)."""

    def buscar(self, pergunta, k, tema):
        raise EmbeddingUnavailableError("ServiceUnavailable")


async def test_embedding_fora_vira_indisponivel_sem_traceback(caplog):
    base = server.build_dependencies(DIR_OFICIAL)
    deps = ToolDependencies(
        repository=base.repository,
        searcher=_BuscadorSemEmbedding(),
        computations=base.computations,
    )
    with caplog.at_level(logging.WARNING, logger="bussola_mcp"):
        async with sessao(deps=deps) as cliente:
            envelope = await chamar(cliente, BUSCA, argumentos(BUSCA, pergunta="O que é o CET?"))
    assert envelope["erro"]["codigo"] == CodigoErro.INDISPONIVEL
    eventos = [getattr(r, "evento", None) for r in caplog.records]
    assert "backend_indisponivel" in eventos
    assert "ferramenta_falhou" not in eventos


def test_modo_real_usa_o_buscador_do_002(monkeypatch):
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    assert isinstance(server._real_searcher(None), BuscadorLexico)
