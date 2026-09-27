"""Testes de ``dominio/repositorio_bq.py`` com um cliente BigQuery falso (ciclo 001, T011).

Sem rede: o cliente falso executa em Python as leituras de ``build_queries`` sobre as
fixtures sintéticas. Cobre AC-04 (validação antes do cliente, SQL constante e
parametrizado) e AC-06 (``query`` == ``memoria``), o filtro D-05 de recorrência e o
tratamento de falhas.
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from google.cloud.bigquery.table import Row

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, FaixaRenda
from bussola_mcp.dominio import repositorio_bq
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.dominio.repositorio_bq import (
    LOCATION,
    TABLE_MODELS,
    RepositorioBigQuery,
    RepositoryUnavailableError,
    build_queries,
    validate_dataset,
)

_TABLE_RE = re.compile(r"FROM `([a-z0-9_]+)\.([a-z_]+)`")
CUTS = (202501, 202502, 202503, 202506, 202507, 202512)
USERS = (ID_ANCORA, ID_CONTROLE)
INJECTION = "x' OR '1'='1"


def _to_row(data: dict[str, Any]) -> Row:
    campos = list(data)
    return Row(tuple(data[c] for c in campos), {c: i for i, c in enumerate(campos)})


class FakeJob:
    def __init__(self, rows: list[Row]) -> None:
        self._rows = rows

    def result(self) -> list[Row]:
        return self._rows


class FakeBigQueryClient:
    """Emula as leituras de ``build_queries`` sobre tabelas em memória.

    Devolve as linhas em ordem invertida para provar que a ordem vem do repositório.
    Com ``ignore_filters`` devolve a tabela inteira (cliente "vazado").
    """

    def __init__(self, tables: dict[str, list[dict[str, Any]]], ignore_filters: bool = False):
        self.tables = tables
        self.ignore_filters = ignore_filters
        self.queries: list[tuple[str, dict[str, tuple[str, Any]], str | None]] = []
        self.listed: list[str] = []

    def query(self, sql: str, job_config: Any = None, location: str | None = None) -> FakeJob:
        params = {p.name: (p.type_, p.value) for p in job_config.query_parameters}
        self.queries.append((sql, params, location))
        match = _TABLE_RE.search(sql)
        assert match is not None
        linhas = self.tables[match.group(2)]
        valores = {nome: valor for nome, (_, valor) in params.items()}
        if not self.ignore_filters:
            linhas = [linha for linha in linhas if self._matches(linha, valores)]
        if sql.startswith("SELECT 1 AS existe"):
            return FakeJob([_to_row({"existe": 1})] if linhas else [])
        return FakeJob([_to_row(linha) for linha in reversed(linhas)])

    @staticmethod
    def _matches(linha: dict[str, Any], valores: dict[str, Any]) -> bool:
        if "id_usuario" in valores and linha["id_usuario"] != valores["id_usuario"]:
            return False
        if "ate_anomes" in valores and linha["anomes"] > valores["ate_anomes"]:
            return False
        if valores.get("desde_anomes") is not None and linha["anomes"] < valores["desde_anomes"]:
            return False
        if "faixa_renda" in valores and linha["faixa_renda"] != valores["faixa_renda"]:
            return False
        return valores.get("macro") is None or linha["macro"] == valores["macro"]

    def list_rows(self, table: str) -> list[Row]:
        self.listed.append(table)
        dataset, _, nome = table.partition(".")
        assert dataset.startswith("bussola_dados")
        return [_to_row(linha) for linha in reversed(self.tables[nome])]


class ForbiddenClient:
    """Qualquer uso do cliente falha o teste."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"cliente BigQuery acessado: {name}")


def _forbidden_create(projeto: str | None) -> Any:
    raise AssertionError("cliente BigQuery criado antes da validação")


def _extra_recurring() -> list[dict[str, Any]]:
    """``academia``: 3 meses no total, mas só 2 até 202506 (D-05)."""
    return [
        {
            "id_usuario": ID_ANCORA,
            "anomes": anomes,
            "descr_norm": "academia",
            "macro": "Saude",
            "micro": "Academia",
            "valor": 99.9,
        }
        for anomes in (202505, 202506, 202507)
    ]


@pytest.fixture
def tables(fixtures_sinteticas: Path) -> dict[str, list[dict[str, Any]]]:
    dados = {
        nome: json.loads(
            (fixtures_sinteticas / "bussola_dados" / f"{nome}.json").read_text(encoding="utf-8")
        )
        for nome in TABLE_MODELS
        if (fixtures_sinteticas / "bussola_dados" / f"{nome}.json").exists()
    }
    dados["recorrentes"] = dados["recorrentes"] + _extra_recurring()
    assert set(dados) == set(TABLE_MODELS)
    return dados


