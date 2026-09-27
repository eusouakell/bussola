"""Testes unitários do adaptador provisório sobre os golden e dos adaptadores de fixtures."""

import json
import shutil

import pytest
from apoio_ferramentas import DIR_OFICIAL

from bussola_mcp.contratos import (
    ID_ANCORA,
    ID_CONTROLE,
    CodigoErro,
    DadosOportunidadesCorte,
)
from bussola_mcp.dominio.fakes import dir_fixtures_padrao
from bussola_mcp.ferramentas.computations import DomainComputations, build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.golden_adapter import (
    CANONICAL_INPUT_WARNING,
    CANONICAL_TARGET,
    CANONICAL_TERM,
    COHORT_WARNING,
    DEMO_WARNING_PREFIX,
    EARLIER_CUT_WARNING,
    GoldenFixtureComputations,
    brl_label,
    month_label,
    normalize_label,
)
from bussola_mcp.ferramentas.ports import BackendUnavailable, DomainError, FinancialComputations


def _calculos(fixtures):
    return GoldenFixtureComputations(fixtures, FixtureRepository(fixtures))


def test_adaptador_implementa_a_porta(fixtures_sinteticas):
    assert isinstance(_calculos(fixtures_sinteticas), FinancialComputations)
    assert isinstance(
        build_computations(FixtureRepository(fixtures_sinteticas)), FinancialComputations
    )


def test_entrada_canonica_vem_do_contrato():
    assert (CANONICAL_TARGET, CANONICAL_TERM) == (30000.0, 24)
    assert "R$ 30.000,00" in CANONICAL_INPUT_WARNING and "24 meses" in CANONICAL_INPUT_WARNING


@pytest.mark.parametrize("aviso", [EARLIER_CUT_WARNING, CANONICAL_INPUT_WARNING])
def test_avisos_de_demonstracao_falam_com_o_cliente(aviso):
    """BUG-06: prefixo estável, sem jargão interno e sem ``anomes`` cru."""
    assert aviso.startswith(DEMO_WARNING_PREFIX)
    for interno in ("mock", "valor_alvo", "prazo_meses", "202506", "ate_anomes", "golden"):
        assert interno not in aviso


@pytest.mark.parametrize(
    "anomes, esperado",
    [(202501, "janeiro/2025"), (202506, "junho/2025"), (202512, "dezembro/2025")],
)
def test_month_label(anomes, esperado):
    assert month_label(anomes) == esperado


@pytest.mark.parametrize(
    "valor, esperado", [(30000.0, "R$ 30.000,00"), (1234.5, "R$ 1.234,50"), (0.0, "R$ 0,00")]
)
def test_brl_label(valor, esperado):
    assert brl_label(valor) == esperado


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Lazer", "lazer"),
        ("  LAZER ", "lazer"),
        ("Educação", "educacao"),
        ("Casa  e  Lar", "casa e lar"),
    ],
)
def test_normalize_label(texto, esperado):
    assert normalize_label(texto) == esperado


@pytest.mark.parametrize(
    "ate_anomes, corte, avisos",
    [
        (202506, 202506, ()),
        (202512, 202512, ()),
        (202507, 202506, (EARLIER_CUT_WARNING,)),
        (202511, 202506, (EARLIER_CUT_WARNING,)),
    ],
)
def test_escolha_do_golden_por_corte(ate_anomes, corte, avisos):
    assert GoldenFixtureComputations._golden_cut(ate_anomes) == (corte, avisos)


@pytest.mark.parametrize("ate_anomes", [202501, 202505])
def test_corte_antes_de_202506_sem_golden(ate_anomes):
    with pytest.raises(BackendUnavailable):
        GoldenFixtureComputations._golden_cut(ate_anomes)


def test_oportunidades_truncadas_sem_alterar_o_cache(fixtures_sinteticas):
    calculos = _calculos(fixtures_sinteticas)
    tres = calculos.oportunidades_corte(ID_ANCORA, 202512, 3)
    dez = calculos.oportunidades_corte(ID_ANCORA, 202512, 10)
    assert isinstance(tres.dados, DadosOportunidadesCorte)
    assert len(tres.dados.categorias) == 3
    assert len(dez.dados.categorias) == 10


