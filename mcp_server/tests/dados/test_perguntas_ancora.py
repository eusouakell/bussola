"""Fixa os números de ``specs/001-camada-dados-financeiros/perguntas-ancora.md`` (AC-01).

Roda sobre as fixtures v1 (iguais a ``bussola_dados``, conferido no ``make test-bq``).
"""

from pathlib import Path

import pytest

from bussola_mcp.contratos import ID_ANCORA
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.fakes import RepositorioFake

FIXTURES = Path(__file__).resolve().parents[3] / "contracts" / "fixtures"
ALVO, PRAZO, EXTRA = 60000.0, 24, 300.0

# corte → valores publicados em perguntas-ancora.md
ESPERADO = {
    202506: {
        "perfil": (6691.39, 4789.93, 1901.47, -2072.31, 19023.89, 17652.15),
        "capacidade": (1729.0, 1901.47, 1677.98, 1),
        "top3": [
            ("Restaurantes", 322.04, 96.61),
            ("Compras", 285.0, 85.5),
            ("Assinaturas", 108.02, 54.01),
        ],
        "falta": (1764.49, False, -35.49),
        "cabe": (2500.0, False, -771.0),
        "cenarios": [(691.6, 87), (1037.4, 58), (1660.85, 37)],
        "mais_300": (1337.4, 45, 391.6),
        "dividas": (6, 35.35, 56.07, 2256.42),
    },
    202512: {
        "perfil": (7451.27, 4614.52, 2836.75, -2072.31, 49320.95, 47597.68),
        "capacidade": (2489.44, 2836.75, 2093.0, 1),
        "top3": [
            ("Restaurantes", 345.35, 103.61),
            ("Compras", 294.05, 88.22),
            ("Assinaturas", 100.54, 50.27),
        ],
        "falta": (516.76, True, 1972.68),
        "cabe": (2500.0, False, -10.56),
        "cenarios": [(995.78, 61), (1493.66, 41), (2277.07, 27)],
        "mais_300": (1793.66, 34, 695.78),
        "dividas": (6, 1.47, 60.51, 42.01),
    },
}


def perfil_avisos(repo: RepositorioFake, ate: int) -> tuple[str, ...]:
    return tuple(metricas.perfil_financeiro(repo, ID_ANCORA, ate).avisos)


@pytest.fixture(scope="module")
def repo() -> RepositorioFake:
    return RepositorioFake(FIXTURES)


@pytest.mark.parametrize("ate", list(ESPERADO))
def test_perguntas_1_a_3(repo, ate: int) -> None:
    esperado = ESPERADO[ate]
    perfil = metricas.perfil_financeiro(repo, ID_ANCORA, ate).dados
    assert (
        perfil.renda_media,
        perfil.gasto_medio,
        perfil.sobra_media,
        perfil.saldo.minimo,
        perfil.saldo.maximo,
        perfil.saldo.atual,
    ) == esperado["perfil"]
    assert "Saldo ficou negativo em 2 meses do período." in perfil_avisos(repo, ate)
    cap = metricas.capacidade_poupanca(repo, ID_ANCORA, ate).dados
    assert (cap.sobra_mediana, cap.sobra_media, cap.desvio_padrao, cap.meses_negativos) == (
        esperado["capacidade"]
    )
    top3 = metricas.oportunidades_corte(repo, ID_ANCORA, ate, top_n=3).dados.categorias
    assert [(c.micro, c.media_mensal, c.economia_potencial_mensal) for c in top3] == (
        esperado["top3"]
    )
    assert not [c for c in top3 if "aluguel" in c.micro.lower()]


@pytest.mark.parametrize("ate", list(ESPERADO))
def test_perguntas_4_a_6(repo, ate: int) -> None:
    esperado = ESPERADO[ate]
    falta = metricas.simular_objetivo(
        repo, ID_ANCORA, ate, ALVO, prazo_meses=PRAZO, usar_saldo_atual=True
    ).dados
    assert (falta.aporte_mensal, falta.viavel, falta.folga_mensal) == esperado["falta"]
    cabe = metricas.simular_objetivo(repo, ID_ANCORA, ate, ALVO, prazo_meses=PRAZO).dados
    assert (cabe.aporte_mensal, cabe.viavel, cabe.folga_mensal) == esperado["cabe"]
    cenarios = metricas.comparar_cenarios(repo, ID_ANCORA, ate, ALVO, PRAZO).dados.cenarios
    assert [(c.aporte_mensal, c.prazo_meses) for c in cenarios] == esperado["cenarios"]
    assert len(cenarios[-1].cortes_sugeridos) == 9
    equilibrado = next(c for c in cenarios if c.nome == "equilibrado")
    mais = metricas.simular_objetivo(
        repo, ID_ANCORA, ate, ALVO, aporte_mensal=round(equilibrado.aporte_mensal + EXTRA, 2)
    ).dados
    assert (mais.aporte_mensal, mais.prazo_meses, mais.folga_mensal) == esperado["mais_300"]
    assert mais.viavel and mais.prazo_meses < equilibrado.prazo_meses


@pytest.mark.parametrize("ate", list(ESPERADO))
def test_pergunta_7(repo, ate: int) -> None:
    dividas = metricas.dividas_e_parcelas(repo, ID_ANCORA, ate).dados
    assert (
        len(dividas.parcelas_ativas),
        dividas.comprometimento_renda_pct,
        dividas.juros_pagos_media,
        max(p.valor for p in dividas.parcelas_ativas),
    ) == ESPERADO[ate]["dividas"]