@pytest.fixture
def client(tables) -> FakeBigQueryClient:
    return FakeBigQueryClient(tables)


@pytest.fixture
def repo_query(client) -> RepositorioBigQuery:
    return RepositorioBigQuery("query", client=client)


@pytest.fixture
def repo_memoria(tables) -> RepositorioBigQuery:
    return RepositorioBigQuery("memoria", client=FakeBigQueryClient(tables))


def _all_reads(repo: Any, id_usuario: str, ate: int) -> dict[str, list[Any]]:
    return {
        "perfil_mensal": repo.perfil_mensal(id_usuario, ate),
        "gastos_categoria": repo.gastos_categoria(id_usuario, ate),
        "gastos_desde": repo.gastos_categoria(id_usuario, ate, desde_anomes=min(ate, 202503)),
        "entradas_categoria": repo.entradas_categoria(id_usuario, ate),
        "recorrentes": repo.recorrentes(id_usuario, ate),
        "parcelas": repo.parcelas(id_usuario, ate),
    }


# ---------------------------------------------------------------------------
# AC-06: query == memoria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ate", CUTS)
@pytest.mark.parametrize("id_usuario", USERS, ids=["ancora", "controle"])
def test_query_igual_a_memoria(repo_query, repo_memoria, id_usuario, ate):
    assert _all_reads(repo_query, id_usuario, ate) == _all_reads(repo_memoria, id_usuario, ate)


def test_tabelas_comuns_iguais_nos_dois_modos(repo_query, repo_memoria):
    assert repo_query.categorias() == repo_memoria.categorias()
    for faixa in FaixaRenda:
        assert repo_query.referencia_coorte(faixa.value) == repo_memoria.referencia_coorte(
            faixa.value
        )
        assert repo_query.referencia_coorte(faixa.value, "Lazer") == (
            repo_memoria.referencia_coorte(faixa.value, "Lazer")
        )


@pytest.mark.parametrize("ate", (202506, 202512))
def test_mesmas_linhas_do_repositorio_fake(fixtures_sinteticas, repo_query, ate):
    """Sem o extra de recorrência, as leituras batem com o ``RepositorioFake``."""
    fake = RepositorioFake(fixtures_sinteticas)
    for id_usuario in USERS:
        assert repo_query.perfil_mensal(id_usuario, ate) == fake.perfil_mensal(id_usuario, ate)
        assert repo_query.parcelas(id_usuario, ate) == fake.parcelas(id_usuario, ate)
        assert sorted(repo_query.gastos_categoria(id_usuario, ate), key=repr) == sorted(
            fake.gastos_categoria(id_usuario, ate), key=repr
        )
    assert sorted(repo_query.categorias(), key=repr) == sorted(fake.categorias(), key=repr)
    assert repo_query.referencia_coorte("3k_6k", "Moradia") == fake.referencia_coorte(
        "3k_6k", "Moradia"
    )


def test_ordem_estavel_mesmo_com_cliente_invertido(repo_query):
    gastos = repo_query.gastos_categoria(ID_ANCORA, 202512)
    chaves = [(g.anomes, g.macro, g.micro) for g in gastos]
    assert chaves == sorted(chaves)
    coorte = repo_query.referencia_coorte("3k_6k")
    assert [r.macro for r in coorte] == sorted(r.macro for r in coorte)


# ---------------------------------------------------------------------------
# Corte, escopo e D-05
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modo", ["query", "memoria"])
def test_cliente_sem_filtro_nao_vaza(tables, modo):
    """Mesmo que o BigQuery devolva a tabela inteira, o repositório refiltra."""
    repo = RepositorioBigQuery(modo, client=FakeBigQueryClient(tables, ignore_filters=True))
    for leitura in _all_reads(repo, ID_CONTROLE, 202506).values():
        assert all(linha.id_usuario == ID_CONTROLE and linha.anomes <= 202506 for linha in leitura)
    desde = repo.gastos_categoria(ID_CONTROLE, 202506, desde_anomes=202504)
    assert {g.anomes for g in desde} == {202504, 202505, 202506}
    assert {r.faixa_renda for r in repo.referencia_coorte("6k_10k")} == {"6k_10k"}


