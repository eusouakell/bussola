"""Tool ``comparar_cenarios`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaCompararCenarios
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "comparar_cenarios"


def compute(deps: ToolDependencies, entrada: EntradaCompararCenarios) -> Computation:
    return deps.computations.comparar_cenarios(
        entrada.id_usuario, entrada.ate_anomes, entrada.valor_alvo, entrada.prazo_meses
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def comparar_cenarios(
        id_usuario: str, ate_anomes: int, valor_alvo: float, prazo_meses: int
    ) -> dict[str, Any]:
        """Cenários conservador, equilibrado e acelerado para o objetivo.

        ``valor_alvo`` em reais (> 0) e ``prazo_meses`` de 1 a 360. Cada cenário
        traz aporte, prazo, viabilidade, cortes sugeridos e trade-offs.
        """
        return runner.run(
            NAME,
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "valor_alvo": valor_alvo,
                "prazo_meses": prazo_meses,
            },
            compute,
        )
