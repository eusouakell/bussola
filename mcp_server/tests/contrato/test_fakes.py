"""Fakes do domínio: escopo, tempo e filtro do buscador (FR-009, FR-010, TS-05, T015)."""

import json
import uuid
from pathlib import Path

import pytest

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, Trecho
from bussola_mcp.dominio.fakes import BuscadorFake, RepositorioFake, dir_fixtures_padrao, tokens
from bussola_mcp.dominio.interfaces import BuscadorContexto, RepositorioFinanceiro

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[3]
UUID_DESCONHECIDO = str(uuid.UUID(int=0x1234, version=4))


@pytest.fixture
def repo(fixtures_sinteticas: Path) -> RepositorioFake:
    return RepositorioFake(fixtures_sinteticas)


@pytest.fixture
def buscador(fixtures_sinteticas: Path) -> BuscadorFake:
    return BuscadorFake(fixtures_sinteticas)


# -- Protocols e diretório padrão ----------------------------------------------


def test_fakes_implementam_os_protocols(tmp_path):
    assert isinstance(RepositorioFake(tmp_path), RepositorioFinanceiro)
    assert isinstance(BuscadorFake(tmp_path), BuscadorContexto)
    assert not isinstance(object(), RepositorioFinanceiro)
    assert not isinstance(object(), BuscadorContexto)


def test_diretorio_padrao_e_contracts_fixtures():
    esperado = RAIZ_REPOSITORIO / "contracts" / "fixtures"
    assert dir_fixtures_padrao() == esperado
    assert RepositorioFake().dir_fixtures == esperado
    assert BuscadorFake(None).dir_fixtures == esperado


def test_leitura_sob_demanda(tmp_path):
    """Construir o fake não lê arquivos: um diretório inexistente só vira tabela vazia."""
    repo = RepositorioFake(tmp_path / "nao_existe")
    assert repo.perfil_mensal(ID_ANCORA, 202512) == []
    assert repo.categorias() == []
    assert repo.usuario_existe(ID_ANCORA) is False
    assert repo.faixa_renda_de(ID_ANCORA) is None
    assert BuscadorFake(tmp_path / "nao_existe").buscar(ID_ANCORA, "aluguel", 5, 202512) == []


# -- escopo e tempo ------------------------------------------------------------------


def test_ts05_controle_ate_202503(repo):
    """TS-05: 3 meses do controle e nenhum do âncora."""
    linhas = repo.perfil_mensal(ID_CONTROLE, 202503)
    assert [linha.anomes for linha in linhas] == [202501, 202502, 202503]
    assert {linha.id_usuario for linha in linhas} == {ID_CONTROLE}


@pytest.mark.parametrize(
    "metodo", ["perfil_mensal", "gastos_categoria", "entradas_categoria", "recorrentes", "parcelas"]
)
@pytest.mark.parametrize("id_usuario", [ID_ANCORA, ID_CONTROLE])
@pytest.mark.parametrize("ate_anomes", [202501, 202506, 202512])
def test_escopo_e_corte_em_toda_leitura(repo, metodo, id_usuario, ate_anomes):
    linhas = getattr(repo, metodo)(id_usuario, ate_anomes)
    assert linhas
    assert {linha.id_usuario for linha in linhas} == {id_usuario}
    assert max(linha.anomes for linha in linhas) == ate_anomes
    assert [linha.anomes for linha in linhas] == sorted(linha.anomes for linha in linhas)


def test_id_usuario_em_maiusculas_tem_o_mesmo_escopo(repo):
    assert repo.perfil_mensal(ID_ANCORA.upper(), 202506) == repo.perfil_mensal(ID_ANCORA, 202506)


def test_usuario_desconhecido_nao_tem_linhas(repo):
    assert repo.usuario_existe(UUID_DESCONHECIDO) is False
    assert repo.perfil_mensal(UUID_DESCONHECIDO, 202512) == []
    assert repo.gastos_categoria(UUID_DESCONHECIDO, 202512) == []


def test_desde_anomes(repo):
    linhas = repo.gastos_categoria(ID_ANCORA, 202506, desde_anomes=202504)
    assert sorted({linha.anomes for linha in linhas}) == [202504, 202505, 202506]
    assert {linha.id_usuario for linha in linhas} == {ID_ANCORA}
    assert repo.gastos_categoria(ID_ANCORA, 202503, desde_anomes=202504) == []
    todos = repo.gastos_categoria(ID_ANCORA, 202506)
    assert sorted({linha.anomes for linha in todos}) == list(range(202501, 202507))


