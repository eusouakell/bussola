"""Tool ``resumo_mes`` (P1, contratos §5; used by the replay of cycle 006)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaResumoMes
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "resumo_mes"


def compute(deps: ToolDependencies, entrada: EntradaResumoMes) -> Computation:
    return deps.computations.resumo_mes(entrada.id_usuario, entrada.ate_anomes, entrada.anomes)


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def resumo_mes(id_usuario: str, ate_anomes: int, anomes: int) -> dict[str, Any]:
        """Renda, gasto, sobra e gastos por macro de um mês (``anomes <= ate_anomes``)."""
        return runner.run(
            NAME, {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "anomes": anomes}, compute
        )
