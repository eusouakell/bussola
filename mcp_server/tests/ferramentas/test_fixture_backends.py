"""Adaptadores de fixtures (``FixtureRepository``, ``FixtureSearcher``) e o domínio sobre eles.

Substitui ``test_golden_adapter.py``. O adaptador provisório de goldens foi
removido (R7 da varredura de Clean Architecture): ``build_computations`` devolve
``DomainComputations`` em todo modo desde o ciclo 001, então as regras D-03 a D-06
— escolha de golden por corte, aviso de entrada não canônica, truncagem do golden
de oportunidades — não existem mais, e os testes delas foram embora com a regra.

O que ficou aqui é o que nunca foi do adaptador: cache e falha alta dos
adaptadores de fixtures, e as regressões do BUG-05 sobre a persona de controle
(que o adaptador já calculava pelo domínio).
"""

import json
import shutil

import pytest
from apoio_ferramentas import DIR_OFICIAL

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, CodigoErro
from bussola_mcp.dominio.fakes import dir_fixtures_padrao
from bussola_mcp.dominio.metricas import COHORT_WARNING
from bussola_mcp.ferramentas.computations import DomainComputations, build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.ports import BackendUnavailable, DomainError, FinancialComputations


def _calculos(fixtures) -> DomainComputations:
    return DomainComputations(FixtureRepository(fixtures))


def test_a_fabrica_devolve_sempre_o_adaptador_de_dominio(fixtures_sinteticas):
    calculos = build_computations(FixtureRepository(fixtures_sinteticas))
    assert isinstance(calculos, DomainComputations)
    assert isinstance(calculos, FinancialComputations)


def test_referencia_coorte_ignora_caixa_e_acento(fixtures_sinteticas):
    resultado = _calculos(fixtures_sinteticas).referencia_coorte(ID_CONTROLE, 202506, " MORADIA ")
    assert resultado.dados.model_dump() == {
        "faixa_renda": "3k_6k",
        "macro": "Moradia",
        "media": 1500.0,
        "mediana": 1500.0,
        "qtd_usuarios": 10,
    }
    assert resultado.periodo.model_dump() == {"inicio": 202501, "fim": 202506}
    assert resultado.avisos == (COHORT_WARNING,)


@pytest.mark.parametrize(
    "ate_anomes, meses, sobra_mediana", [(202506, 6, 2208.24), (202512, 12, 2824.05)]
)
def test_controle_oficial_tem_historico_e_diagnostico(ate_anomes, meses, sobra_mediana):
    """BUG-05: a persona de controle tem 12 meses; o corte não muda isso."""
    calculos = _calculos(DIR_OFICIAL)
    perfil = calculos.perfil_financeiro(ID_CONTROLE, ate_anomes)
    capacidade = calculos.capacidade_poupanca(ID_CONTROLE, ate_anomes)
    assert (perfil.dados.meses_considerados, capacidade.dados.meses_considerados) == (meses, meses)
    assert (perfil.dados.sobra_mediana, capacidade.dados.sobra_mediana) == (
        sobra_mediana,
        sobra_mediana,
    )
    assert perfil.periodo.model_dump() == {"inicio": 202501, "fim": ate_anomes}


def test_controle_oficial_simula_com_a_propria_capacidade():
    """A simulação do controle usa a capacidade dele."""
    resultado = _calculos(DIR_OFICIAL).simular_objetivo(
        ID_CONTROLE, 202512, 30000.0, 24, None, False
    )
    assert resultado.dados.premissas["capacidade_mensal"] == 2824.05


