"""Adaptador ``DomainComputations`` (unidade): fábrica e tradução de falhas.

A igualdade com os goldens v1 sobre as fixtures oficiais fica em
``test_contrato_golden.py``, que usa a fábrica do servidor.
"""

import pytest
from apoio_ferramentas import DIR_OFICIAL

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, CodigoErro
from bussola_mcp.dominio.repositorio_bq import RepositoryUnavailableError
from bussola_mcp.ferramentas.computations import DomainComputations, build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository
from bussola_mcp.ferramentas.ports import BackendUnavailable, DomainError, FinancialComputations

CLIENTE_SEM_DADOS = "0b6f4f55-1c1e-4a57-9d3b-2f8a6f0c9e11"


class _RepositorioFora:
    """Repositório cujo backend caiu em toda leitura."""

    def __getattr__(self, _nome: str):
        def _falha(*_args, **_kwargs):
            raise RepositoryUnavailableError()

        return _falha


def _calculos() -> DomainComputations:
    return DomainComputations(FixtureRepository(DIR_OFICIAL))


def test_fabrica_devolve_o_adaptador_de_dominio_em_qualquer_modo():
    calculos = build_computations(FixtureRepository(DIR_OFICIAL), DIR_OFICIAL)
    assert isinstance(calculos, DomainComputations)
    assert isinstance(calculos, FinancialComputations)


def test_controle_recebe_os_proprios_numeros():
    """Com o domínio, o controle deixa de receber DADOS_INSUFICIENTES (D-06 do 003)."""
    ancora = _calculos().capacidade_poupanca(ID_ANCORA, 202512)
    controle = _calculos().capacidade_poupanca(ID_CONTROLE, 202512)
    assert controle.dados != ancora.dados
    assert controle.periodo.fim == 202512


def test_prazo_acima_de_360_meses_vira_prazo_implausivel():
    with pytest.raises(DomainError) as erro:
        _calculos().simular_objetivo(ID_ANCORA, 202512, 1_000_000.0, None, 1.0, False)
    assert erro.value.codigo is CodigoErro.PRAZO_IMPLAUSIVEL


def test_cliente_sem_dados_vira_dados_insuficientes():
    with pytest.raises(DomainError) as erro:
        _calculos().perfil_financeiro(CLIENTE_SEM_DADOS, 202512)
    assert erro.value.codigo is CodigoErro.DADOS_INSUFICIENTES


def test_mes_depois_do_corte_vira_entrada_invalida():
    with pytest.raises(DomainError) as erro:
        _calculos().resumo_mes(ID_ANCORA, 202503, 202506)
    assert erro.value.codigo is CodigoErro.ENTRADA_INVALIDA


def test_entrada_invalida_nao_chega_ao_repositorio():
    calculos = DomainComputations(_RepositorioFora())
    with pytest.raises(DomainError) as erro:
        calculos.perfil_financeiro("nao-e-uuid", 202512)
    assert erro.value.codigo is CodigoErro.ENTRADA_INVALIDA


def test_backend_fora_vira_indisponivel_sem_detalhe():
    calculos = DomainComputations(_RepositorioFora())
    with pytest.raises(BackendUnavailable) as erro:
        calculos.perfil_financeiro(ID_ANCORA, 202512)
    assert erro.value.mensagem is None
