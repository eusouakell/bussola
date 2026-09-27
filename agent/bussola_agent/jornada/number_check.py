"""Number verification of the final answer (004 §3.5; spec FR-014, D-04).

``after_model`` order 50: every number in the model's final text must come from
the evidence of the turn:

- the tool responses of the current invocation (numbers inside texts too);
- what the client wrote in the session;
- the registered ``objetivo`` and the session ``ate_anomes``.

A number without evidence is logged as ``evento=numero_sem_fonte`` with
``erro_codigo=NUMERO_DIVERGENTE``; the text is never echoed. An answer with
numbers that does not cite a source gets a deterministic footer built from the
``fonte`` of the turn's tools (``FONTE_NAO_CITADA``). The response is changed
in place and the callback returns ``None``, so the chain goes on to order 90.

The pure helpers (:func:`extract_numbers`, :func:`evidence_from`,
:func:`unsupported_numbers`) are shared with ``eval/agente/rodar_eval.py``.
"""

import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from bussola_agent.estado import CHAVE_ATE_ANOMES, CHAVE_ESTADO_JORNADA, CHAVE_OBJETIVO
from bussola_agent.jornada.tool_results import ToolOutcome, tool_outcomes, user_texts
from bussola_agent.logging_json import obter_logger
from bussola_agent.mcp_conexao import FERRAMENTAS_MCP

ORDER = 50
EVENT_UNSUPPORTED_NUMBER = "numero_sem_fonte"
ERROR_DIVERGENT_NUMBER = "NUMERO_DIVERGENTE"
ERROR_SOURCE_NOT_CITED = "FONTE_NAO_CITADA"
EXEMPT_MAX = 10
"""Bare integers from 0 to 10 (steps, "2 anos", "3 caminhos") are not checked."""

UNIT_PERCENT = "%"
UNIT_THOUSAND = "mil"
UNIT_YEARS = "anos"

READABLE_TOOLS: Mapping[str, str] = {
    "perfil_financeiro": "perfil financeiro",
    "capacidade_poupanca": "capacidade de poupança",
    "oportunidades_corte": "oportunidades de corte",
    "dividas_e_parcelas": "dívidas e parcelas",
    "simular_objetivo": "simulação do objetivo",
    "comparar_cenarios": "comparação de cenários",
    "buscar_contexto_financeiro": "base de conhecimento",
    "resumo_mes": "resumo do mês",
}
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")

_URL = re.compile(r"https?://\S+")
_TOKEN = re.compile(
    r"(?<![\w.,])(?P<num>\d+(?:[.,]\d+)*)(?![\dºª°])"
    r"(?P<unit>\s*(?:%|por\s+cento\b|mil\b|anos?\b))?",
    re.IGNORECASE,
)
_SOURCE_CITED = re.compile(r"\bfontes?\b", re.IGNORECASE)

_log = obter_logger(__name__)


@dataclass(frozen=True)
class Claim:
    """A number written in the answer, with its readings (pt-BR and en formats)."""

    token: str
    unit: str
    readings: tuple[tuple[float, int], ...]
    """``(value, decimals)`` pairs; the claim is supported when any reading is."""

    @property
    def exempt(self) -> bool:
        """Bare small integer (no unit, a single reading without decimals)."""
        if self.unit or len(self.readings) != 1:
            return False
        value, decimals = self.readings[0]
        return decimals == 0 and value <= EXEMPT_MAX


def _readings(token: str) -> tuple[tuple[float, int], ...]:
    """Values a token can mean: ``1.250,00`` (pt), ``1,250.00`` (en), ``1.250`` (both)."""
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        whole, _, fraction = token.partition(",")
        readings = [(float(whole.replace(".", "") + "." + (fraction or "0")), len(fraction))]
        if not fraction and token.count(".") == 1:
            readings.append((float(token), 3))
        return tuple(readings)
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", token):
        whole, _, fraction = token.partition(".")
        readings = [(float(whole.replace(",", "") + "." + (fraction or "0")), len(fraction))]
        if not fraction and token.count(",") == 1:
            readings.append((float(token.replace(",", ".")), 3))
        return tuple(readings)
    if re.fullmatch(r"\d+,\d+", token):
        return ((float(token.replace(",", ".")), len(token.split(",")[1])),)
    if re.fullmatch(r"\d+\.\d+", token):
        return ((float(token), len(token.split(".")[1])),)
    if re.fullmatch(r"\d+", token):
        return ((float(token), 0),)
    return ()


