"""Result envelopes of the local governance tools (contratos §5 and §6).

- success: ``{dados, fonte: {ferramenta, tabelas, periodo}, avisos}``, with
  ``periodo = None`` when the tool reads no monthly data (same as the 004 tools);
- failure: ``{erro: {codigo, mensagem}}``, returned as the tool result (never
  raised). Messages are customer-facing pt-BR and never echo input values.
"""

import json
from collections.abc import Iterable, Mapping
from typing import Any

# Local agent error codes (contratos §6), besides the MCP ones.
CONSENT_REQUIRED = "CONSENTIMENTO_NECESSARIO"
NOT_ALLOWED = "NAO_PERMITIDO"
PRODUCT_NOT_IN_CATALOG = "PRODUTO_FORA_DO_CATALOGO"
INVALID_INPUT = "ENTRADA_INVALIDA"
UNAVAILABLE = "INDISPONIVEL"

# Codes that mean "stopped by governance" rather than "the tool failed".
BLOCKING_CODES = frozenset({CONSENT_REQUIRED, NOT_ALLOWED})


def ok(
    dados: Mapping[str, Any],
    ferramenta: str,
    tabelas: Iterable[str],
    ate_anomes: int | None,
    avisos: Iterable[str] = (),
    periodo: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Success envelope. ``periodo`` defaults to ``{inicio, fim}`` = ``ate_anomes``."""
    if periodo is None and ate_anomes is not None:
        periodo = {"inicio": ate_anomes, "fim": ate_anomes}
    fonte: dict[str, Any] = {
        "ferramenta": ferramenta,
        "tabelas": list(tabelas),
        "periodo": dict(periodo) if periodo is not None else None,
    }
    return {"dados": dict(dados), "fonte": fonte, "avisos": list(avisos)}


def error(codigo: str, mensagem: str) -> dict[str, Any]:
    return {"erro": {"codigo": codigo, "mensagem": mensagem}}


def error_code(response: Any) -> str | None:
    """Error code of a tool result, looking inside the MCP wrappers.

    Handles ``{erro}``, ``isError``, ``structuredContent``/``result`` and text
    parts holding a JSON envelope. ``None`` means success.
    """
    if not isinstance(response, Mapping):
        return None
    erro = response.get("erro")
    if isinstance(erro, Mapping):
        codigo = erro.get("codigo")
        return codigo if isinstance(codigo, str) and codigo else "ERRO"
    for key in ("structuredContent", "result"):
        nested = error_code(response.get(key))
        if nested:
            return nested
    content = response.get("content")
    for part in content if isinstance(content, list) else ():
        if isinstance(part, Mapping) and part.get("type") == "text":
            try:
                nested = error_code(json.loads(part.get("text") or ""))
            except ValueError:
                continue
            if nested:
                return nested
    if response.get("isError") is True or response.get("is_error") is True:
        return "ERRO"
    return None
