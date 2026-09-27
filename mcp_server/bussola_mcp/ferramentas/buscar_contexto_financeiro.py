"""Tool ``buscar_contexto_financeiro`` (P0, contratos §5; corpus of Q-17).

The searcher receives only ``pergunta``, ``k`` and ``tema``: the corpus is
general knowledge, without client data. ``id_usuario`` and ``ate_anomes`` are
still validated (session scope and cut) but never reach the searcher.
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from bussola_mcp.contratos import (
    ANOMES_MIN,
    AVISO_CONHECIMENTO,
    AVISO_SEM_TRECHOS,
    DadosBuscarContexto,
    EntradaBuscarContexto,
    Periodo,
)
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.ports import Computation, ToolDependencies
from bussola_mcp.ferramentas.registry import TOOL_ANNOTATIONS

NAME = "buscar_contexto_financeiro"


def compute(deps: ToolDependencies, entrada: EntradaBuscarContexto) -> Computation:
    trechos = deps.searcher.buscar(entrada.pergunta, entrada.k, entrada.tema)
    avisos = (AVISO_CONHECIMENTO,) if trechos else (AVISO_CONHECIMENTO, AVISO_SEM_TRECHOS)
    return Computation(
        dados=DadosBuscarContexto(trechos=trechos),
        periodo=Periodo(inicio=ANOMES_MIN, fim=entrada.ate_anomes),
        avisos=avisos,
    )


def register(server: FastMCP, runner: ToolRunner) -> None:
    @server.tool(name=NAME, annotations=TOOL_ANNOTATIONS)
    def buscar_contexto_financeiro(
        id_usuario: str,
        ate_anomes: int,
        pergunta: str,
        k: int = 5,
        tema: str | None = None,
    ) -> dict[str, Any]:
        """Trechos da base de conhecimento: normas do BACEN, crédito, boas práticas e produtos.

        Conteúdo geral, não é dado do cliente. ``tema`` opcional: ``norma_bacen``,
        ``credito``, ``boas_praticas`` ou ``produto`` (catálogo, sem taxas). Até ``k``
        trechos (de 1 a 10), com a fonte. ``pergunta`` com até 500 caracteres.
        """
        return runner.run(
            NAME,
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "pergunta": pergunta,
                "k": k,
                "tema": tema,
            },
            compute,
        )
