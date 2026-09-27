"""Escopo por cliente e corte (critério §6): o id do controle nunca traz dados do âncora.

Um repositório espião registra cada leitura: toda leitura com id usa o id da
chamada e o corte pedido. O buscador nunca recebe id nem corte (Q-17 do 000).
"""

import json

import pytest
from apoio_ferramentas import (
    BUSCA,
    FERRAMENTAS_CLIENTE,
    TODAS,
    BuscadorEspiao,
    RepositorioEspiao,
    argumentos,
    chamar,
    sessao,
)

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, id_usuario_valido
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.golden_adapter import GoldenFixtureComputations
from bussola_mcp.ferramentas.ports import ToolDependencies

OUTRO = {ID_ANCORA: ID_CONTROLE, ID_CONTROLE: ID_ANCORA}


def _deps(fixtures, buscador=None):
    repositorio = RepositorioEspiao(FixtureRepository(fixtures))
    return ToolDependencies(
        repository=repositorio,
        searcher=buscador or FixtureSearcher(fixtures),
        computations=GoldenFixtureComputations(fixtures, repositorio),
    )


@pytest.mark.parametrize("ate_anomes", [202506, 202512])
@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE])
async def test_leituras_so_com_o_id_e_o_corte_da_chamada(
    fixtures_sinteticas, id_usuario, ate_anomes
):
    deps = _deps(fixtures_sinteticas)
    async with sessao(deps=deps) as cliente:
        for ferramenta in TODAS:
            args = argumentos(ferramenta, id_usuario=id_usuario, ate_anomes=ate_anomes)
            await chamar(cliente, ferramenta, args)
    chamadas = deps.repository.chamadas
    assert chamadas, "o espião deveria registrar leituras"
    for nome, args in chamadas:
        ids = [a for a in args if id_usuario_valido(a)]
        assert ids in ([], [id_usuario]), (nome, args)
        if nome not in ("usuario_existe", "categorias", "referencia_coorte"):
            assert ids == [id_usuario], nome
            cortes = [a for a in args if isinstance(a, int) and 202501 <= a <= 202512]
            assert cortes and max(cortes) <= ate_anomes, (nome, args)


@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE])
async def test_saidas_nunca_citam_o_outro_cliente(fixtures_sinteticas, id_usuario):
    async with sessao(fixtures_sinteticas) as cliente:
        for ferramenta in TODAS:
            envelope = await chamar(cliente, ferramenta, argumentos(ferramenta, id_usuario))
            texto = json.dumps(envelope, ensure_ascii=False).lower()
            assert OUTRO[id_usuario] not in texto, ferramenta
            assert id_usuario not in texto, ferramenta


async def test_controle_nao_recebe_os_numeros_do_ancora(fixtures_sinteticas):
    """Vale para qualquer adaptador: hoje o controle recebe erro (D-06), depois do 001
    recebe os próprios números, nunca os do âncora."""
    async with sessao(fixtures_sinteticas) as cliente:
        for ferramenta in FERRAMENTAS_CLIENTE:
            ancora = await chamar(cliente, ferramenta, argumentos(ferramenta, ID_ANCORA))
            controle = await chamar(cliente, ferramenta, argumentos(ferramenta, ID_CONTROLE))
            assert "dados" in ancora, ferramenta
            assert controle.get("dados") != ancora["dados"], ferramenta


async def test_referencia_coorte_usa_a_faixa_de_cada_cliente(fixtures_sinteticas):
    """Nas fixtures sintéticas, âncora em 6k_10k e controle em 3k_6k."""
    async with sessao(fixtures_sinteticas) as cliente:
        ancora = await chamar(
            cliente, "referencia_coorte", argumentos("referencia_coorte", ID_ANCORA)
        )
        controle = await chamar(
            cliente, "referencia_coorte", argumentos("referencia_coorte", ID_CONTROLE)
        )
    assert ancora["dados"]["faixa_renda"] == "6k_10k"
    assert controle["dados"]["faixa_renda"] == "3k_6k"


@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE])
async def test_buscador_nunca_recebe_id_nem_corte(fixtures_sinteticas, id_usuario):
    buscador = BuscadorEspiao()
    async with sessao(deps=_deps(fixtures_sinteticas, buscador)) as cliente:
        envelope = await chamar(
            cliente,
            BUSCA,
            argumentos(BUSCA, id_usuario, ate_anomes=202503, k=3, tema="credito"),
        )
    assert envelope["fonte"]["tabelas"] == []
    assert buscador.chamadas == [
        {"pergunta": "Como funciona o rotativo do cartão?", "k": 3, "tema": "credito"}
    ]


async def test_busca_devolve_os_mesmos_trechos_para_os_dois_clientes(fixtures_sinteticas):
    """O corpus é conhecimento geral: não há trecho por cliente."""
    async with sessao(fixtures_sinteticas) as cliente:
        ancora = await chamar(cliente, BUSCA, argumentos(BUSCA, ID_ANCORA))
        controle = await chamar(cliente, BUSCA, argumentos(BUSCA, ID_CONTROLE))
    assert ancora["dados"] == controle["dados"]
