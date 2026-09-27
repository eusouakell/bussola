"""Coerência entre as ferramentas de simulação e ``dominio/simulacao.py`` (ciclo 001).

Pulado enquanto o 001 não estiver em ``main``. Depois da troca em
``computations.build_computations`` (plan.md, "Troca pós-001"), o cenário do
ciclo §7 (R$ 60.000 em 24 meses) passa a ser conferido contra
``aporte_para_prazo``.
"""

from typing import Any

import pytest
from apoio_ferramentas import DIR_OFICIAL, argumentos, chamar, ler_golden, sessao

from bussola_mcp.contratos import ENTRADA_CANONICA_SIMULACAO, brl
from bussola_mcp.ferramentas.computations import build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository
from bussola_mcp.ferramentas.golden_adapter import (
    CANONICAL_INPUT_WARNING,
    GoldenFixtureComputations,
)

simulacao = pytest.importorskip(
    "bussola_mcp.dominio.simulacao", reason="dominio/simulacao.py chega com o ciclo 001"
)


def _aporte(resultado: Any) -> float:
    valor = resultado["aporte_mensal"] if isinstance(resultado, dict) else resultado.aporte_mensal
    return brl(valor)


def test_golden_canonico_bate_com_aporte_para_prazo():
    golden = ler_golden(DIR_OFICIAL, "simular_objetivo__ate_202512.json")
    esperado = simulacao.aporte_para_prazo(
        ENTRADA_CANONICA_SIMULACAO["valor_alvo"], ENTRADA_CANONICA_SIMULACAO["prazo_meses"]
    )
    assert golden["dados"]["modo"] == "prazo"
    assert golden["dados"]["aporte_mensal"] == _aporte(esperado)


async def test_cenario_do_ciclo_60_mil_em_24_meses_usa_o_dominio():
    if isinstance(build_computations(FixtureRepository(DIR_OFICIAL)), GoldenFixtureComputations):
        pytest.skip("build_computations ainda usa o adaptador de goldens (troca pós-001)")
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente,
            "simular_objetivo",
            argumentos("simular_objetivo", valor_alvo=60000.0, prazo_meses=24),
        )
    assert "erro" not in envelope
    dados = envelope["dados"]
    assert dados["modo"] == "prazo"
    assert dados["valor_alvo"] == 60000.0
    assert dados["prazo_meses"] == 24
    assert dados["aporte_mensal"] == _aporte(simulacao.aporte_para_prazo(60000.0, 24))
    assert CANONICAL_INPUT_WARNING not in envelope["avisos"]