def test_usuarios_e_faixa(repo):
    assert repo.usuario_existe(ID_ANCORA) and repo.usuario_existe(ID_CONTROLE)
    assert repo.faixa_renda_de(ID_ANCORA) == "6k_10k"
    assert repo.faixa_renda_de(ID_CONTROLE.upper()) == "3k_6k"
    assert repo.faixa_renda_de(UUID_DESCONHECIDO) is None


def test_categorias_e_referencia_coorte(repo):
    assert {(c.macro, c.micro) for c in repo.categorias()} == {
        ("Moradia", "Aluguel"),
        ("Lazer", "Restaurantes"),
    }
    refs = repo.referencia_coorte("6k_10k")
    assert {r.macro for r in refs} == {"Moradia", "Lazer"}
    assert {r.faixa_renda for r in refs} == {"6k_10k"}
    assert [r.macro for r in repo.referencia_coorte("6k_10k", "Lazer")] == ["Lazer"]
    assert repo.referencia_coorte("acima_20k") == []


def test_aceita_objeto_com_lista_de_linhas(tmp_path):
    """Formato alternativo: ``{"linhas": [...]}`` e ``{"usuarios": [...]}``."""
    (tmp_path / "bussola_dados").mkdir()
    linha = {
        "macro": "Lazer",
        "micro": "Restaurantes",
        "discricionaria": True,
        "corte_max_pct": 0.3,
    }
    (tmp_path / "bussola_dados" / "categorias.json").write_text(json.dumps({"linhas": [linha]}))
    usuario = {"id_usuario": ID_ANCORA, "papel": "ancora", "faixa_renda": "6k_10k"}
    (tmp_path / "usuarios.json").write_text(json.dumps({"usuarios": [usuario]}))
    repo = RepositorioFake(tmp_path)
    assert len(repo.categorias()) == 1
    assert repo.usuario_existe(ID_ANCORA)


# -- buscador ----------------------------------------------------------------------


def _ids(trechos: list[Trecho]) -> list[str]:
    return [t.doc_id for t in trechos]


def test_buscador_escopo_e_coorte(buscador):
    trechos = buscador.buscar(ID_ANCORA, "aluguel", 10, 202512)
    assert set(_ids(trechos)) == {
        "anc-202503",
        "anc-202509",
        "anc-anual",
        "coo-geral",
        "coo-202510",
    }
    for trecho in trechos:
        assert trecho.origem.id_usuario == ID_ANCORA or trecho.tipo == "coorte"


def test_buscador_corte_temporal_e_anomes_nulo(buscador):
    trechos = buscador.buscar(ID_ANCORA, "aluguel", 10, 202506)
    assert set(_ids(trechos)) == {"anc-202503", "anc-anual", "coo-geral"}
    assert all(t.anomes is None or t.anomes <= 202506 for t in trechos)


def test_buscador_nunca_devolve_outro_cliente(buscador):
    assert "ctl-202503" not in _ids(buscador.buscar(ID_ANCORA, "aluguel mercado", 10, 202512))
    do_controle = buscador.buscar(ID_CONTROLE, "aluguel mercado", 10, 202512)
    assert {t.origem.id_usuario for t in do_controle} <= {ID_CONTROLE, None}
    assert "ctl-202503" in _ids(do_controle)


def test_buscador_ordena_por_relevancia_e_doc_id(buscador):
    trechos = buscador.buscar(ID_ANCORA, "Quanto gastei com restaurantes?", 10, 202512)
    assert _ids(trechos)[:2] == ["anc-202509", "coo-202510"]
    assert trechos[0].score > trechos[-1].score
    assert all(0.0 <= t.score <= 1.0 for t in trechos)
    # empates (sem sobreposição) seguem a ordem de doc_id
    empatados = [t.doc_id for t in trechos if t.score == 0.0]
    assert empatados == sorted(empatados)


def test_buscador_respeita_k_e_e_deterministico(buscador):
    primeiro = buscador.buscar(ID_ANCORA, "aluguel", 2, 202512)
    assert len(primeiro) == 2
    assert primeiro == buscador.buscar(ID_ANCORA, "aluguel", 2, 202512)
    assert buscador.buscar(ID_ANCORA, "aluguel", 0, 202512) == []


def test_buscador_ignora_acentos_e_caixa(buscador):
    assert _ids(buscador.buscar(ID_ANCORA, "MARÇO", 1, 202512)) == ["anc-202503"]


def test_tokens():
    assert tokens("Quanto gastei com Aluguel em março?") == {"gastei", "aluguel", "marco"}
