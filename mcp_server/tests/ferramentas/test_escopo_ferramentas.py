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
from bussola_mcp.dominio import metricas
from bussola_mcp.ferramentas.computations import DomainComputations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.ports import ToolDependencies

OUTRO = {ID_ANCORA: ID_CONTROLE, ID_CONTROLE: ID_ANCORA}


def _deps(fixtures, buscador=None):
    repositorio = RepositorioEspiao(FixtureRepository(fixtures))
    return ToolDependencies(
        repository=repositorio,
        searcher=buscador or FixtureSearcher(fixtures),
        computations=DomainComputations(repositorio),
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
    """O controle recebe os próprios números, nunca os do âncora.

    ``referencia_coorte`` fica de fora: é agregada por faixa de renda, sem dado
    individual, e dois clientes da mesma faixa recebem a mesma referência.
    """
    async with sessao(fixtures_sinteticas) as cliente:
        for ferramenta in (f for f in FERRAMENTAS_CLIENTE if f != "referencia_coorte"):
            ancora = await chamar(cliente, ferramenta, argumentos(ferramenta, ID_ANCORA))
            controle = await chamar(cliente, ferramenta, argumentos(ferramenta, ID_CONTROLE))
            assert "dados" in ancora, ferramenta
            assert controle.get("dados") != ancora["dados"], ferramenta


@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE])
async def test_referencia_coorte_usa_a_faixa_de_cada_cliente(fixtures_sinteticas, id_usuario):
    """A faixa vem da renda média do próprio cliente no corte (a mesma do perfil)."""
    async with sessao(fixtures_sinteticas) as cliente:
        perfil = await chamar(
            cliente, "perfil_financeiro", argumentos("perfil_financeiro", id_usuario)
        )
        coorte = await chamar(
            cliente, "referencia_coorte", argumentos("referencia_coorte", id_usuario)
        )
    faixa = metricas.income_band(perfil["dados"]["renda_media"])
    assert coorte["dados"]["faixa_renda"] == faixa


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
