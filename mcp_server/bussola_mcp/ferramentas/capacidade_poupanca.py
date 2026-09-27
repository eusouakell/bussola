"""Tool ``capacidade_poupanca`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaCapacidadePoupanca
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "capacidade_poupanca"


def compute(deps: ToolDependencies, entrada: EntradaCapacidadePoupanca) -> Computation:
    return deps.computations.capacidade_poupanca(entrada.id_usuario, entrada.ate_anomes)


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def capacidade_poupanca(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Sobra média e mediana, desvio padrão e meses negativos até o corte.

        Use para saber quanto o cliente consegue guardar por mês e com que
        regularidade.
        """
        return runner.run(NAME, {"id_usuario": id_usuario, "ate_anomes": ate_anomes}, compute)
