"""Instruction of the journey agent (FR-004–FR-006; AC-04, AC-05; spec D-05, D-07)."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from google.adk.utils.instructions_utils import _TEMPLATE_VAR_PATTERN, inject_session_state

from bussola_agent.estado import estado_inicial
from bussola_agent.prompts import (
    CATALOG,
    PLACEHOLDERS,
    base_instruction,
    build_instruction,
    render_catalog,
)

RAIZ = Path(__file__).resolve().parents[3]
ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"


def _context(state: dict) -> SimpleNamespace:
    session = SimpleNamespace(state=state, app_name="a", user_id="u", id="s")
    return SimpleNamespace(
        _invocation_context=SimpleNamespace(session=session, artifact_service=None),
        agent_name="bussola",
    )


def test_only_the_known_placeholders_appear() -> None:
    found = set(_TEMPLATE_VAR_PATTERN.findall(base_instruction()))
    assert found == set(PLACEHOLDERS)


async def test_renders_with_the_session_state() -> None:
    state = {
        **estado_inicial(ANCORA, 202506),
        "estado_jornada": "ORIENTAR",
        "objetivo": {"tipo": "imovel", "valor_alvo": 60000.0, "prazo_meses": 24},
    }
    text = await inject_session_state(build_instruction(), _context(state))
    assert "Etapa atual da jornada: ORIENTAR" in text
    assert "'valor_alvo': 60000.0" in text
    assert "(AAAAMM): 202506" in text
    assert all(placeholder not in text for placeholder in PLACEHOLDERS)


async def test_renders_with_an_empty_state() -> None:
    text = await inject_session_state(build_instruction(), _context({}))
    assert "Etapa atual da jornada: \n" in text
    assert "{" not in text


def test_catalog_is_equal_to_the_contract() -> None:
    contract = json.loads((RAIZ / "contracts" / "catalogo_produtos.json").read_text("utf-8"))
    assert list(CATALOG) == contract


def test_catalog_render_has_no_rates_or_conditions() -> None:
    render = render_catalog()
    without_links = re.sub(r"https://\S+", "", render)
    assert not re.search(r"\d", without_links)
    assert "%" not in render
    assert "{" not in render and "}" not in render
    for item in CATALOG:
        assert item["nome"] in render and item["fonte_oficial"] in render


@pytest.mark.parametrize(
    "rule",
    [
        "Resolução Conjunta nº 8",
        "IA responsável",
        "**Diagnóstico**",
        "**Simulação**",
        "**Recomendação**",
        "Nunca pergunte renda",
        "vem de uma ferramenta chamada neste turno",
        "Fonte: perfil financeiro, jan–jun/2025",
        "Não faça contas",
        "quantos meses passam do prazo",
        "O recomendado é sempre o caminho viável",
        "simular_objetivo com aporte_mensal",
        "Nunca prometa nem garanta aprovação de crédito",
        "Nunca contrate, compre, invista",
        "Nunca peça, aceite nem use outro identificador",
        "Nunca informe taxas",
        "registrar_objetivo",
        "escolher_cenario",
        "comparar_cenarios",
    ],
)
def test_fixed_rules_are_in_the_prompt(rule: str) -> None:
    assert rule in base_instruction()


@pytest.mark.parametrize("stage", ["OBJETIVO", "ENTENDER", "ANTECIPAR", "ORIENTAR", "AGIR"])
def test_every_stage_has_a_behavior(stage: str) -> None:
    assert f"- {stage}:" in base_instruction()


def test_extension_texts_come_after_the_base() -> None:
    extra = "## Consentimento\nPeça autorização antes de criar o plano."
    text = build_instruction(extra)
    assert text.startswith(base_instruction())
    assert text.rstrip().endswith("Peça autorização antes de criar o plano.")
    assert build_instruction("") == base_instruction()
    assert build_instruction("   ") == base_instruction()