def test_sem_nenhum_mes_ainda_e_dados_insuficientes(fixtures_sinteticas):
    """Nenhum mês de ``perfil_mensal`` até o corte → ``DADOS_INSUFICIENTES``."""
    caminho = fixtures_sinteticas / "bussola_dados" / "perfil_mensal.json"
    linhas = json.loads(caminho.read_text("utf-8"))
    caminho.write_text(
        json.dumps([linha for linha in linhas if linha["id_usuario"] != ID_CONTROLE]), "utf-8"
    )
    calculos = _calculos(fixtures_sinteticas)
    for metodo in ("perfil_financeiro", "capacidade_poupanca"):
        with pytest.raises(DomainError) as info:
            getattr(calculos, metodo)(ID_CONTROLE, 202512)
        assert info.value.codigo == CodigoErro.DADOS_INSUFICIENTES, metodo


def test_usuarios_invalidos_ficam_indisponiveis(fixtures_sinteticas):
    (fixtures_sinteticas / "usuarios.json").write_text("[{", "utf-8")
    with pytest.raises(BackendUnavailable):
        FixtureRepository(fixtures_sinteticas).usuario_existe(ID_ANCORA)


def test_fixtures_criadas_depois_passam_a_ser_servidas(tmp_path, fixtures_sinteticas):
    """Só leituras com sucesso ficam em cache (``make fixtures`` com o servidor no ar)."""
    destino = tmp_path / "depois"
    destino.mkdir()
    repositorio = FixtureRepository(destino)
    buscador = FixtureSearcher(destino)
    calculos = DomainComputations(repositorio)
    with pytest.raises(BackendUnavailable):
        repositorio.usuario_existe(ID_ANCORA)
    with pytest.raises(BackendUnavailable):
        buscador.buscar("cet", 3)
    with pytest.raises(BackendUnavailable):
        calculos.capacidade_poupanca(ID_ANCORA, 202512)

    shutil.copytree(fixtures_sinteticas, destino, dirs_exist_ok=True)

    assert repositorio.usuario_existe(ID_ANCORA) is True
    assert [t.trecho_id for t in buscador.buscar("O que é o CET?", 3)] == ["cet#1"]
    assert calculos.capacidade_poupanca(ID_ANCORA, 202512).dados is not None


def test_tabela_corrompida_e_depois_corrigida(fixtures_sinteticas):
    caminho = fixtures_sinteticas / "bussola_dados" / "parcelas.json"
    original = caminho.read_text("utf-8")
    repositorio = FixtureRepository(fixtures_sinteticas)
    caminho.write_text("[{", "utf-8")
    with pytest.raises(BackendUnavailable):
        repositorio.parcelas(ID_ANCORA, 202512)
    caminho.write_text(original, "utf-8")
    assert len(repositorio.parcelas(ID_ANCORA, 202512)) == 12


@pytest.mark.parametrize(
    "metodo, args",
    [
        ("perfil_mensal", (ID_ANCORA, 202512)),
        ("gastos_categoria", (ID_ANCORA, 202512)),
        ("entradas_categoria", (ID_ANCORA, 202512)),
        ("recorrentes", (ID_ANCORA, 202512)),
        ("parcelas", (ID_ANCORA, 202512)),
        ("categorias", ()),
        ("referencia_coorte", ("6k_10k",)),
    ],
)
def test_tabela_ausente_fica_indisponivel(fixtures_sinteticas, metodo, args):
    (fixtures_sinteticas / "bussola_dados" / f"{metodo}.json").unlink()
    with pytest.raises(BackendUnavailable):
        getattr(FixtureRepository(fixtures_sinteticas), metodo)(*args)


def test_repositorio_de_fixtures_respeita_o_corte(fixtures_sinteticas):
    linhas = FixtureRepository(fixtures_sinteticas).perfil_mensal(ID_ANCORA, 202503)
    assert [linha.anomes for linha in linhas] == [202501, 202502, 202503]
    assert {linha.id_usuario for linha in linhas} == {ID_ANCORA}


def test_padrao_e_o_diretorio_oficial():
    assert FixtureRepository().fixtures_dir == dir_fixtures_padrao()
    assert FixtureSearcher().fixtures_dir == dir_fixtures_padrao()
