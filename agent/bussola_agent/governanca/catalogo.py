"""Action catalog: free, sensitive and forbidden tools; product catalog.

- **Free** tools run without consent: MCP reads, the 004 journey tools,
  ``solicitar_consentimento`` and the 006 read-only tools.
- **Sensitive** tools need an ``aceito`` consent that has not been used yet.
  Any tool that is not known as free is sensitive (fail closed), and so is
  anything registered with ``extensoes.registrar_ferramenta(fn, sensivel=True)``.
- **Forbidden** tools are always refused (``NAO_PERMITIDO``), with or without
  consent: ``compartilhar_dados`` in the PoC.

The product catalog is a copy of ``contracts/catalogo_produtos.json`` (the
agent image does not ship ``contracts/``). A test keeps both files equal.
"""

import json
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from bussola_agent import extensoes
from bussola_agent.mcp_conexao import FERRAMENTAS_MCP

# MCP tools (contratos §5): read only. ``referencia_coorte`` is the P1 tool of §5.
MCP_TOOLS: frozenset[str] = frozenset({*FERRAMENTAS_MCP, "referencia_coorte"})
# Local tools that only read or register what the customer said (004, 005, 006).
LOCAL_FREE_TOOLS: frozenset[str] = frozenset(
    {
        "registrar_objetivo",
        "escolher_cenario",
        "solicitar_consentimento",
        "avancar_mes",
        "status_plano",
    }
)
FREE_TOOLS: frozenset[str] = MCP_TOOLS | LOCAL_FREE_TOOLS

# Sensitive actions known to the catalog (contratos §6), with their pt-BR label.
SENSITIVE_ACTIONS: dict[str, str] = {
    "criar_plano": "criar o seu plano",
    "ativar_lembretes": "ativar lembretes do plano",
    "simular_contratacao": "simular a contratação de um produto",
    "compartilhar_dados": "compartilhar os seus dados",
    "ajustar_plano": "ajustar o seu plano",
}
FORBIDDEN_ACTIONS: frozenset[str] = frozenset({"compartilhar_dados"})

REQUEST_CONSENT_TOOL = "solicitar_consentimento"


def is_free(tool_name: str) -> bool:
    """True for a known free tool that no extension marked as sensitive."""
    return tool_name in FREE_TOOLS and tool_name not in extensoes.ferramentas_sensiveis()


def is_sensitive(tool_name: str) -> bool:
    """Everything that is not free is sensitive, including unknown tools."""
    return not is_free(tool_name)


def is_forbidden(tool_name: str) -> bool:
    return tool_name in FORBIDDEN_ACTIONS


def action_label(action: str) -> str:
    """pt-BR label for the consent text (``"executar esta ação"`` if unknown)."""
    return SENSITIVE_ACTIONS.get(action, "executar esta ação")


@dataclass(frozen=True)
class Product:
    produto_id: str
    nome: str
    categoria: str
    uso: str
    cuidado: str
    fonte_oficial: str
    acao_simulada: bool


@cache
def _raw_catalog() -> tuple[dict[str, Any], ...]:
    text = resources.files(__package__).joinpath("catalogo_produtos.json").read_text("utf-8")
    return tuple(json.loads(text))


def products() -> tuple[Product, ...]:
    return tuple(Product(**item) for item in _raw_catalog())


def simulable_product(produto_id: object) -> Product | None:
    """The catalog product with ``acao_simulada = true`` and this id, or ``None``."""
    if not isinstance(produto_id, str):
        return None
    key = produto_id.strip().lower()
    for product in products():
        if product.produto_id == key and product.acao_simulada:
            return product
    return None
