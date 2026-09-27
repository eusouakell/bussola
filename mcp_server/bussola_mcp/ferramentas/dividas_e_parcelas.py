"""Tool ``dividas_e_parcelas`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaDividasParcelas
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "dividas_e_parcelas"


def compute(deps: ToolDependencies, entrada: EntradaDividasParcelas) -> Computation:
    return deps.computations.dividas_e_parcelas(entrada.id_usuario, entrada.ate_anomes)


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def dividas_e_parcelas(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Parcelas ativas, juros pagos em média e comprometimento da renda.

        Use para falar das dívidas e compras parceladas do próprio cliente.
        """
        return runner.run(NAME, {"id_usuario": id_usuario, "ate_anomes": ate_anomes}, compute)