@pytest.mark.parametrize(
    "kwargs, com_aviso",
    [
        ({"valor_alvo": 30000.0, "prazo_meses": 24, "aporte_mensal": None}, False),
        ({"valor_alvo": 30000.0, "prazo_meses": 12, "aporte_mensal": None}, True),
        ({"valor_alvo": 30000.0, "prazo_meses": None, "aporte_mensal": 500.0}, True),
    ],
)
def test_simulacao_nao_canonica_ganha_aviso(fixtures_sinteticas, kwargs, com_aviso):
    resultado = _calculos(fixtures_sinteticas).simular_objetivo(
        ID_ANCORA, 202512, usar_saldo_atual=False, **kwargs
    )
    assert (CANONICAL_INPUT_WARNING in resultado.avisos) is com_aviso


def test_usar_saldo_atual_nao_e_canonico(fixtures_sinteticas):
    resultado = _calculos(fixtures_sinteticas).simular_objetivo(
        ID_ANCORA, 202512, 30000.0, 24, None, True
    )
    assert CANONICAL_INPUT_WARNING in resultado.avisos


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


def test_controle_sem_golden_cai_no_dominio(fixtures_sinteticas):
    """BUG-05: sem golden gravado o cliente é calculado, não recusado."""
    calculos = _calculos(fixtures_sinteticas)
    dominio = DomainComputations(FixtureRepository(fixtures_sinteticas))
    for metodo in ("perfil_financeiro", "capacidade_poupanca", "dividas_e_parcelas"):
        resultado = getattr(calculos, metodo)(ID_CONTROLE, 202512)
        assert resultado.dados == getattr(dominio, metodo)(ID_CONTROLE, 202512).dados, metodo
        assert EARLIER_CUT_WARNING not in resultado.avisos
    assert calculos.has_golden(ID_ANCORA) and not calculos.has_golden(ID_CONTROLE)


@pytest.mark.parametrize(
    "ate_anomes, meses, sobra_mediana", [(202506, 6, 2208.24), (202512, 12, 2824.05)]
)
def test_controle_oficial_tem_historico_e_diagnostico(ate_anomes, meses, sobra_mediana):
    """BUG-05: a persona de controle tem 12 meses; o corte não muda isso."""
    calculos = GoldenFixtureComputations(DIR_OFICIAL, FixtureRepository(DIR_OFICIAL))
    perfil = calculos.perfil_financeiro(ID_CONTROLE, ate_anomes)
    capacidade = calculos.capacidade_poupanca(ID_CONTROLE, ate_anomes)
    assert (perfil.dados.meses_considerados, capacidade.dados.meses_considerados) == (meses, meses)
    assert (perfil.dados.sobra_mediana, capacidade.dados.sobra_mediana) == (
        sobra_mediana,
        sobra_mediana,
    )
    assert perfil.periodo.model_dump() == {"inicio": 202501, "fim": ate_anomes}


def test_controle_oficial_simula_com_a_propria_capacidade():
    """A simulação do controle usa a capacidade dele, sem o aviso de entrada canônica."""
    calculos = GoldenFixtureComputations(DIR_OFICIAL, FixtureRepository(DIR_OFICIAL))
    resultado = calculos.simular_objetivo(ID_CONTROLE, 202512, 30000.0, 24, None, False)
    assert resultado.dados.premissas["capacidade_mensal"] == 2824.05
    assert CANONICAL_INPUT_WARNING not in resultado.avisos


def test_sem_nenhum_mes_ainda_e_dados_insuficientes(fixtures_sinteticas):
    """Única razão honesta de ``DADOS_INSUFICIENTES``: nenhum mês até o corte (regra 2)."""
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


def test_golden_invalido_fica_indisponivel(fixtures_sinteticas):
    (fixtures_sinteticas / "ferramentas" / "capacidade_poupanca__ate_202512.json").write_text(
        json.dumps({"dados": {"campo": "errado"}}), "utf-8"
    )
    with pytest.raises(BackendUnavailable):
        _calculos(fixtures_sinteticas).capacidade_poupanca(ID_ANCORA, 202512)


def test_usuarios_invalidos_ficam_indisponiveis(fixtures_sinteticas):
    (fixtures_sinteticas / "usuarios.json").write_text("[{", "utf-8")
    calculos = GoldenFixtureComputations(
        fixtures_sinteticas, FixtureRepository(fixtures_sinteticas)
    )
    with pytest.raises(BackendUnavailable):
        calculos.referencia_coorte(ID_ANCORA, 202512, "Lazer")


def test_fixtures_criadas_depois_passam_a_ser_servidas(tmp_path, fixtures_sinteticas):
    """Só leituras com sucesso ficam em cache (``make fixtures`` com o servidor no ar)."""
    destino = tmp_path / "depois"
    destino.mkdir()
    repositorio = FixtureRepository(destino)
    buscador = FixtureSearcher(destino)
    calculos = GoldenFixtureComputations(destino, repositorio)
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