def _unit(raw: str | None) -> str:
    text = (raw or "").strip().casefold()
    if not text:
        return ""
    if text == "%" or text.startswith("por"):
        return UNIT_PERCENT
    if text == "mil":
        return UNIT_THOUSAND
    return UNIT_YEARS


def extract_numbers(text: str) -> list[Claim]:
    """Numbers of a pt-BR text (URLs ignored), in order of appearance."""
    claims = []
    for match in _TOKEN.finditer(_URL.sub(" ", text or "")):
        readings = _readings(match.group("num"))
        if readings:
            claims.append(Claim(match.group("num"), _unit(match.group("unit")), readings))
    return claims


def _add_number(evidence: set[float], value: float) -> None:
    if not math.isfinite(value):
        return
    value = abs(value)
    evidence.add(value)
    if value.is_integer():
        integer = int(value)
        if 190001 <= integer <= 210012 and 1 <= integer % 100 <= 12:
            evidence.update({float(integer // 100), float(integer % 100)})  # AAAAMM
        if integer > 0 and integer % 12 == 0:
            evidence.add(float(integer // 12))  # meses → anos


def _collect(value: Any, evidence: set[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        _add_number(evidence, float(value))
    elif isinstance(value, str):
        for claim in extract_numbers(value):
            for number, _ in claim.readings:
                _add_number(evidence, number)
                if claim.unit == UNIT_THOUSAND:
                    _add_number(evidence, number * 1000)
                elif claim.unit == UNIT_YEARS:
                    _add_number(evidence, number * 12)
    elif isinstance(value, Mapping):
        for item in value.values():
            _collect(item, evidence)
    elif isinstance(value, list | tuple):
        for item in value:
            _collect(item, evidence)


def evidence_from(*sources: Any) -> frozenset[float]:
    """Absolute values found in tool responses, client texts and state values."""
    evidence: set[float] = set()
    for source in sources:
        _collect(source, evidence)
    return frozenset(evidence)


def _near(evidence_value: float, claimed: float, decimals: int) -> bool:
    """Formatting tolerance: ``claimed`` is ``evidence_value`` rounded or truncated.

    With ``unit`` the last digit shown, the evidence must lie in
    ``[claimed - unit/2, claimed + unit)``: 691,6 → 692 (rounded) and
    1901,47 → 1901 (truncated) pass; 54,01 → 55 and 1729 → 1730 do not.
    """
    unit = 10.0 ** (-decimals)
    diff = evidence_value - claimed
    return -unit / 2 - 1e-9 <= diff < unit - 1e-9


def is_supported(claim: Claim, evidence: Iterable[float]) -> bool:
    for value in evidence:
        for claimed, decimals in claim.readings:
            if claim.unit == UNIT_PERCENT:
                if _near(value, claimed, decimals) or _near(value * 100, claimed, decimals):
                    return True
            elif claim.unit == UNIT_THOUSAND:
                if _near(value / 1000, claimed, decimals) or _near(value, claimed, decimals):
                    return True
            elif claim.unit == UNIT_YEARS:
                if _near(value, claimed, decimals) or _near(value, claimed * 12, decimals):
                    return True
            elif _near(value, claimed, decimals):
                return True
    return False


def unsupported_numbers(text: str, evidence: Iterable[float]) -> list[Claim]:
    """Non-exempt numbers of ``text`` without evidence."""
    pool = tuple(evidence)
    return [c for c in extract_numbers(text) if not c.exempt and not is_supported(c, pool)]


def checked_numbers(text: str) -> list[Claim]:
    """Non-exempt numbers of ``text`` (the ones the check looks at)."""
    return [c for c in extract_numbers(text) if not c.exempt]


def cites_source(text: str) -> bool:
    return bool(_SOURCE_CITED.search(text or ""))


def _period(period: Any) -> str | None:
    if not isinstance(period, Mapping):
        return None
    start, end = period.get("inicio"), period.get("fim")
    if not (isinstance(start, int) and isinstance(end, int)):
        return None
    if not (1 <= start % 100 <= 12 and 1 <= end % 100 <= 12):
        return None
    first, last = MONTHS[start % 100 - 1], MONTHS[end % 100 - 1]
    if start == end:
        return f"{last}/{end // 100}"
    if start // 100 == end // 100:
        return f"{first}–{last}/{end // 100}"
    return f"{first}/{start // 100}–{last}/{end // 100}"


def source_footer(outcomes: Iterable[ToolOutcome]) -> str | None:
    """``Fonte: perfil financeiro e capacidade de poupança, jan–jun/2025.`` or ``None``."""
    labels: list[str] = []
    periods: list[str] = []
    for outcome in outcomes:
        if not outcome.ok or outcome.name not in FERRAMENTAS_MCP:
            continue
        label = READABLE_TOOLS.get(outcome.name, outcome.name.replace("_", " "))
        if label not in labels:
            labels.append(label)
        source = (outcome.envelope or {}).get("fonte")
        period = _period(source.get("periodo")) if isinstance(source, Mapping) else None
        if period and period not in periods:
            periods.append(period)
    if not labels:
        return None
    names = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " e " + labels[-1]
    suffix = f", {'; '.join(periods)}" if periods else ""
    return f"Fonte: {names}{suffix}."


def _parts(holder: Any) -> list[Any]:
    content = getattr(holder, "content", None)
    return list(getattr(content, "parts", None) or [])


def is_final_text(llm_response: Any) -> bool:
    """Complete model text without a pending function call."""
    if getattr(llm_response, "partial", False) or getattr(llm_response, "error_code", None):
        return False
    parts = _parts(llm_response)
    if any(getattr(p, "function_call", None) for p in parts):
        return False
    return any(getattr(p, "text", None) and not getattr(p, "thought", False) for p in parts)


def _answer_text(llm_response: Any) -> str:
    return "".join(
        p.text for p in _parts(llm_response) if getattr(p, "text", None) and not p.thought
    )


def _client_texts(callback_context: Any, events: list[Any]) -> list[str]:
    texts = user_texts(events)
    current = getattr(callback_context, "user_content", None)
    texts.extend(p.text for p in getattr(current, "parts", None) or [] if getattr(p, "text", None))
    return texts


def check_numbers(callback_context: Any, llm_response: Any) -> None:
    """``after_model`` order 50: logs unsupported numbers and adds the source footer."""
    if not is_final_text(llm_response):
        return None
    text = _answer_text(llm_response)
    claims = checked_numbers(text)
    if not claims:
        return None
    session = getattr(callback_context, "session", None)
    events = list(getattr(session, "events", None) or [])
    outcomes = list(tool_outcomes(events, getattr(callback_context, "invocation_id", None)))
    state = callback_context.state
    evidence = evidence_from(
        [o.envelope if o.envelope is not None else o.response for o in outcomes],
        _client_texts(callback_context, events),
        state.get(CHAVE_OBJETIVO),
        state.get(CHAVE_ATE_ANOMES),
    )
    base = {
        "evento": EVENT_UNSUPPORTED_NUMBER,
        "session_id": getattr(session, "id", None),
        "estado_jornada": state.get(CHAVE_ESTADO_JORNADA),
    }
    missing = [c for c in claims if not is_supported(c, evidence)]
    if missing:
        _log.warning(
            f"{len(missing)} de {len(claims)} números da resposta sem fonte no turno.",
            extra={**base, "erro_codigo": ERROR_DIVERGENT_NUMBER},
        )
    footer = source_footer(outcomes)
    if footer and not cites_source(text):
        _log.info(
            "Resposta com números de ferramenta sem citar a fonte; rodapé acrescentado.",
            extra={**base, "erro_codigo": ERROR_SOURCE_NOT_CITED},
        )
        last = [p for p in _parts(llm_response) if getattr(p, "text", None) and not p.thought][-1]
        last.text = f"{last.text.rstrip()}\n\n{footer}"
    return None
