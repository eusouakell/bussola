"""Testes de ``dominio/metricas.py`` sobre as fixtures sintéticas (ciclo 001, T009).

- Valores conhecidos no corte 202506 (âncora) e 202512 (controle).
- AC-05: nenhum dado depois do corte muda o resultado (futuro "envenenado").
- TS-05 e constituição III: escopo por cliente e corte refeitos em ``metricas``,
  mesmo com um repositório que ignora os filtros.
- AC-04: ``id_usuario`` malicioso é rejeitado antes de qualquer leitura.
"""

import importlib.util
import json
import shutil
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from bussola_mcp.contratos import (
    FERRAMENTAS,
    ID_ANCORA,
    ID_CONTROLE,
    MENSAGENS_ERRO,
    TABELAS_FERRAMENTA,
    CodigoErro,
    FaixaRenda,
    Resposta,
)
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.dominio.metricas import (
    COHORT_WARNING,
    ImplausibleTermError,
    InsufficientDataError,
    InvalidInputError,
    MetricError,
    MetricResult,
    build_envelope,
    income_band,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CORTE = 202506
FUTURE_FACTOR = 1000.0

Metric = Callable[..., MetricResult]

# (ferramenta, função, argumentos além de repo/id/corte)
SPECS: list[tuple[str, Metric, dict[str, Any]]] = [
    ("perfil_financeiro", metricas.perfil_financeiro, {}),
    ("capacidade_poupanca", metricas.capacidade_poupanca, {}),
    ("oportunidades_corte", metricas.oportunidades_corte, {"top_n": 10}),
    ("dividas_e_parcelas", metricas.dividas_e_parcelas, {}),
    (
        "simular_objetivo",
        metricas.simular_objetivo,
        {"valor_alvo": 30000.0, "prazo_meses": 24},
    ),
    (
        "comparar_cenarios",
        metricas.comparar_cenarios,
        {"valor_alvo": 30000.0, "prazo_meses": 24},
    ),
    ("resumo_mes", metricas.resumo_mes, {"anomes": 202503}),
    ("referencia_coorte", metricas.referencia_coorte, {"categoria": "Moradia"}),
]
SPEC_IDS = [spec[0] for spec in SPECS]


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / "data" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"bussola_scripts_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(fixtures_sinteticas: Path) -> RepositorioFake:
    return RepositorioFake(fixtures_sinteticas)


def _envelope(ferramenta: str, fn: Metric, repo: Any, id_usuario: str, ate: int, **kw: Any):
    return build_envelope(ferramenta, fn(repo, id_usuario, ate, **kw))


# ---------------------------------------------------------------------------
# Repositórios auxiliares
# ---------------------------------------------------------------------------


class LeakyRepository:
    """Ignora corte e escopo: devolve linhas dos dois clientes e dos 12 meses, invertidas."""

    def __init__(self, base: RepositorioFake) -> None:
        self._base = base

    def _both(self, method: str) -> list[Any]:
        linhas = [
            *getattr(self._base, method)(ID_ANCORA, 202512),
            *getattr(self._base, method)(ID_CONTROLE, 202512),
        ]
        return linhas[::-1]

    def usuario_existe(self, id_usuario: str) -> bool:
        return True

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[Any]:
        return self._both("perfil_mensal")

    def gastos_categoria(
        self, id_usuario: str, ate_anomes: int, desde_anomes: int | None = None
    ) -> list[Any]:
        return self._both("gastos_categoria")

    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[Any]:
        return self._both("entradas_categoria")

    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Any]:
        return self._both("recorrentes")

    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Any]:
        return self._both("parcelas")

    def categorias(self) -> list[Any]:
        return self._base.categorias()[::-1]

    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[Any]:
        return [ref for faixa in FaixaRenda for ref in self._base.referencia_coorte(faixa.value)]


