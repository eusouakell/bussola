"""Fábrica de dependências do servidor (contratos §4, ciclo §3.1).

Os módulos reais (``repositorio_bq`` do 001 e ``rag`` do 002) são trocados por
nomes inexistentes ou por módulos de teste, para o teste valer antes e depois
do merge deles.
"""

import logging
import sys
import types

import pytest
from apoio_ferramentas import argumentos, chamar, sessao

from bussola_mcp import server
from bussola_mcp.contratos import FERRAMENTAS
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.ports import FinancialComputations


@pytest.fixture
def modo_real(monkeypatch):
    monkeypatch.setenv("BUSSOLA_FAKES", "FALSE")
    monkeypatch.delenv("BQ_MODO_LEITURA", raising=False)
    monkeypatch.delenv("RAG_BACKEND", raising=False)


@pytest.fixture
def modulos_reais_de_teste(monkeypatch, modo_real):
    """Injeta ``RepositorioBigQuery`` e ``criar_buscador`` de mentira e devolve os registros."""
    registros: dict[str, list[str]] = {"modo": [], "backend": []}

    class RepositorioBigQuery:
        def __init__(self, modo: str) -> None:
            registros["modo"].append(modo)

    def criar_buscador(backend: str):
        registros["backend"].append(backend)
        return FixtureSearcher()

    repo = types.ModuleType("repo_real_teste_003")
    repo.RepositorioBigQuery = RepositorioBigQuery
    rag = types.ModuleType("rag_real_teste_003")
    rag.criar_buscador = criar_buscador
    monkeypatch.setitem(sys.modules, repo.__name__, repo)
    monkeypatch.setitem(sys.modules, rag.__name__, rag)
    monkeypatch.setattr(server, "REAL_REPOSITORY_MODULE", repo.__name__)
    monkeypatch.setattr(server, "REAL_SEARCHER_MODULE", rag.__name__)
    return registros


@pytest.mark.parametrize("valor", ["TRUE", "true", " True ", "1"])
def test_fakes_ligados(monkeypatch, valor):
    monkeypatch.setenv("BUSSOLA_FAKES", valor)
    assert server.fakes_enabled() is True


@pytest.mark.parametrize("valor", ["FALSE", "0", "", "sim"])
def test_fakes_desligados(monkeypatch, valor):
    monkeypatch.setenv("BUSSOLA_FAKES", valor)
    assert server.fakes_enabled() is False


def test_modo_fake_usa_fixtures(monkeypatch):
    monkeypatch.setenv("BUSSOLA_FAKES", "TRUE")
    deps = server.build_dependencies()
    assert isinstance(deps.repository, FixtureRepository)
    assert isinstance(deps.searcher, FixtureSearcher)
    assert isinstance(deps.computations, FinancialComputations)


def test_fixtures_explicitas_forcam_o_modo_fake(modulos_reais_de_teste, fixtures_sinteticas):
    deps = server.build_dependencies(fixtures_sinteticas)
    assert isinstance(deps.repository, FixtureRepository)
    assert deps.repository.fixtures_dir == fixtures_sinteticas
    assert modulos_reais_de_teste == {"modo": [], "backend": []}


def test_modo_real_usa_os_padroes(modulos_reais_de_teste):
    deps = server.build_dependencies()
    assert modulos_reais_de_teste == {"modo": ["query"], "backend": ["lexico"]}
    assert type(deps.repository).__name__ == "RepositorioBigQuery"
    assert isinstance(deps.computations, FinancialComputations)


def test_modo_real_respeita_as_variaveis(monkeypatch, modulos_reais_de_teste):
    monkeypatch.setenv("BQ_MODO_LEITURA", "memoria")
    monkeypatch.setenv("RAG_BACKEND", "numpy")
    server.build_dependencies()
    assert modulos_reais_de_teste == {"modo": ["memoria"], "backend": ["numpy"]}


def test_modulos_ausentes_caem_nas_fixtures_com_aviso(monkeypatch, modo_real, caplog):
    monkeypatch.setattr(server, "REAL_REPOSITORY_MODULE", "modulo_inexistente_003")
    monkeypatch.setattr(server, "REAL_SEARCHER_MODULE", "pacote_inexistente_003.rag")
    with caplog.at_level(logging.WARNING, logger="bussola_mcp.server"):
        deps = server.build_dependencies()
    assert isinstance(deps.repository, FixtureRepository)
    assert isinstance(deps.searcher, FixtureSearcher)
    avisos = [r for r in caplog.records if getattr(r, "evento", None) == "dependencia_ausente"]
    assert len(avisos) == 2


async def test_servidor_em_fallback_responde(monkeypatch, modo_real):
    monkeypatch.setattr(server, "REAL_REPOSITORY_MODULE", "modulo_inexistente_003")
    monkeypatch.setattr(server, "REAL_SEARCHER_MODULE", "modulo_inexistente_003")
    async with sessao() as cliente:
        envelope = await chamar(cliente, "perfil_financeiro", argumentos("perfil_financeiro"))
    assert "dados" in envelope


def test_dependencia_interna_ausente_propaga(monkeypatch, modo_real, tmp_path):
    """Pacote ausente *dentro* do módulo real é falha de startup, não fallback."""
    (tmp_path / "modulo_quebrado_003.py").write_text(
        "import pacote_que_nao_existe_003\n", encoding="utf-8"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(server, "REAL_REPOSITORY_MODULE", "modulo_quebrado_003")
    with pytest.raises(ModuleNotFoundError) as info:
        server.build_dependencies()
    assert info.value.name == "pacote_que_nao_existe_003"


async def test_criar_servidor_compativel_com_o_mock_do_000(fixtures_sinteticas):
    servidor = server.criar_servidor(fixtures_sinteticas)
    assert {f.name for f in await servidor.list_tools()} == set(FERRAMENTAS)


def test_argumentos_da_linha_de_comando(monkeypatch, tmp_path):
    monkeypatch.setenv("PORT", "9123")
    args = server._argumentos([])
    assert (args.host, args.port, args.fixtures) == ("0.0.0.0", 9123, None)
    args = server._argumentos(["--host", "127.0.0.1", "--port", "81", "--fixtures", str(tmp_path)])
    assert (args.host, args.port, args.fixtures) == ("127.0.0.1", 81, tmp_path)
