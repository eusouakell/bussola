"""MCP tools of the Bússola, one module per tool (contratos §5, cycle 003).

Each module exposes ``NAME``, ``compute(deps, entrada) -> Computation`` and
``register(server, runner)``. :func:`register_all` registers the 9 tools of
``contratos.FERRAMENTAS`` on a FastMCP server with the injected ports.
"""

from types import ModuleType

from mcp.server.fastmcp import FastMCP

from bussola_mcp.ferramentas import (
    buscar_contexto_financeiro,
    capacidade_poupanca,
    comparar_cenarios,
    dividas_e_parcelas,
    oportunidades_corte,
    perfil_financeiro,
    referencia_coorte,
    resumo_mes,
    simular_objetivo,
)
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import ToolDependencies

TOOL_MODULES: tuple[ModuleType, ...] = (
    perfil_financeiro,
    capacidade_poupanca,
    oportunidades_corte,
    dividas_e_parcelas,
    simular_objetivo,
    comparar_cenarios,
    buscar_contexto_financeiro,
    resumo_mes,
    referencia_coorte,
)


def register_all(server: FastMCP, deps: ToolDependencies) -> ToolRunner:
    """Registers every tool on ``server`` and returns the shared runner."""
    runner = ToolRunner(deps)
    for module in TOOL_MODULES:
        module.register(server, runner)
    return runner


__all__ = ["TOOL_MODULES", "register_all"]
