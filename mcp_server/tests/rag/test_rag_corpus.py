"""Leitura e validação do corpus (``bussola_mcp.rag.corpus`` e ``validar_corpus.py``)."""

from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest
from rag_support import REAL_CORPUS

from bussola_mcp.contratos import ProdutoCatalogo, TemaConhecimento, contem_taxa
from bussola_mcp.rag.corpus import (
    CorpusFormatError,
    load_corpus,
    parse_document,
    validate_corpus,
)

MakeDoc = Callable[..., str]
AddDoc = Callable[[Path, str, str, str], Path]


def _one_problem(problems: list[str], fragment: str) -> str:
    matching = [p for p in problems if fragment in p]
    assert matching, problems
    return matching[0]


# --- leitura -----------------------------------------------------------------


def test_corpus_valido_vira_um_trecho_por_secao(small_corpus: Path) -> None:
    assert validate_corpus(small_corpus) == []
    chunks = load_corpus(small_corpus)
    assert [c.trecho_id for c in chunks] == [
        "reserva#1",
        "reserva#2",
        "portabilidade#1",
        "cheque-especial#1",
        "cheque-especial#2",
    ]
    cheque = next(c for c in chunks if c.trecho_id == "cheque-especial#1")
    assert cheque.doc_id == "cheque-especial"
    assert cheque.titulo == "Limite de juros do cheque especial"
    assert cheque.tema is TemaConhecimento.NORMA_BACEN
    assert cheque.texto == "Os juros do cheque especial têm teto."
    assert cheque.fonte.nome == "Conselho Monetário Nacional"
    assert cheque.fonte.referencia == "Resolução CMN nº 4.765/2019"
    assert cheque.fonte.url is None


def test_linhas_do_mesmo_paragrafo_sao_juntadas(
    tmp_path: Path, document: MakeDoc, add_doc: AddDoc
) -> None:
    path = add_doc(
        tmp_path,
        "credito",
        "quebra",
        document(sections=[("Seção", "primeira linha\nsegunda linha\n\nnovo parágrafo")]),
    )
    parsed = parse_document(path)
    assert parsed.sections[0].text == "primeira linha segunda linha\n\nnovo parágrafo"


def test_sem_cabecalho_levanta_erro_de_formato(tmp_path: Path, add_doc: AddDoc) -> None:
    path = add_doc(tmp_path, "credito", "sem-cabecalho", "## Seção\n\nTexto.\n")
    with pytest.raises(CorpusFormatError, match="sem cabeçalho"):
        parse_document(path)


# --- validação ---------------------------------------------------------------


def test_sem_fonte_referencia_falha_nomeando_o_arquivo(
    small_corpus: Path, document: MakeDoc, add_doc: AddDoc
) -> None:
    add_doc(small_corpus, "credito", "sem-fonte", document(source_reference=None))
    problem = _one_problem(validate_corpus(small_corpus), "fonte_referencia")
    assert problem == "credito/sem-fonte.md: campo obrigatório ausente: fonte_referencia"


