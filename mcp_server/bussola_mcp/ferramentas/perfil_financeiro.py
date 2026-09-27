"""Tool ``perfil_financeiro`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaPerfilFinanceiro
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "perfil_financeiro"


def compute(deps: ToolDependencies, entrada: EntradaPerfilFinanceiro) -> Computation:
    return deps.computations.perfil_financeiro(entrada.id_usuario, entrada.ate_anomes)


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def perfil_financeiro(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Renda, gasto e sobra médios, fontes de renda, saldo e série mensal até o corte.

        Use para descrever a situação financeira do cliente. Valores em reais,
        calculados sobre os meses de ``fonte.periodo``.
        """
        return runner.run(NAME, {"id_usuario": id_usuario, "ate_anomes": ate_anomes}, compute)