class SpyRepository:
    """Registra qualquer acesso: o teste exige que nenhum aconteça."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name: str) -> Any:
        self.calls.append(name)
        raise AssertionError(f"repositório acessado: {name}")


def _poison_future(origem: Path, destino: Path, corte: int) -> Path:
    """Cópia das fixtures com todo valor numérico depois de ``corte`` multiplicado."""
    shutil.copytree(origem, destino)
    for arquivo in (destino / "bussola_dados").glob("*.json"):
        conteudo = json.loads(arquivo.read_text(encoding="utf-8"))
        linhas = conteudo["linhas"] if isinstance(conteudo, dict) else conteudo
        for linha in linhas:
            if linha.get("anomes", 0) > corte:
                for campo, valor in linha.items():
                    if isinstance(valor, float):
                        linha[campo] = round(valor * FUTURE_FACTOR, 2)
        arquivo.write_text(json.dumps(conteudo), encoding="utf-8")
    return destino


# ---------------------------------------------------------------------------
# Valores conhecidos
# ---------------------------------------------------------------------------


def test_perfil_financeiro_no_corte(repo):
    resultado = metricas.perfil_financeiro(repo, ID_ANCORA, CORTE)
    dados = resultado.dados
    assert dados.renda_media == 5025.0
    assert dados.gasto_medio == 3000.0
    assert dados.sobra_media == 2025.0
    assert dados.sobra_mediana == 2025.0
    assert [(f.macro, f.micro, f.media) for f in dados.fontes_renda] == [
        ("Renda", "Salario", 5025.0)
    ]
    assert (dados.saldo.minimo, dados.saldo.maximo, dados.saldo.atual) == (-50.0, 1005.0, 600.0)
    assert [p.anomes for p in dados.serie_mensal] == list(range(202501, 202507))
    assert dados.meses_considerados == 6
    assert (resultado.periodo.inicio, resultado.periodo.fim) == (202501, 202506)
    assert resultado.avisos == ("Saldo ficou negativo em 6 meses do período.",)


def test_capacidade_poupanca_no_corte(repo):
    resultado = metricas.capacidade_poupanca(repo, ID_ANCORA, CORTE)
    dados = resultado.dados
    assert (dados.sobra_media, dados.sobra_mediana, dados.desvio_padrao) == (
        2025.0,
        2025.0,
        17.08,
    )
    assert (dados.meses_negativos, dados.meses_considerados) == (0, 6)
    assert resultado.avisos == ()


def test_oportunidades_no_corte(repo):
    resultado = metricas.oportunidades_corte(repo, ID_ANCORA, CORTE, top_n=10)
    assert [
        (o.micro, o.media_mensal, o.economia_potencial_mensal) for o in resultado.dados.categorias
    ] == [("Restaurantes", 500.0, 150.0)]
    assert resultado.avisos == ()


def test_dividas_no_corte(repo):
    resultado = metricas.dividas_e_parcelas(repo, ID_ANCORA, CORTE)
    dados = resultado.dados
    assert [(p.parcela_atual, p.meses_restantes, p.valor) for p in dados.parcelas_ativas] == [
        (6, 6, 100.0)
    ]
    assert dados.juros_pagos_media == 5.0
    assert dados.comprometimento_renda_pct == 1.99


def test_simular_objetivo_modo_prazo(repo):
    resultado = metricas.simular_objetivo(repo, ID_ANCORA, CORTE, 30000.0, prazo_meses=24)
    dados = resultado.dados
    assert (dados.modo, dados.aporte_mensal, dados.prazo_meses) == ("prazo", 1250.0, 24)
    assert (dados.viavel, dados.folga_mensal) == (True, 775.0)
    assert dados.premissas["capacidade_mensal"] == 2025.0
    assert dados.premissas["saldo_inicial"] == 0.0
    assert resultado.avisos == ()


def test_simular_objetivo_com_saldo_atual(repo):
    resultado = metricas.simular_objetivo(
        repo, ID_ANCORA, CORTE, 30000.0, prazo_meses=24, usar_saldo_atual=True
    )
    assert resultado.dados.premissas["saldo_inicial"] == 600.0
    assert resultado.dados.aporte_mensal == 1225.0


def test_simular_objetivo_modo_aporte(repo):
    resultado = metricas.simular_objetivo(repo, ID_ANCORA, CORTE, 30000.0, aporte_mensal=3000.0)
    dados = resultado.dados
    assert (dados.modo, dados.prazo_meses, dados.viavel) == ("aporte", 10, False)
    assert dados.folga_mensal == -975.0
    assert resultado.avisos == (metricas.CONTRIBUTION_ABOVE_SURPLUS_WARNING,)


def test_simular_objetivo_prazo_implausivel(repo):
    with pytest.raises(ImplausibleTermError) as exc:
        metricas.simular_objetivo(repo, ID_ANCORA, CORTE, 30000.0, aporte_mensal=50.0)
    assert exc.value.codigo is CodigoErro.PRAZO_IMPLAUSIVEL


def test_comparar_cenarios_no_corte(repo):
    resultado = metricas.comparar_cenarios(repo, ID_ANCORA, CORTE, 30000.0, 24)
    cenarios = resultado.dados.cenarios
    assert [(c.nome, c.aporte_mensal) for c in cenarios] == [
        ("conservador", 810.0),
        ("equilibrado", 1215.0),
        ("acelerado", 1770.0),
    ]
    assert cenarios[2].prazo_meses == min(c.prazo_meses for c in cenarios)
    assert resultado.dados.regras.pct_capacidade["acelerado"] == 0.8


def test_resumo_mes(repo):
    resultado = metricas.resumo_mes(repo, ID_ANCORA, CORTE, 202503)
    dados = resultado.dados
    assert (dados.anomes, dados.renda, dados.gasto, dados.sobra) == (202503, 5020.0, 3000.0, 2020.0)
    assert [(g.macro, g.total) for g in dados.gastos_macro] == [
        ("Moradia", 1500.0),
        ("Lazer", 500.0),
    ]
    assert (resultado.periodo.inicio, resultado.periodo.fim) == (202503, 202503)
    assert resultado.avisos == ("Saldo ficou negativo neste mês.",)


def test_resumo_mes_depois_do_corte_e_invalido(repo):
    with pytest.raises(InvalidInputError):
        metricas.resumo_mes(repo, ID_ANCORA, CORTE, 202507)


def test_resumo_mes_sem_dados_do_mes(fixtures_sinteticas: Path):
    arquivo = fixtures_sinteticas / "bussola_dados" / "perfil_mensal.json"
    linhas = [
        linha
        for linha in json.loads(arquivo.read_text(encoding="utf-8"))
        if linha["anomes"] != 202503
    ]
    arquivo.write_text(json.dumps(linhas), encoding="utf-8")
    with pytest.raises(InsufficientDataError) as exc:
        metricas.resumo_mes(RepositorioFake(fixtures_sinteticas), ID_ANCORA, CORTE, 202503)
    assert exc.value.mensagem == metricas.MONTH_UNAVAILABLE_MESSAGE


def test_referencia_coorte_pela_faixa_do_periodo(repo):
    resultado = metricas.referencia_coorte(repo, ID_ANCORA, 202512, "moradia")
    dados = resultado.dados
    assert (dados.faixa_renda, dados.macro, dados.media, dados.qtd_usuarios) == (
        "3k_6k",
        "Moradia",
        1500.0,
        10,
    )
    assert resultado.avisos == (COHORT_WARNING,)


def test_referencia_coorte_sem_referencia(repo):
    with pytest.raises(InsufficientDataError) as exc:
        metricas.referencia_coorte(repo, ID_ANCORA, 202512, "Viagem")
    assert exc.value.mensagem == metricas.NO_REFERENCE_MESSAGE


def test_cliente_sem_dados(repo):
    with pytest.raises(InsufficientDataError) as exc:
        metricas.perfil_financeiro(repo, str(uuid.uuid4()), CORTE)
    assert exc.value.codigo is CodigoErro.DADOS_INSUFICIENTES


def test_id_em_maiusculas_equivale(repo):
    assert metricas.perfil_financeiro(repo, ID_ANCORA.upper(), CORTE) == (
        metricas.perfil_financeiro(repo, ID_ANCORA, CORTE)
    )


# ---------------------------------------------------------------------------
# AC-05: corte temporal por métrica
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE], ids=["ancora", "controle"])
def test_futuro_nao_muda_o_corte(fixtures_sinteticas, tmp_path, ferramenta, fn, kw, id_usuario):
    original = RepositorioFake(fixtures_sinteticas)
    envenenado = RepositorioFake(_poison_future(fixtures_sinteticas, tmp_path / "futuro", CORTE))
    assert _envelope(ferramenta, fn, envenenado, id_usuario, CORTE, **kw) == _envelope(
        ferramenta, fn, original, id_usuario, CORTE, **kw
    )


def test_envenenamento_do_futuro_tem_efeito(fixtures_sinteticas, tmp_path):
    """Sanidade do teste acima: em 202512 o futuro alterado aparece."""
    original = RepositorioFake(fixtures_sinteticas)
    envenenado = RepositorioFake(_poison_future(fixtures_sinteticas, tmp_path / "futuro", CORTE))
    assert (
        metricas.perfil_financeiro(envenenado, ID_ANCORA, 202512).dados.renda_media
        > metricas.perfil_financeiro(original, ID_ANCORA, 202512).dados.renda_media * 100
    )


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
def test_periodo_termina_no_corte(repo, ferramenta, fn, kw):
    resultado = fn(repo, ID_ANCORA, CORTE, **kw)
    assert resultado.periodo.fim <= CORTE


# ---------------------------------------------------------------------------
# TS-05: escopo por cliente
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
@pytest.mark.parametrize("corte", [CORTE, 202512])
@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE], ids=["ancora", "controle"])
def test_repositorio_sem_filtro_nao_vaza(repo, ferramenta, fn, kw, corte, id_usuario):
    vazado = LeakyRepository(repo)
    assert _envelope(ferramenta, fn, vazado, id_usuario, corte, **kw) == _envelope(
        ferramenta, fn, repo, id_usuario, corte, **kw
    )


def test_controle_isolado_do_ancora(repo):
    ancora = metricas.perfil_financeiro(repo, ID_ANCORA, 202512).dados
    controle = metricas.perfil_financeiro(repo, ID_CONTROLE, 202512).dados
    assert (ancora.renda_media, controle.renda_media) == (5055.0, 3055.0)
    assert (ancora.sobra_mediana, controle.sobra_mediana) == (2055.0, 1255.0)


# ---------------------------------------------------------------------------
# AC-04: validação antes do repositório
# ---------------------------------------------------------------------------

INVALID_IDS = [
    "x' OR '1'='1",
    "36a21505-d6d4-42d3-b319-d51a133c7269' --",
    "",
    "36a21505-d6d4-12d3-b319-d51a133c7269",  # UUID v1
    None,
    123,
]


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
@pytest.mark.parametrize("id_usuario", INVALID_IDS)
def test_id_invalido_rejeitado_antes_do_repositorio(ferramenta, fn, kw, id_usuario):
    spy = SpyRepository()
    with pytest.raises(InvalidInputError) as exc:
        fn(spy, id_usuario, CORTE, **kw)
    assert spy.calls == []
    assert exc.value.codigo is CodigoErro.ENTRADA_INVALIDA
    assert "OR" not in exc.value.mensagem and "'" not in exc.value.mensagem


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
@pytest.mark.parametrize("ate", [202413, 202500, 202513, 202601, True])
def test_corte_fora_do_intervalo_rejeitado(ferramenta, fn, kw, ate):
    spy = SpyRepository()
    with pytest.raises(InvalidInputError):
        fn(spy, ID_ANCORA, ate, **kw)
    assert spy.calls == []


@pytest.mark.parametrize(
    ("fn", "kw"),
    [
        (metricas.oportunidades_corte, {"top_n": 0}),
        (metricas.oportunidades_corte, {"top_n": 11}),
        (metricas.simular_objetivo, {"valor_alvo": 30000.0}),
        (metricas.simular_objetivo, {"valor_alvo": 30000.0, "prazo_meses": 12, "aporte_mensal": 1}),
        (metricas.simular_objetivo, {"valor_alvo": -1.0, "prazo_meses": 12}),
        (metricas.simular_objetivo, {"valor_alvo": 30000.0, "prazo_meses": 361}),
        (metricas.comparar_cenarios, {"valor_alvo": 0.0, "prazo_meses": 12}),
        (metricas.comparar_cenarios, {"valor_alvo": 30000.0, "prazo_meses": 0}),
        (metricas.resumo_mes, {"anomes": 202413}),
        (metricas.referencia_coorte, {"categoria": ""}),
    ],
)
def test_parametros_invalidos_rejeitados(fn, kw):
    spy = SpyRepository()
    with pytest.raises(InvalidInputError):
        fn(spy, ID_ANCORA, CORTE, **kw)
    assert spy.calls == []


# ---------------------------------------------------------------------------
# Faixa de renda, erros e envelope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "renda", [0.0, 2999.99, 3000.0, 5055.0, 5999.99, 6000.0, 9999.0, 10000.0, 20000.0, 1e6]
)
def test_faixa_igual_a_do_gerador_de_fixtures(renda):
    gerador = _load_script("gerar_fixtures")
    assert income_band(renda) == gerador.faixa_renda(renda)


def test_faixa_limites():
    assert income_band(2999.99) == "ate_3k"
    assert income_band(3000.0) == "3k_6k"
    assert income_band(20000.0) == list(FaixaRenda)[-1].value
    for invalido in (float("nan"), True, "5000"):
        with pytest.raises(ValueError):
            income_band(invalido)  # type: ignore[arg-type]


def test_erros_de_metrica():
    assert InvalidInputError().mensagem == MENSAGENS_ERRO[CodigoErro.ENTRADA_INVALIDA]
    assert isinstance(InvalidInputError(), ValueError)
    assert InsufficientDataError("x").mensagem == "x"
    assert MetricError(codigo=CodigoErro.INDISPONIVEL).codigo is CodigoErro.INDISPONIVEL
    with pytest.raises(TypeError):
        MetricError()


@pytest.mark.parametrize(("ferramenta", "fn", "kw"), SPECS, ids=SPEC_IDS)
def test_envelope_valido_pelo_contrato(repo, ferramenta, fn, kw):
    envelope = _envelope(ferramenta, fn, repo, ID_ANCORA, CORTE, **kw)
    assert set(envelope) == {"dados", "fonte", "avisos"}
    assert envelope["fonte"]["ferramenta"] == ferramenta
    assert envelope["fonte"]["tabelas"] == list(TABELAS_FERRAMENTA[ferramenta])
    Resposta[FERRAMENTAS[ferramenta][1]].model_validate(envelope)


def test_envelope_rejeita_ferramenta_desconhecida(repo):
    resultado = metricas.capacidade_poupanca(repo, ID_ANCORA, CORTE)
    with pytest.raises(ValueError):
        build_envelope("ferramenta_inexistente", resultado)
