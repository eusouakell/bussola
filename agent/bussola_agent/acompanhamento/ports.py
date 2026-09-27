"""Portas do acompanhamento: ferramentas MCP e registro da aplicação.

- :class:`McpGateway` é a porta das duas ferramentas MCP usadas pelo 006
  (``resumo_mes`` e ``simular_objetivo``). O adaptador padrão,
  :class:`McpToolGateway`, usa ``mcp_conexao.chamar_ferramenta``, que força
  ``id_usuario`` e ``ate_anomes`` a partir do state recebido.
- O registro é a porta ``persistencia.RegistroApp`` do 000. O padrão é um
  ``RegistroEmMemoria`` único por processo. O 005 (ou quem montar o agente)
  liga o ``RegistroBigQuery`` com :func:`configure_registry`.
"""

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from bussola_agent import mcp_conexao
from bussola_agent.persistencia import RegistroApp, RegistroEmMemoria

TOOL_MONTHLY_SUMMARY = "resumo_mes"
TOOL_SIMULATE_GOAL = "simular_objetivo"


@runtime_checkable
class McpGateway(Protocol):
    async def monthly_summary(self, anomes: int, state: Mapping[str, Any]) -> dict[str, Any]: ...

    async def simulate_goal(
        self,
        valor_alvo: float,
        state: Mapping[str, Any],
        prazo_meses: int | None = None,
        aporte_mensal: float | None = None,
    ) -> dict[str, Any]: ...


class McpToolGateway:
    """Adaptador sobre ``mcp_conexao.chamar_ferramenta`` (envelope §5, nunca levanta)."""

    async def monthly_summary(self, anomes: int, state: Mapping[str, Any]) -> dict[str, Any]:
        return await mcp_conexao.chamar_ferramenta(TOOL_MONTHLY_SUMMARY, {"anomes": anomes}, state)

    async def simulate_goal(
        self,
        valor_alvo: float,
        state: Mapping[str, Any],
        prazo_meses: int | None = None,
        aporte_mensal: float | None = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {"valor_alvo": valor_alvo}
        if prazo_meses is not None:
            args["prazo_meses"] = prazo_meses
        if aporte_mensal is not None:
            args["aporte_mensal"] = aporte_mensal
        return await mcp_conexao.chamar_ferramenta(TOOL_SIMULATE_GOAL, args, state)


_gateway: McpGateway | None = None
_registry: RegistroApp | None = None
_default_registry: RegistroEmMemoria | None = None


def configure_gateway(gateway: McpGateway | None) -> None:
    """Troca o gateway MCP (``None`` volta ao :class:`McpToolGateway`)."""
    global _gateway
    _gateway = gateway


def get_gateway() -> McpGateway:
    return _gateway if _gateway is not None else McpToolGateway()


def configure_registry(registry: RegistroApp | None) -> None:
    """Troca o registro da aplicação (``None`` volta ao ``RegistroEmMemoria`` padrão)."""
    global _registry
    if registry is not None and not isinstance(registry, RegistroApp):
        raise TypeError("O registro deve implementar persistencia.RegistroApp.")
    _registry = registry


def get_registry() -> RegistroApp:
    global _default_registry
    if _registry is not None:
        return _registry
    if _default_registry is None:
        _default_registry = RegistroEmMemoria()
    return _default_registry


def reset() -> None:
    """Volta aos adaptadores padrão, com um registro em memória novo. Só para testes."""
    global _gateway, _registry, _default_registry
    _gateway = None
    _registry = None
    _default_registry = None
