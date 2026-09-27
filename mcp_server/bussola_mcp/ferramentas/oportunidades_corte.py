"""Tool ``oportunidades_corte`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaOportunidadesCorte
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "oportunidades_corte"


def compute(deps: ToolDependencies, entrada: EntradaOportunidadesCorte) -> Computation:
    return deps.computations.oportunidades_corte(
        entrada.id_usuario, entrada.ate_anomes, entrada.top_n
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def oportunidades_corte(id_usuario: str, ate_anomes: int, top_n: int = 5) -> dict[str, Any]:
        """Categorias com maior economia potencial mensal (até ``top_n``, de 1 a 10).

        Use para sugerir onde cortar gastos. Traz a média mensal da categoria, se
        é discricionária e o critério da economia potencial.
        """
        return runner.run(
            NAME, {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "top_n": top_n}, compute
        )
