"""Ferramentas contra o BigQuery real, só leitura (``make test-bq``, precisa de ADC).

Marcados ``bq``: ficam fora do ``make test``. Pulados enquanto
``dominio/repositorio_bq.py`` (ciclo 001) não estiver em ``main``. Cobrem os
dois modos de leitura (``query`` e ``memoria``, contratos §4) passando pelo
servidor real. Nada é gravado.
"""

import pytest
from apoio_ferramentas import (
    DIR_OFICIAL,
    UUID_DESCONHECIDO,
    argumentos,
    chamar,
    codigo,
    ler_golden,
    sessao,
)

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    FERRAMENTAS,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    arquivo_golden,
)
from bussola_mcp.ferramentas.computations import build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureSearcher
from bussola_mcp.ferramentas.ports import ToolDependencies

pytestmark = pytest.mark.bq

repositorio_bq = pytest.importorskip(
    "bussola_mcp.dominio.repositorio_bq", reason="repositorio_bq.py chega com o ciclo 001"
)

MODOS = ("query", "memoria")
ENTRADA_GOLDEN = {
    "oportunidades_corte": {"top_n": 10},
    "simular_objetivo": {"valor_alvo": 30000.0, "prazo_meses": 24, "aporte_mensal": None},
    "comparar_cenarios": {"valor_alvo": 30000.0, "prazo_meses": 24},
}


@pytest.fixture(scope="module", params=MODOS)
def deps_bq(request) -> ToolDependencies:
    repositorio = repositorio_bq.RepositorioBigQuery(modo=request.param)
    return ToolDependencies(
        repository=repositorio,
        searcher=FixtureSearcher(DIR_OFICIAL),
        computations=build_computations(repositorio),
    )


@pytest.mark.parametrize("corte", CORTES_GOLDEN)
async def test_goldens_reproduzidos_com_bigquery(deps_bq, corte):
    async with sessao(deps=deps_bq) as cliente:
        for ferramenta in FERRAMENTAS_GOLDEN:
            args = argumentos(ferramenta, ate_anomes=corte, **ENTRADA_GOLDEN.get(ferramenta, {}))
            envelope = await chamar(cliente, ferramenta, args)
            golden = ler_golden(DIR_OFICIAL, arquivo_golden(ferramenta, corte))
            assert envelope == golden, ferramenta


async def test_usuarios_existem_e_desconhecido_nao(deps_bq):
    assert deps_bq.repository.usuario_existe(ID_ANCORA)
    assert deps_bq.repository.usuario_existe(ID_CONTROLE)
    async with sessao(deps=deps_bq) as cliente:
        for ferramenta in FERRAMENTAS:
            envelope = await chamar(
                cliente, ferramenta, argumentos(ferramenta, id_usuario=UUID_DESCONHECIDO)
            )
            assert codigo(envelope) == "USUARIO_INEXISTENTE", ferramenta


async def test_controle_tem_perfil_proprio(deps_bq):
    async with sessao(deps=deps_bq) as cliente:
        envelope = await chamar(
            cliente,
            "perfil_financeiro",
            argumentos("perfil_financeiro", id_usuario=ID_CONTROLE, ate_anomes=202512),
        )
    assert envelope != ler_golden(DIR_OFICIAL, arquivo_golden("perfil_financeiro", 202512))
