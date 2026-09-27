"""Instruction of the Bússola agent (004 §3.2).

:func:`build_instruction` joins the base prompt, the curated catalog and the
extension texts of 005/006 (``extensoes.instrucoes()``), in this order. The
result is an ADK template: ``{estado_jornada?}`` and ``{objetivo?}`` are filled
from ``session.state`` on every model call (spec D-07).
"""

from bussola_agent.prompts.base import (
    FORMAT,
    JOURNEY,
    LIMITS,
    NUMBERS,
    OTHER_PATH,
    PERSONA,
    PRODUCTS_HEADER,
    SESSION_CONTEXT,
)
from bussola_agent.prompts.catalog import CATALOG, render_catalog

PLACEHOLDERS: tuple[str, ...] = (
    "{id_usuario?}",
    "{ate_anomes?}",
    "{estado_jornada?}",
    "{objetivo?}",
)


def base_instruction() -> str:
    """Base prompt with the catalog, without the extension texts."""
    sections = (
        PERSONA,
        SESSION_CONTEXT,
        JOURNEY,
        NUMBERS,
        FORMAT,
        OTHER_PATH,
        f"{PRODUCTS_HEADER}\n{render_catalog()}",
        LIMITS,
    )
    return "\n\n".join(sections) + "\n"


def build_instruction(extensions: str = "") -> str:
    """Base prompt followed by the extension texts (already ordered by ``extensoes``)."""
    base = base_instruction()
    extra = extensions.strip()
    return f"{base}\n{extra}\n" if extra else base


__all__ = ["CATALOG", "PLACEHOLDERS", "base_instruction", "build_instruction", "render_catalog"]
