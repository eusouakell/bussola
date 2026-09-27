"""``RepositorioBigQuery`` contra o BigQuery real (``make test-bq``; AC-03, AC-06, TS-01, TS-02).

Só leitura em ``bussola_dados``, com ADC. Nada é gravado. O projeto vem de
``GOOGLE_CLOUD_PROJECT`` ou, na falta dela, de ``contracts/env.example``.
"""

import json
import os
import statistics
from pathlib import Path
from typing import Any

import pytest

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    FaixaRenda,
    arquivo_golden,
    arquivo_resumo_mes,
)
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.repositorio_bq import RepositorioBigQuery

pytestmark = pytest.mark.bq

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "contracts" / "fixtures"
USERS = (ID_ANCORA, ID_CONTROLE)
CUTS = (202503, 202506, 202512)
GOLDEN_ARGUMENTS: dict[str, dict[str, Any]] = {
    "oportunidades_corte": {"top_n": 10},
    "simular_objetivo": dict(ENTRADA_CANONICA_SIMULACAO),
    "comparar_cenarios": dict(ENTRADA_CANONICA_SIMULACAO),
}

# contratos §8: valores de referência do âncora (média de 2025, corte 202512).
REFERENCE = {
    "renda": 7451.0,
    "gasto": 4615.0,
    "sobra": 2836.0,
    "aluguel": 1077.0,
    "comer_fora": 364.0,
    "assinaturas": 101.0,
    "juros": 61.0,
    "saldo_minimo": -2072.0,
    "saldo_maximo": 49321.0,
}
TOLERANCE = 0.01


def _project() -> str:
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        return os.environ["GOOGLE_CLOUD_PROJECT"]
    for line in (REPO_ROOT / "contracts" / "env.example").read_text().splitlines():
        if line.startswith("GOOGLE_CLOUD_PROJECT="):
            return line.partition("=")[2].strip()
    raise RuntimeError("GOOGLE_CLOUD_PROJECT ausente")


@pytest.fixture(scope="module")
def repo_query() -> RepositorioBigQuery:
    return RepositorioBigQuery("query", dataset="bussola_dados", projeto=_project())


@pytest.fixture(scope="module")
def repo_memoria() -> RepositorioBigQuery:
    return RepositorioBigQuery("memoria", dataset="bussola_dados", projeto=_project())


def _reads(repo: RepositorioBigQuery, id_usuario: str, ate: int) -> dict[str, list[Any]]:
    return {
        "perfil_mensal": repo.perfil_mensal(id_usuario, ate),
        "gastos_categoria": repo.gastos_categoria(id_usuario, ate),
        "gastos_desde_abril": repo.gastos_categoria(id_usuario, ate, desde_anomes=202504),
        "entradas_categoria": repo.entradas_categoria(id_usuario, ate),
        "recorrentes": repo.recorrentes(id_usuario, ate),
        "parcelas": repo.parcelas(id_usuario, ate),
    }


# ---------------------------------------------------------------------------
# AC-06: query == memoria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ate", CUTS)
@pytest.mark.parametrize("id_usuario", USERS)
def test_query_igual_a_memoria(repo_query, repo_memoria, id_usuario: str, ate: int) -> None:
    assert _reads(repo_query, id_usuario, ate) == _reads(repo_memoria, id_usuario, ate)


def test_tabelas_comuns_iguais_nos_dois_modos(repo_query, repo_memoria) -> None:
    assert repo_query.categorias() == repo_memoria.categorias()
    for band in FaixaRenda:
        assert repo_query.referencia_coorte(band.value) == repo_memoria.referencia_coorte(
            band.value
        )
    for id_usuario in USERS:
        assert repo_query.usuario_existe(id_usuario) and repo_memoria.usuario_existe(id_usuario)


def test_usuario_desconhecido_nao_existe(repo_query) -> None:
    assert repo_query.usuario_existe("00000000-0000-4000-8000-000000000000") is False


def test_catalogo_e_coorte_publicados(repo_query) -> None:
    assert len(repo_query.categorias()) == 98
    coorte = [r for b in FaixaRenda for r in repo_query.referencia_coorte(b.value)]
    assert coorte and min(r.qtd_usuarios for r in coorte) >= 5


