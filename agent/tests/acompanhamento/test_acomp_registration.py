"""Registro do pacote em ``extensoes``: ferramentas, sensibilidade e instruções (contrato)."""

import importlib

from google.adk.tools import FunctionTool

import bussola_agent.acompanhamento as acompanhamento
from bussola_agent import callbacks, extensoes
from bussola_agent.acompanhamento.instructions import INSTRUCTIONS


def _names() -> list[str]:
    return [fn.__name__ for fn in extensoes.ferramentas()]


def test_register_adds_the_three_tools_and_marks_only_ajustar_plano() -> None:
    acompanhamento.register()
    assert _names() == ["avancar_mes", "status_plano", "ajustar_plano"]
    assert extensoes.ferramentas_sensiveis() == {"ajustar_plano"}


def test_register_is_idempotent() -> None:
    acompanhamento.register()
    acompanhamento.register()
    assert _names() == ["avancar_mes", "status_plano", "ajustar_plano"]
    assert extensoes.instrucoes().count("## Acompanhamento mês a mês") == 1


def test_instructions_use_only_the_reserved_orders() -> None:
    assert all(70 <= order <= 89 for order, _ in INSTRUCTIONS)
    acompanhamento.register()
    text = extensoes.instrucoes()
    assert text.index("avancar_mes()") < text.index("ajustar_plano(rota=")
    assert '"avançar um mês"' in text
    assert "Ver status do plano" in text


def test_carregar_extensoes_finds_the_real_package() -> None:
    importlib.reload(acompanhamento)  # simula o primeiro import feito pelo agent.py
    extensoes.carregar_extensoes()
    assert set(_names()) >= {"avancar_mes", "status_plano", "ajustar_plano"}


def test_the_package_registers_no_callbacks() -> None:
    acompanhamento.register()
    for phase in ("before_model", "after_model", "before_tool", "after_tool"):
        assert callbacks.registrados(phase) == []


def _schema(declaration: object) -> dict:
    """Propriedades e obrigatórios da declaração (JSON Schema ou ``Schema`` do genai)."""
    json_schema = getattr(declaration, "parameters_json_schema", None)
    if json_schema:
        return {
            "properties": set(json_schema.get("properties") or {}),
            "required": list(json_schema.get("required") or []),
        }
    schema = getattr(declaration, "parameters", None)
    return {
        "properties": set((schema.properties or {}) if schema else {}),
        "required": list((schema.required or []) if schema else []),
    }


def test_tool_declarations_hide_the_scope_and_the_context() -> None:
    acompanhamento.register()
    declarations = {
        fn.__name__: FunctionTool(fn)._get_declaration() for fn in extensoes.ferramentas()
    }
    for declaration in declarations.values():
        assert not _schema(declaration)["properties"] & {"id_usuario", "ate_anomes", "tool_context"}
    adjust = _schema(declarations["ajustar_plano"])
    assert adjust == {"properties": {"rota", "aporte_mensal", "prazo_meses"}, "required": []}
    assert "consentimento" in declarations["ajustar_plano"].description