@pytest.mark.parametrize("modo", ["query", "memoria"])
def test_recorrencia_so_com_meses_ate_o_corte(tables, modo):
    repo = RepositorioBigQuery(modo, client=FakeBigQueryClient(tables))
    descricoes = {ate: {r.descr_norm for r in repo.recorrentes(ID_ANCORA, ate)} for ate in CUTS}
    assert descricoes[202501] == set()
    assert descricoes[202502] == set()
    assert descricoes[202503] == {"streaming exemplo"}
    assert descricoes[202506] == {"streaming exemplo"}  # academia: 2 meses até o corte
    assert descricoes[202507] == {"streaming exemplo", "academia"}
    assert descricoes[202512] == {"streaming exemplo", "academia"}


@pytest.mark.parametrize("modo", ["query", "memoria"])
def test_usuario_existe(tables, modo):
    repo = RepositorioBigQuery(modo, client=FakeBigQueryClient(tables))
    assert repo.usuario_existe(ID_ANCORA) is True
    assert repo.usuario_existe(ID_CONTROLE.upper()) is True
    assert repo.usuario_existe(str(uuid.uuid4())) is False
    with pytest.raises(ValueError):
        repo.usuario_existe(INJECTION)


# ---------------------------------------------------------------------------
# AC-04: SQL constante e parametrizado, validação antes do cliente
# ---------------------------------------------------------------------------


def test_sql_executado_e_sempre_o_constante(repo_query, client):
    _all_reads(repo_query, ID_ANCORA.upper(), 202506)
    repo_query.usuario_existe(ID_ANCORA)
    repo_query.categorias()
    repo_query.referencia_coorte("3k_6k", "Lazer")
    constantes = set(build_queries("bussola_dados").values())
    assert client.queries
    for sql, _params, location in client.queries:
        assert sql in constantes
        assert ID_ANCORA not in sql.lower() and "202506" not in sql and "Lazer" not in sql
        assert location == LOCATION
    params = client.queries[0][1]
    assert params["id_usuario"] == ("STRING", ID_ANCORA)
    assert params["ate_anomes"] == ("INT64", 202506)
    coorte = client.queries[-1][1]
    assert coorte == {"faixa_renda": ("STRING", "3k_6k"), "macro": ("STRING", "Lazer")}


def test_sql_so_interpola_o_dataset():
    for nome, sql in build_queries("bussola_dados_c001").items():
        tabelas = _TABLE_RE.findall(sql)
        assert tabelas and all(ds == "bussola_dados_c001" for ds, _ in tabelas), nome
        assert "{" not in sql and "}" not in sql
        if nome not in ("categorias",):
            assert "@" in sql


INVALID_IDS = [INJECTION, "", "36a21505-d6d4-12d3-b319-d51a133c7269", None, 42]


@pytest.mark.parametrize("modo", ["query", "memoria"])
@pytest.mark.parametrize("id_usuario", INVALID_IDS)
def test_id_invalido_antes_do_cliente(tables, modo, id_usuario):
    client = FakeBigQueryClient(tables)
    repo = RepositorioBigQuery(modo, client=client)
    antes = (len(client.queries), len(client.listed))
    leituras = [
        lambda: repo.perfil_mensal(id_usuario, 202506),
        lambda: repo.gastos_categoria(id_usuario, 202506),
        lambda: repo.entradas_categoria(id_usuario, 202506),
        lambda: repo.recorrentes(id_usuario, 202506),
        lambda: repo.parcelas(id_usuario, 202506),
        lambda: repo.usuario_existe(id_usuario),
    ]
    for leitura in leituras:
        with pytest.raises(ValueError) as exc:
            leitura()
        assert "OR" not in str(exc.value)
    assert (len(client.queries), len(client.listed)) == antes


@pytest.mark.parametrize(
    "chamada",
    [
        lambda r: r.perfil_mensal(ID_ANCORA, 202413),
        lambda r: r.perfil_mensal(ID_ANCORA, 202601),
        lambda r: r.parcelas(ID_ANCORA, True),
        lambda r: r.parcelas(ID_ANCORA, "202506"),
        lambda r: r.gastos_categoria(ID_ANCORA, 202506, desde_anomes=202413),
        lambda r: r.gastos_categoria(ID_ANCORA, 202506, desde_anomes="202501"),
        lambda r: r.referencia_coorte("' OR 1=1 --"),
        lambda r: r.referencia_coorte("3k_6k", ""),
        lambda r: r.referencia_coorte("3k_6k", 7),
    ],
)
def test_parametros_invalidos_antes_do_cliente(chamada):
    repo = RepositorioBigQuery("query", client=ForbiddenClient())
    with pytest.raises(ValueError):
        chamada(repo)