# ---------------------------------------------------------------------------
# AC-03 e TS-01: âncora a 1% do §8
# ---------------------------------------------------------------------------


def _anchor_metrics(repo: RepositorioBigQuery) -> dict[str, float]:
    perfil = repo.perfil_mensal(ID_ANCORA, 202512)
    gastos = repo.gastos_categoria(ID_ANCORA, 202512)
    meses = len(perfil)

    def total(pred: Any) -> float:
        return sum(g.total for g in gastos if pred(g)) / meses

    return {
        "renda": statistics.fmean(p.renda for p in perfil),
        "gasto": statistics.fmean(p.gasto for p in perfil),
        "sobra": statistics.fmean(p.sobra for p in perfil),
        "aluguel": total(lambda g: g.micro == "Pagamento de aluguel"),
        "comer_fora": total(lambda g: g.macro == "Restaurantes"),
        "assinaturas": total(lambda g: g.macro == "Assinaturas"),
        "juros": statistics.fmean(p.juros for p in perfil),
        "saldo_minimo": min(p.saldo_minimo for p in perfil),
        "saldo_maximo": max(p.saldo_maximo for p in perfil),
    }


def test_perfil_do_ancora_tem_12_meses(repo_query) -> None:
    perfil = repo_query.perfil_mensal(ID_ANCORA, 202512)
    assert [p.anomes for p in perfil] == list(range(202501, 202513))


@pytest.mark.parametrize("metrica", list(REFERENCE))
def test_ancora_a_1_por_cento_do_contrato(repo_query, metrica: str) -> None:
    obtido = _anchor_metrics(repo_query)[metrica]
    esperado = REFERENCE[metrica]
    assert abs(obtido - esperado) <= abs(esperado) * TOLERANCE, (metrica, obtido)


def test_ts02_oportunidades_top3_inclui_comer_fora_sem_aluguel(repo_query) -> None:
    resultado = metricas.oportunidades_corte(repo_query, ID_ANCORA, 202512, top_n=3)
    itens = resultado.dados.categorias
    assert len(itens) == 3
    assert [i for i in itens if i.macro == "Restaurantes"]
    assert not [i for i in itens if "aluguel" in i.micro.lower()]


def test_ts05_controle_nao_mistura_linhas_do_ancora(repo_query) -> None:
    for leitura in _reads(repo_query, ID_CONTROLE, 202512).values():
        assert leitura and {r.id_usuario for r in leitura} == {ID_CONTROLE}


# ---------------------------------------------------------------------------
# Fixtures v1 == bussola_dados (D-07): o que o 003 serve é o golden
# ---------------------------------------------------------------------------


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


GOLDEN_CALLS = [
    (arquivo_golden(tool, cut), tool, cut, GOLDEN_ARGUMENTS.get(tool, {}))
    for cut in CORTES_GOLDEN
    for tool in FERRAMENTAS_GOLDEN
] + [
    (arquivo_resumo_mes(anomes), "resumo_mes", anomes, {"anomes": anomes})
    for anomes in (202501, 202506, 202512)
]


@pytest.mark.parametrize(("arquivo", "tool", "ate", "kwargs"), GOLDEN_CALLS)
def test_metricas_sobre_bigquery_igual_ao_golden_v1(repo_query, arquivo, tool, ate, kwargs):
    resultado = getattr(metricas, tool)(repo_query, ID_ANCORA, ate, **kwargs)
    envelope = metricas.build_envelope(tool, resultado)
    assert envelope == _read(FIXTURES / "ferramentas" / arquivo)


def test_linhas_das_fixtures_v1_iguais_ao_dataset(repo_query) -> None:
    for tabela in ("perfil_mensal", "gastos_categoria", "parcelas"):
        versionado = [
            r
            for r in _read(FIXTURES / "bussola_dados" / f"{tabela}.json")
            if r["id_usuario"] == ID_ANCORA
        ]
        lido = [r.model_dump(mode="json") for r in getattr(repo_query, tabela)(ID_ANCORA, 202512)]
        assert lido == versionado, tabela
