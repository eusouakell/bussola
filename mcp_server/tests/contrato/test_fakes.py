"""Fakes do domínio: escopo, tempo e busca no corpus de conhecimento (FR-009, FR-010, TS-05,
T015, Q-17)."""

import inspect
import json
import uuid
from pathlib import Path

import pytest

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE, TemaConhecimento, Trecho
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
    assert BuscadorFake(tmp_path / "nao_existe").buscar("rotativo do cartão", 5) == []


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
    return [t.trecho_id for t in trechos]


def test_buscador_nao_recebe_cliente_nem_corte():
    """Conhecimento geral: sem ``id_usuario`` nem ``ate_anomes`` (Q-17)."""
    parametros = list(inspect.signature(BuscadorFake.buscar).parameters)
    assert parametros == ["self", "pergunta", "k", "tema"]


def test_buscador_devolve_so_trechos_relevantes(buscador):
    trechos = buscador.buscar("Como funciona o rotativo do cartão?", 10)
    assert _ids(trechos) == ["rotativo#1", "teto-juros#1"]
    assert all(t.score > 0 for t in trechos)
    assert buscador.buscar("Qual a previsão do tempo?", 5) == []


def test_buscador_ordena_por_score_e_trecho_id(buscador):
    trechos = buscador.buscar("juros do rotativo do cartão", 10)
    assert _ids(trechos) == ["teto-juros#1", "rotativo#1", "cet#1"]
    assert [t.score for t in trechos] == [1.0, 0.6667, 0.3333]


def test_buscador_filtra_por_tema(buscador):
    assert buscador.buscar("juros do rotativo do cartão", 10, TemaConhecimento.CREDITO) == []
    trechos = buscador.buscar("Onde consultar minhas dívidas?", 10, TemaConhecimento.CREDITO)
    assert _ids(trechos) == ["registrato#1"]
    assert trechos[0].tema == TemaConhecimento.CREDITO


def test_buscador_devolve_titulo_e_fonte(buscador):
    (trecho,) = buscador.buscar("reserva de emergência", 1)
    assert trecho.doc_id == "reserva"
    assert trecho.titulo == "Reserva de emergência"
    assert trecho.tema == TemaConhecimento.BOAS_PRATICAS
    assert trecho.fonte.referencia == "Norma reserva"


def test_buscador_respeita_k_e_e_deterministico(buscador):
    primeiro = buscador.buscar("juros do rotativo do cartão", 2)
    assert len(primeiro) == 2
    assert primeiro == buscador.buscar("juros do rotativo do cartão", 2)
    assert buscador.buscar("juros do rotativo do cartão", 0) == []


def test_buscador_ignora_acentos_e_caixa(buscador):
    assert _ids(buscador.buscar("DÍVIDAS", 1)) == ["registrato#1"]


def test_tokens():
    assert tokens("Quanto gastei com Aluguel em março?") == {"gastei", "aluguel", "marco"}
