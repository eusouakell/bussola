"""Audit trail (ciclo §3.4): events in ``bussola_app.auditoria`` and JSON logs.

- :func:`record_event` writes one :class:`EventoAuditoria`. A registry failure
  is logged and swallowed: auditing never breaks the customer's turn (the
  consent row, which the gate depends on, is handled in :mod:`.consent`).
- ``before_model`` 10 (:func:`record_session_start`): ``sessao_iniciada`` on
  the first model call of a session.
- ``before_tool`` 90 (:func:`remember_tool_call`): remembers the journey state
  and the start time of the call.
- ``after_tool`` 90 (:func:`record_tool_call`): ``ferramenta_chamada`` and,
  when the journey moved, ``estado_alterado``. It also runs for calls stopped
  by an earlier ``before_tool`` (scope or gate), which show up as
  ``bloqueado``/``erro`` without latency.

Minimization: the ``resumo`` of a tool call carries argument **names**,
numeric values and a few enumerated options (scenario, action, product id),
never free text, messages or prompts.
"""

import asyncio
import re
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from bussola_agent.estado import CHAVE_ESTADO_JORNADA, EstadoJornada
from bussola_agent.governanca import envelope, services
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import EventoAuditoria, TipoEvento

UNKNOWN_SESSION = "desconhecida"

# Arguments whose short identifier value may be stored (never free text).
OPTION_ARGS = frozenset({"acao", "cenario", "nome", "tipo_produto", "frequencia", "destino_tipo"})
_OPTION_VALUE = re.compile(r"^[a-z0-9_]{1,40}$")
_MAX_ARGS = 20
_MAX_MEMO = 2_000
_MAX_SESSIONS = 10_000

_log = obter_logger(__name__)

_calls: OrderedDict[str, tuple[str, float]] = OrderedDict()
_started_sessions: OrderedDict[str, None] = OrderedDict()


def session_id_of(context: Any) -> str | None:
    session = getattr(context, "session", None)
    value = getattr(session, "id", None)
    return value if isinstance(value, str) and value else None


def current_state(state: Mapping[str, Any] | Any) -> EstadoJornada:
    """Journey state, ``OBJETIVO`` when missing or unknown (auditing never fails)."""
    try:
        return EstadoJornada(state.get(CHAVE_ESTADO_JORNADA) or EstadoJornada.OBJETIVO)
    except (ValueError, AttributeError):
        return EstadoJornada.OBJETIVO


async def record_event(
    context: Any,
    tipo: TipoEvento,
    resumo: Mapping[str, Any] | None = None,
    ferramenta: str | None = None,
    estado: EstadoJornada | None = None,
) -> bool:
    """Writes one audit event. Returns ``False`` (and logs) if the registry failed."""
    session_id = session_id_of(context)
    try:
        event = EventoAuditoria(
            session_id=session_id or UNKNOWN_SESSION,
            estado=estado or current_state(getattr(context, "state", {})),
            tipo_evento=tipo,
            ferramenta=ferramenta,
            resumo=dict(resumo or {}),
            ts=services.get_clock().now(),
        )
        registry = services.get_registry()
        await asyncio.to_thread(registry.registrar_evento, event)
    except Exception as exc:
        _log.error(
            "Falha ao gravar evento de auditoria.",
            extra={
                "evento": str(tipo),
                "session_id": session_id,
                "ferramenta": ferramenta,
                "erro_codigo": "AUDITORIA_FALHOU",
            },
            exc_info=exc,
        )
        return False
    return True


# ---------------------------------------------------------------------------
# before_model 10: session start
# ---------------------------------------------------------------------------


def _is_first_model_call(callback_context: Any) -> bool:
    """First invocation of the session and no model output recorded yet."""
    session = getattr(callback_context, "session", None)
    invocation_id = getattr(callback_context, "invocation_id", None)
    for event in getattr(session, "events", None) or []:
        if getattr(event, "invocation_id", invocation_id) != invocation_id:
            return False
        if getattr(event, "author", "user") != "user":
            parts = getattr(getattr(event, "content", None), "parts", None) or []
            if parts:
                return False
    return True