def test_script_validar_corpus_falha_nomeando_o_arquivo(
    small_corpus: Path,
    document: MakeDoc,
    add_doc: AddDoc,
    validar_corpus,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = tmp_path / "catalogo_vazio.json"
    catalog.write_text("[]", encoding="utf-8")
    assert validar_corpus.main(["--corpus", str(small_corpus), "--catalogo", str(catalog)]) == 0
    assert "corpus válido: 3 documentos, 5 trechos" in capsys.readouterr().out

    add_doc(small_corpus, "credito", "sem-fonte", document(source_reference=None))
    assert validar_corpus.main(["--corpus", str(small_corpus), "--catalogo", str(catalog)]) == 1
    assert "credito/sem-fonte.md: campo obrigatório ausente: fonte_referencia" in (
        capsys.readouterr().err
    )


@pytest.mark.parametrize(
    ("topic", "folder", "fragment"),
    [
        ("astrologia", "credito", "tema inválido: astrologia"),
        ("norma_bacen", "credito", "difere da pasta"),
    ],
)
def test_tema_invalido_ou_fora_da_pasta(
    small_corpus: Path,
    document: MakeDoc,
    add_doc: AddDoc,
    topic: str,
    folder: str,
    fragment: str,
) -> None:
    add_doc(small_corpus, folder, "tema-errado", document(topic=topic))
    assert _one_problem(validate_corpus(small_corpus), fragment).startswith(
        f"{folder}/tema-errado.md: "
    )


def test_pasta_de_tema_desconhecida(small_corpus: Path, document: MakeDoc, add_doc: AddDoc) -> None:
    add_doc(small_corpus, "diversos", "solto", document(topic="credito"))
    _one_problem(validate_corpus(small_corpus), "diversos/solto.md: pasta de tema inválida")


def test_doc_id_duplicado(small_corpus: Path, document: MakeDoc, add_doc: AddDoc) -> None:
    add_doc(small_corpus, "boas_praticas", "portabilidade", document(topic="boas_praticas"))
    problem = _one_problem(validate_corpus(small_corpus), "doc_id duplicado")
    assert "credito/portabilidade.md" in problem


@pytest.mark.parametrize(
    ("sections", "fragment"),
    [
        ([("Seção vazia", "")], "seção 1 vazia"),
        ([], "nenhuma seção ##"),
    ],
)
def test_secao_vazia_ou_ausente(
    small_corpus: Path,
    document: MakeDoc,
    add_doc: AddDoc,
    sections: list[tuple[str, str]],
    fragment: str,
) -> None:
    add_doc(small_corpus, "credito", "vazio", document(sections=sections))
    _one_problem(validate_corpus(small_corpus), f"credito/vazio.md: {fragment}")


def test_texto_antes_da_primeira_secao(
    small_corpus: Path, document: MakeDoc, add_doc: AddDoc
) -> None:
    content = document().replace("---\n\n## ", "---\n\nTexto solto.\n\n## ", 1)
    add_doc(small_corpus, "credito", "preambulo", content)
    _one_problem(validate_corpus(small_corpus), "texto antes da primeira seção")


def test_campo_desconhecido_e_cabecalho_malformado(
    small_corpus: Path, document: MakeDoc, add_doc: AddDoc
) -> None:
    add_doc(small_corpus, "credito", "extra", document(extra_header="autor: alguém"))
    add_doc(small_corpus, "credito", "malformado", document(extra_header="linha sem dois pontos"))
    problems = validate_corpus(small_corpus)
    _one_problem(problems, "credito/extra.md: campo desconhecido no cabeçalho: autor")
    _one_problem(problems, "credito/malformado.md: linha")


def test_corpus_vazio(tmp_path: Path) -> None:
    assert validate_corpus(tmp_path) == [f"{tmp_path}: corpus vazio"]


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Cliente 36a21505-d6d4-42d3-b319-d51a133c7269 pagou.", "UUID"),
        ("CPF 123.456.789-09 do titular.", "CPF"),
        ("Escreva para fulano@exemplo.com.br hoje.", "e-mail"),
        ("Cartão 4111 1111 1111 1111 bloqueado.", "número de cartão"),
        ("Conta 12345678901 encerrada.", "número longo"),
    ],
)
def test_dado_de_cliente_ou_identificador_e_recusado(
    small_corpus: Path, document: MakeDoc, add_doc: AddDoc, text: str, label: str
) -> None:
    add_doc(small_corpus, "credito", "sensivel", document(sections=[("Seção", text)]))
    _one_problem(
        validate_corpus(small_corpus),
        f"credito/sensivel.md: contém dado de cliente ou identificador ({label}",
    )


# --- tema produto -------------------------------------------------------------


@pytest.fixture
def product_catalog() -> list[ProdutoCatalogo]:
    return [
        ProdutoCatalogo(
            produto_id="reserva_objetivo",
            nome="Reserva por objetivo",
            categoria="Metas & reserva",
            uso="Criar meta e acompanhar objetivo",
            cuidado="Não citar rentabilidade",
            fonte_oficial="https://exemplo.test/reserva-objetivo",
            acao_simulada=True,
        )
    ]


def _product_doc(document: MakeDoc, text: str, url: str | None) -> str:
    return document(
        "Reserva por objetivo",
        "produto",
        [("Reserva por objetivo: o que é", text)],
        source_name="Catálogo de produtos",
        source_reference="Página oficial do produto",
        source_url=url,
    )


