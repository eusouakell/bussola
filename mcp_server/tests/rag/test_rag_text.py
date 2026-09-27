"""Normalização pt-BR da busca léxica (``bussola_mcp.rag.text``)."""

import pytest

from bussola_mcp.rag.text import STOPWORDS, fold, stem, tokenize


def test_fold_remove_acentos_e_caixa() -> None:
    assert fold("Cartão de CRÉDITO à vista") == "cartao de credito a vista"


@pytest.mark.parametrize(
    "variantes",
    [
        ("parcelar", "parcela", "parcelas", "parcelamento"),
        ("cartão", "cartões"),
        ("consignado", "consignada"),
        ("dívida", "dívidas"),
        ("renegociação", "renegociações"),
    ],
)
def test_variacoes_da_mesma_palavra_tem_o_mesmo_radical(variantes: tuple[str, ...]) -> None:
    radicais = {stem(fold(palavra)) for palavra in variantes}
    assert len(radicais) == 1, radicais


def test_cartao_nao_colide_com_carta() -> None:
    assert stem("cartao") != stem("carta")
    assert tokenize("cartão") != tokenize("carta de crédito")[:1]


def test_termos_curtos_e_numeros_ficam_inteiros() -> None:
    assert stem("cet") == "cet"
    assert stem("2019") == "2019"
    assert tokenize("Resolução 4765 de 2019") == [stem("resolucao"), "4765", "2019"]


def test_stopwords_e_letras_soltas_saem() -> None:
    assert tokenize("o que é que eu devo fazer com a minha") == []
    assert {"que", "para", "nao", "voce"} <= STOPWORDS


def test_tokenize_e_deterministico() -> None:
    texto = "Paguei só o mínimo da fatura do cartão"
    assert tokenize(texto) == tokenize(texto)
    assert tokenize(texto) == tokenize(texto.upper())