async def record_session_start(callback_context: Any, llm_request: Any) -> None:
    """``before_model`` 10: ``sessao_iniciada`` once per session."""
    session_id = session_id_of(callback_context)
    if session_id is None or session_id in _started_sessions:
        return None
    if not _is_first_model_call(callback_context):
        return None
    _started_sessions[session_id] = None
    while len(_started_sessions) > _MAX_SESSIONS:
        _started_sessions.popitem(last=False)
    await record_event(callback_context, TipoEvento.SESSAO_INICIADA, {})
    _log.info(
        "Sessão iniciada.",
        extra={"evento": "sessao_iniciada", "session_id": session_id},
    )
    return None


# ---------------------------------------------------------------------------
# before_tool / after_tool 90: tool calls
# ---------------------------------------------------------------------------


def _call_key(tool_context: Any) -> str | None:
    value = getattr(tool_context, "function_call_id", None)
    return value if isinstance(value, str) and value else None


def summarize_args(args: Mapping[str, Any] | None) -> dict[str, Any]:
    """Argument names, numeric values and enumerated options only."""
    if not isinstance(args, Mapping):
        return {"args": []}
    names = sorted(str(k) for k in args)[:_MAX_ARGS]
    numbers = {
        str(k): v
        for k, v in args.items()
        if isinstance(v, int | float) and not isinstance(v, bool) and v == v
    }
    options = {
        str(k): v
        for k, v in args.items()
        if k in OPTION_ARGS and isinstance(v, str) and _OPTION_VALUE.fullmatch(v)
    }
    summary: dict[str, Any] = {"args": names}
    if numbers:
        summary["numeros"] = numbers
    if options:
        summary["opcoes"] = options
    return summary


def remember_tool_call(tool: Any, args: dict[str, Any], tool_context: Any) -> None:
    """``before_tool`` 90: journey state and start time of the call."""
    key = _call_key(tool_context)
    if key is not None:
        _calls[key] = (
            current_state(tool_context.state).value,
            services.get_clock().monotonic(),
        )
        while len(_calls) > _MAX_MEMO:
            _calls.popitem(last=False)
    return None


async def record_tool_call(
    tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any
) -> None:
    """``after_tool`` 90: ``ferramenta_chamada`` and ``estado_alterado``."""
    name = getattr(tool, "name", None) or "desconhecida"
    key = _call_key(tool_context)
    memo = _calls.pop(key, None) if key is not None else None
    code = envelope.error_code(tool_response)
    if code is None:
        status = "ok"
    elif code in envelope.BLOCKING_CODES or memo is None:
        status = "bloqueado"
    else:
        status = "erro"
    summary = summarize_args(args)
    summary["status"] = status
    if code:
        summary["erro_codigo"] = code
    latency_ms = None
    if memo is not None:
        latency_ms = max(0, round((services.get_clock().monotonic() - memo[1]) * 1000))
        summary["latencia_ms"] = latency_ms
    before = memo[0] if memo is not None else None
    after = current_state(tool_context.state)

    await record_event(
        tool_context,
        TipoEvento.FERRAMENTA_CHAMADA,
        summary,
        ferramenta=name,
        estado=EstadoJornada(before) if before else after,
    )
    session_id = session_id_of(tool_context)
    _log.info(
        "Ferramenta chamada.",
        extra={
            "evento": "ferramenta_chamada",
            "ferramenta": name,
            "session_id": session_id,
            "estado_jornada": after.value,
            "latencia_ms": latency_ms,
            "erro_codigo": code,
        },
    )
    if before and before != after.value:
        await record_event(
            tool_context,
            TipoEvento.ESTADO_ALTERADO,
            {"de": before, "para": after.value},
            ferramenta=name,
            estado=after,
        )
    return None


def reset() -> None:
    """Forgets remembered calls and started sessions. Only for tests."""
    _calls.clear()
    _started_sessions.clear()
