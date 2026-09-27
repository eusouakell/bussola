"""Tool ``referencia_coorte`` (P1, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaReferenciaCoorte
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "referencia_coorte"


def compute(deps: ToolDependencies, entrada: EntradaReferenciaCoorte) -> Computation:
    return deps.computations.referencia_coorte(
        entrada.id_usuario, entrada.ate_anomes, entrada.categoria
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def referencia_coorte(id_usuario: str, ate_anomes: int, categoria: str) -> dict[str, Any]:
        """Média e mediana mensais de gasto na categoria entre clientes da mesma faixa de renda.

        ``categoria`` é a macro (ex.: ``Lazer``, ``Restaurantes``). Referência
        agregada, sem dado individual de outros clientes. Use para comparar o
        gasto do cliente com o de clientes parecidos.
        """
        return runner.run(
            NAME,
            {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "categoria": categoria},
            compute,
        )
