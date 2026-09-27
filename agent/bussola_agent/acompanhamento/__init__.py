"""F6: acompanhamento com replay temporal (ciclo 006).

Carregado por ``extensoes.carregar_extensoes()``. Ao importar, registra:

- ``avancar_mes`` e ``status_plano`` (livres);
- ``ajustar_plano`` (sensível: passa pelo gate de consentimento do 005);
- as instruções do ACOMPANHAR nas ordens 70–89.

O registro é idempotente. O 006 não registra callbacks.
"""

from bussola_agent import extensoes
from bussola_agent.acompanhamento.instructions import INSTRUCTIONS
from bussola_agent.acompanhamento.tools import ajustar_plano, avancar_mes, status_plano

FREE_TOOLS = (avancar_mes, status_plano)
SENSITIVE_TOOLS = (ajustar_plano,)

__all__ = ["FREE_TOOLS", "SENSITIVE_TOOLS", "register"]


def register() -> None:
    """Registra ferramentas e instruções em ``extensoes`` (só uma vez por registro limpo)."""
    registered = {getattr(fn, "__name__", "") for fn in extensoes.ferramentas()}
    if avancar_mes.__name__ in registered:
        return
    for fn in FREE_TOOLS:
        extensoes.registrar_ferramenta(fn)
    for fn in SENSITIVE_TOOLS:
        extensoes.registrar_ferramenta(fn, sensivel=True)
    for order, text in INSTRUCTIONS:
        extensoes.registrar_instrucao(order, text)


register()
