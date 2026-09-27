"""Tool ``simular_objetivo`` (P0, contratos §5)."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import EntradaSimularObjetivo
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "simular_objetivo"


def compute(deps: ToolDependencies, entrada: EntradaSimularObjetivo) -> Computation:
    return deps.computations.simular_objetivo(
        entrada.id_usuario,
        entrada.ate_anomes,
        entrada.valor_alvo,
        entrada.prazo_meses,
        entrada.aporte_mensal,
        entrada.usar_saldo_atual,
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def simular_objetivo(
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int | None = None,
        aporte_mensal: float | None = None,
        usar_saldo_atual: bool = False,
    ) -> dict[str, Any]:
        """Aporte para um prazo ou prazo para um aporte. Informe exatamente um dos dois.

        ``valor_alvo`` em reais (> 0). ``prazo_meses`` de 1 a 360 calcula o aporte
        mensal; ``aporte_mensal`` (> 0) calcula o prazo. Diz se o objetivo cabe
        na capacidade de poupança do cliente e com que folga.
        """
        return runner.run(
            NAME,
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "valor_alvo": valor_alvo,
                "prazo_meses": prazo_meses,
                "aporte_mensal": aporte_mensal,
                "usar_saldo_atual": usar_saldo_atual,
            },
            compute,
        )
