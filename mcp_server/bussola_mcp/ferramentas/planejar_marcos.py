"""Tool ``planejar_marcos``: intermediate milestones (cycle 009, contratos §5).

Full contract in ``specs/009-marcos-financeiros/contracts/planejar_marcos.md``.

``PRAZO_IMPLAUSIVEL`` is only raised by the runner when ``prazo_meses`` arrives
outside 1–360. A **computed** term above ``RegrasMarco.prazo_maximo_marco``
becomes ``trajetoria_incerta`` instead of an error, because answering "not
viable" is exactly what this tool exists to avoid (FR-010, SC-008).
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaPlanejarMarcos
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "planejar_marcos"


def compute(deps: ToolDependencies, entrada: EntradaPlanejarMarcos) -> Computation:
    return deps.computations.planejar_marcos(
        entrada.id_usuario,
        entrada.ate_anomes,
        entrada.valor_alvo,
        entrada.prazo_meses,
        entrada.prioridade,
        entrada.usar_saldo_atual,
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def planejar_marcos(
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int,
        prioridade: str | None = None,
        usar_saldo_atual: bool = True,
    ) -> dict[str, Any]:
        """Marcos intermediários quando o objetivo não cabe nas condições atuais.

        Use quando `simular_objetivo` voltar `viavel = false`, quando nenhum
        cenário de `comparar_cenarios` couber, ou quando o objetivo estiver
        claramente distante da situação do cliente. Devolve os motivos, o
        próximo marco e a trajetória — nunca um veredito de inviabilidade.
        """
        return runner.run(
            NAME,
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "valor_alvo": valor_alvo,
                "prazo_meses": prazo_meses,
                "prioridade": prioridade,
                "usar_saldo_atual": usar_saldo_atual,
            },
            compute,
        )
