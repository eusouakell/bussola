"""``BuscadorLexico``: BM25 com normalização pt-BR, cobertura mínima e desempate."""

from pathlib import Path

import pytest

from bussola_mcp.contratos import FonteTrecho, TemaConhecimento, Trecho, TrechoCorpus
from bussola_mcp.rag import BuscadorLexico
from bussola_mcp.rag.corpus import load_corpus

FONTE = FonteTrecho(nome="Equipe Bússola", referencia="Conteúdo educativo")


def _chunk(
    trecho_id: str, title: str, text: str, topic: TemaConhecimento = TemaConhecimento.CREDITO
) -> TrechoCorpus:
    return TrechoCorpus(
        doc_id=trecho_id.split("#")[0],
        trecho_id=trecho_id,
        titulo=title,
        tema=topic,
        texto=text,
        fonte=FONTE,
    )


@pytest.fixture
def searcher(small_corpus: Path) -> BuscadorLexico:
    return BuscadorLexico(chunks=load_corpus(small_corpus))


def test_ranking_traz_o_trecho_mais_relevante(searcher: BuscadorLexico) -> None:
    result = searcher.buscar("Qual o limite de juros do cheque especial?", 3)
    assert result[0].trecho_id == "cheque-especial#1"
    assert all(isinstance(t, Trecho) for t in result)
    assert [t.score for t in result] == sorted((t.score for t in result), reverse=True)
    assert all(t.score > 0 for t in result)


def test_filtro_por_tema(searcher: BuscadorLexico) -> None:
    question = "reserva de emergência e cheque especial"
    assert {t.tema for t in searcher.buscar(question, 5)} == {
        TemaConhecimento.NORMA_BACEN,
        TemaConhecimento.BOAS_PRATICAS,
    }
    only = searcher.buscar(question, 5, TemaConhecimento.BOAS_PRATICAS)
    assert only and {t.tema for t in only} == {TemaConhecimento.BOAS_PRATICAS}
    assert searcher.buscar(question, 5, TemaConhecimento.PRODUTO) == []


def test_limite_k(searcher: BuscadorLexico) -> None:
    question = "reserva de emergência e cheque especial"
    assert len(searcher.buscar(question, 1)) == 1
    assert searcher.buscar(question, 0) == []


@pytest.mark.parametrize("question", ["", "   ", "o que é que eu devo fazer?", "?!"])
def test_pergunta_vazia_ou_so_stopwords_devolve_vazio(
    searcher: BuscadorLexico, question: str
) -> None:
    assert searcher.buscar(question, 5) == []


def test_empate_desfeito_por_trecho_id() -> None:
    chunks = [
        _chunk("b#1", "Tarifa", "Tarifa bancária cobrada na conta."),
        _chunk("a#1", "Tarifa", "Tarifa bancária cobrada na conta."),
        _chunk("c#1", "Outro assunto", "Planejamento de metas."),
    ]
    result = BuscadorLexico(chunks=chunks).buscar("tarifa bancária", 5)
    assert [t.trecho_id for t in result] == ["a#1", "b#1"]
    assert result[0].score == result[1].score


def test_titulo_pesa_mais_que_o_corpo() -> None:
    chunks = [
        _chunk("corpo#1", "Assunto geral", "Explica a portabilidade entre bancos."),
        _chunk("titulo#1", "Portabilidade", "Explica o assunto entre bancos."),
        _chunk("outro#1", "Metas", "Defina metas com prazo."),
    ]
    result = BuscadorLexico(chunks=chunks).buscar("portabilidade", 5)
    assert [t.trecho_id for t in result] == ["titulo#1", "corpo#1"]


def test_cobertura_minima_descarta_casamento_fraco() -> None:
    chunks = [
        _chunk("tempo#1", "Prazo", "Quanto tempo leva a portabilidade."),
        _chunk("metas#1", "Metas", "Defina metas com prazo e valor."),
        _chunk("reserva#1", "Reserva", "Guarde dinheiro para emergências."),
    ]
    searcher = BuscadorLexico(chunks=chunks)
    # "previsão" não existe no corpus: casar só "tempo" não basta.
    assert searcher.buscar("previsão do tempo", 5) == []
    assert BuscadorLexico(chunks=chunks, single_term_coverage=0.0).buscar("previsão do tempo", 5)


def test_indice_versionado_nao_responde_fora_do_dominio() -> None:
    searcher = BuscadorLexico()
    for question in ("previsão do tempo", "Qual a previsão do tempo para amanhã?"):
        assert searcher.buscar(question, 5) == []


def test_indice_versionado_responde_pergunta_de_produto() -> None:
    result = BuscadorLexico().buscar("Onde guardo o dinheiro da entrada?", 3)
    assert "cofrinhos#1" in [t.trecho_id for t in result]