@pytest.mark.parametrize("nome", ["bussola_dados", "bussola_dados_c001", "bussola_dados_teste_2"])
def test_dataset_aceito(nome):
    assert validate_dataset(nome) == nome


@pytest.mark.parametrize(
    "nome",
    [
        "hackathon_dados",
        "bussola_app_dev",
        "BUSSOLA_DADOS",
        "bussola_dados;DROP TABLE x",
        "bussola_dados`.x",
        "bussola_dados_",
        "outro.bussola_dados",
        "",
        None,
    ],
)
def test_dataset_recusado_antes_do_cliente(monkeypatch, nome):
    monkeypatch.setattr(repositorio_bq, "_create_client", _forbidden_create)
    with pytest.raises(ValueError):
        validate_dataset(nome)
    if nome:  # vazio ou None caem no padrão do ambiente
        with pytest.raises(ValueError):
            RepositorioBigQuery("query", dataset=nome)


@pytest.mark.parametrize("modo", ["QUERY", "cache", "", 1])
def test_modo_invalido(monkeypatch, modo):
    monkeypatch.setattr(repositorio_bq, "_create_client", _forbidden_create)
    with pytest.raises(ValueError):
        repositorio_bq.validate_mode(modo)
    if isinstance(modo, str) and modo:
        with pytest.raises(ValueError):
            RepositorioBigQuery(modo)


def test_configuracao_por_ambiente(monkeypatch, tables):
    criados: list[str | None] = []

    def fake_create(projeto: str | None) -> FakeBigQueryClient:
        criados.append(projeto)
        return FakeBigQueryClient(tables)

    monkeypatch.setattr(repositorio_bq, "_create_client", fake_create)
    monkeypatch.setenv("BQ_MODO_LEITURA", "memoria")
    monkeypatch.setenv("BQ_DATASET_DADOS", "bussola_dados_c001")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "projeto-teste")
    repo = RepositorioBigQuery()
    assert (repo.modo, repo.dataset) == ("memoria", "bussola_dados_c001")
    assert criados == ["projeto-teste"]
    assert repo._client.listed == [f"bussola_dados_c001.{t}" for t in TABLE_MODELS]


def test_padrao_e_query_em_bussola_dados(monkeypatch, client):
    monkeypatch.delenv("BQ_MODO_LEITURA", raising=False)
    monkeypatch.delenv("BQ_DATASET_DADOS", raising=False)
    repo = RepositorioBigQuery(client=client)
    assert (repo.modo, repo.dataset) == ("query", "bussola_dados")
    assert client.queries == [] and client.listed == []


# ---------------------------------------------------------------------------
# Cache e falhas
# ---------------------------------------------------------------------------


def test_categorias_lidas_uma_vez(repo_query, client):
    primeira = repo_query.categorias()
    primeira.clear()
    segunda = repo_query.categorias()
    assert segunda
    assert sum(1 for sql, _, _ in client.queries if "`bussola_dados.categorias`" in sql) == 1


class BrokenClient:
    def query(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("falha interna com SELECT e projeto-secreto")

    def list_rows(self, table: str) -> Any:
        raise RuntimeError("falha interna com projeto-secreto")


def test_falha_da_consulta_vira_indisponivel():
    repo = RepositorioBigQuery("query", client=BrokenClient())
    with pytest.raises(RepositoryUnavailableError) as exc:
        repo.perfil_mensal(ID_ANCORA, 202506)
    assert "projeto-secreto" not in str(exc.value) and "SELECT" not in str(exc.value)
    with pytest.raises(RepositoryUnavailableError):
        repo.categorias()


def test_falha_na_carga_da_memoria_vira_indisponivel():
    with pytest.raises(RepositoryUnavailableError) as exc:
        RepositorioBigQuery("memoria", client=BrokenClient())
    assert str(exc.value) == "Leitura de dados indisponível."


def test_falha_ao_criar_cliente_vira_indisponivel(monkeypatch):
    def quebra(projeto: str | None) -> Any:
        raise RuntimeError("sem credencial")

    monkeypatch.setattr(repositorio_bq, "_create_client", quebra)
    with pytest.raises(RepositoryUnavailableError):
        RepositorioBigQuery("query")


def test_linha_fora_do_contrato_vira_indisponivel(tables):
    tables["perfil_mensal"][0] = {**tables["perfil_mensal"][0], "renda": "muito"}
    repo = RepositorioBigQuery("query", client=FakeBigQueryClient(tables))
    with pytest.raises(RepositoryUnavailableError):
        repo.perfil_mensal(tables["perfil_mensal"][0]["id_usuario"], 202512)