def test_produto_valido(
    tmp_path: Path, document: MakeDoc, add_doc: AddDoc, product_catalog: list[ProdutoCatalogo]
) -> None:
    add_doc(
        tmp_path,
        "produto",
        "reserva_objetivo",
        _product_doc(
            document, "Separa dinheiro por meta.", "https://exemplo.test/reserva-objetivo"
        ),
    )
    assert validate_corpus(tmp_path, product_catalog) == []


@pytest.mark.parametrize("marker", ["%", "R$", "a.a.", "a.m."])
def test_produto_nao_pode_ter_taxa_nem_valor(
    tmp_path: Path,
    document: MakeDoc,
    add_doc: AddDoc,
    product_catalog: list[ProdutoCatalogo],
    marker: str,
) -> None:
    text = f"Rende 1 {marker} ao guardar."
    add_doc(
        tmp_path,
        "produto",
        "reserva_objetivo",
        _product_doc(document, text, product_catalog[0].fonte_oficial),
    )
    _one_problem(validate_corpus(tmp_path, product_catalog), f"taxa ou valor ({marker!r})")


def test_produto_exige_fonte_url_igual_ao_catalogo(
    tmp_path: Path, document: MakeDoc, add_doc: AddDoc, product_catalog: list[ProdutoCatalogo]
) -> None:
    add_doc(
        tmp_path, "produto", "reserva_objetivo", _product_doc(document, "Separa dinheiro.", None)
    )
    _one_problem(validate_corpus(tmp_path, product_catalog), "tema produto exige fonte_url")

    add_doc(
        tmp_path,
        "produto",
        "reserva_objetivo",
        _product_doc(document, "Separa dinheiro.", "https://www.exemplo.com/reserva-objetivo"),
    )
    _one_problem(validate_corpus(tmp_path, product_catalog), "difere da fonte oficial do catálogo")


def test_produto_fora_do_catalogo_e_catalogo_sem_documento(
    tmp_path: Path, document: MakeDoc, add_doc: AddDoc, product_catalog: list[ProdutoCatalogo]
) -> None:
    add_doc(
        tmp_path,
        "produto",
        "poupanca-magica",
        _product_doc(document, "Produto inventado.", "https://exemplo.test/x"),
    )
    problems = validate_corpus(tmp_path, product_catalog)
    _one_problem(problems, "produto/poupanca-magica.md: produto fora de contracts/")
    _one_problem(problems, "produto/reserva_objetivo.md: produto do catálogo sem documento")


# --- corpus real ---------------------------------------------------------------


def test_corpus_real_e_valido_com_o_catalogo(catalog: list[ProdutoCatalogo]) -> None:
    assert validate_corpus(REAL_CORPUS, catalog) == []


def test_corpus_real_tem_ao_menos_30_trechos_nos_tres_temas() -> None:
    chunks = load_corpus(REAL_CORPUS)
    by_topic = Counter(c.tema for c in chunks)
    knowledge = [
        TemaConhecimento.NORMA_BACEN,
        TemaConhecimento.CREDITO,
        TemaConhecimento.BOAS_PRATICAS,
    ]
    assert sum(by_topic[t] for t in knowledge) >= 30
    assert all(by_topic[t] > 0 for t in knowledge)


def test_corpus_real_cobre_os_assuntos_do_ciclo(catalog: list[ProdutoCatalogo]) -> None:
    doc_ids = {c.doc_id for c in load_corpus(REAL_CORPUS)}
    required = {
        "cartao-rotativo",
        "custo-efetivo-total",
        "cheque-especial",
        "portabilidade-credito",
        "renegociacao-dividas",
        "superendividamento",
        "reserva-emergencia",
        "orcamento-mensal",
        "ordem-quitacao",
    }
    assert required <= doc_ids
    assert {p.produto_id for p in catalog} <= doc_ids


def test_produtos_do_corpus_real_seguem_o_catalogo(catalog: list[ProdutoCatalogo]) -> None:
    official = {p.produto_id: p.fonte_oficial for p in catalog}
    products = [c for c in load_corpus(REAL_CORPUS) if c.tema is TemaConhecimento.PRODUTO]
    assert products
    for chunk in products:
        assert chunk.fonte.url == official[chunk.doc_id]
        assert not contem_taxa(chunk.texto), chunk.trecho_id
        assert not contem_taxa(chunk.titulo), chunk.trecho_id
