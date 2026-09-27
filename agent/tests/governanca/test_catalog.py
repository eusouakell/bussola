"""Action catalog: free, sensitive (fail closed) and forbidden; product catalog."""

import json
from pathlib import Path

import pytest

from bussola_agent import extensoes
from bussola_agent.governanca import catalogo
from bussola_agent.mcp_conexao import FERRAMENTAS_MCP

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("name", sorted({*FERRAMENTAS_MCP, "referencia_coorte"}))
def test_mcp_tools_are_free(name: str) -> None:
    assert catalogo.is_free(name)
    assert not catalogo.is_sensitive(name)


@pytest.mark.parametrize(
    "name", ["registrar_objetivo", "escolher_cenario", "solicitar_consentimento", "avancar_mes"]
)
def test_journey_tools_are_free(name: str) -> None:
    assert catalogo.is_free(name)


@pytest.mark.parametrize(
    "name",
    [
        "criar_plano",
        "ativar_lembretes",
        "simular_contratacao",
        "ajustar_plano",
        "compartilhar_dados",
    ],
)
def test_actions_are_sensitive(name: str) -> None:
    assert catalogo.is_sensitive(name)


@pytest.mark.parametrize("name", ["transferir_pix", "", "resumo_mes_v2", "CRIAR_PLANO"])
def test_unknown_tools_are_sensitive(name: str) -> None:
    assert catalogo.is_sensitive(name)


def test_extension_can_mark_a_free_name_as_sensitive() -> None:
    def status_plano() -> dict:
        return {}

    assert catalogo.is_free("status_plano")
    extensoes.registrar_ferramenta(status_plano, sensivel=True)
    assert catalogo.is_sensitive("status_plano")


def test_only_share_data_is_forbidden() -> None:
    assert catalogo.FORBIDDEN_ACTIONS == frozenset({"compartilhar_dados"})
    assert catalogo.is_forbidden("compartilhar_dados")
    assert not catalogo.is_forbidden("criar_plano")


def test_action_label() -> None:
    assert catalogo.action_label("criar_plano") == "criar o seu plano"
    assert catalogo.action_label("outra") == "executar esta ação"


def test_product_catalog_copy_matches_the_contract() -> None:
    contract = json.loads((REPO / "contracts" / "catalogo_produtos.json").read_text("utf-8"))
    package = REPO / "agent" / "bussola_agent" / "governanca" / "catalogo_produtos.json"
    assert json.loads(package.read_text("utf-8")) == contract


def test_simulable_products() -> None:
    assert catalogo.simulable_product("credito_imobiliario").nome
    assert catalogo.simulable_product(" Reserva_Objetivo ").produto_id == "reserva_objetivo"
    assert catalogo.simulable_product("cdb_renda_fixa") is None  # acao_simulada = false
    assert catalogo.simulable_product("emprestimo_pessoal") is None
    assert catalogo.simulable_product(None) is None
    for product in catalogo.products():
        assert product.fonte_oficial.startswith("https://")
