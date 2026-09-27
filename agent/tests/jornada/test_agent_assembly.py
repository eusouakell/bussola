"""Montagem do agente da jornada (FR-001–FR-003; AC-01), sem rede e sem modelo."""

import importlib
import sys
from collections.abc import Callable
from types import ModuleType

import pytest
from google.adk.tools.function_tool import FunctionTool
from google.genai import types

import bussola_agent
from bussola_agent.prompts import base_instruction, build_instruction


@pytest.fixture
def agent_module(monkeypatch: pytest.MonkeyPatch) -> Callable[[], ModuleType]:
    monkeypatch.setenv("ADK_DISABLE_LOAD_DOTENV", "TRUE")
    for key in ("BUSSOLA_MODEL", "MCP_URL", "ANCHOR_USER_ID", "REPLAY_START_ANOMES"):
        monkeypatch.delenv(key, raising=False)

    def load() -> ModuleType:
        monkeypatch.delitem(sys.modules, "bussola_agent.agent", raising=False)
        monkeypatch.delattr(bussola_agent, "agent", raising=False)
        return importlib.import_module("bussola_agent.agent")

    return load


def test_instruction_is_the_journey_prompt(agent_module: Callable[[], ModuleType]) -> None:
    agent = agent_module().root_agent
    assert agent.instruction == build_instruction("") == base_instruction()
    assert "{estado_jornada?}" in agent.instruction
    assert "{objetivo?}" in agent.instruction


def test_safety_settings_block_medium_and_above(agent_module: Callable[[], ModuleType]) -> None:
    config = agent_module().root_agent.generate_content_config
    assert config is not None
    medium = types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    settings = {s.category: s.threshold for s in config.safety_settings or []}
    assert settings == {
        types.HarmCategory.HARM_CATEGORY_HARASSMENT: medium,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH: medium,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: medium,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: medium,
    }


@pytest.mark.parametrize(
    ("tool", "required", "optional"),
    [
        (
            "registrar_objetivo",
            {"tipo", "descricao"},
            {"valor_alvo", "prazo_meses", "prioridade"},
        ),
        ("escolher_cenario", {"nome"}, set()),
    ],
)
def test_local_tools_hide_tool_context_from_the_model(
    agent_module: Callable[[], ModuleType], tool: str, required: set[str], optional: set[str]
) -> None:
    functions = {f.__name__: f for f in agent_module().root_agent.tools[1:3]}
    declaration = FunctionTool(functions[tool])._get_declaration()
    assert declaration is not None and declaration.name == tool
    schema = declaration.parameters_json_schema
    assert isinstance(schema, dict)
    assert set(schema["properties"]) == required | optional
    assert set(schema.get("required", [])) == required
    assert "tool_context" not in schema["properties"]


def test_description_is_pt_br(agent_module: Callable[[], ModuleType]) -> None:
    assert "objetivo financeiro" in agent_module().root_agent.description
