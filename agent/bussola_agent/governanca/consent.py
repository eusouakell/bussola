"""Consent: yes/no parser, ``solicitar_consentimento``, reply reader and gate.

Flow (contratos §6, ciclo §3.2):

1. The model calls :func:`solicitar_consentimento`. The entry
   ``session.state.consentimentos[acao]`` becomes ``pendente``, with the id of
   the invocation that asked.
2. On the customer's next message, :func:`read_reply` (``before_model`` 20)
   decides it with :func:`parse_reply`. The model never decides:
   - accept: ``aceito``, the ``consentimentos`` row and the audit event are
     written, and the model is told to run the action now;
   - refuse: ``recusado``, recorded, and a fixed reply goes out without calling
     the model;
   - ambiguous: stays ``pendente`` and a fixed reply asks again;
   - neither yes nor no: stays ``pendente`` and the model is told to ask again.
3. :func:`gate` (``before_tool`` 20) lets a sensitive tool run only with an
   ``aceito`` entry that has not been used, and consumes it (``usado: true``)
   before the tool runs. Forbidden tools always get ``NAO_PERMITIDO``.

The ``consentimentos`` dict is always reassigned (never changed in place),
so the ADK records the state delta.
"""

import asyncio
import re
import uuid
from collections import OrderedDict
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from google.adk.models.llm_response import LlmResponse
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from bussola_agent import extensoes
from bussola_agent.estado import (
    CHAVE_CONSENTIMENTOS,
    CHAVE_PLANO_ID,
    EstadoJornada,
    definir_estado_jornada,
)
from bussola_agent.governanca import catalogo, envelope, services
from bussola_agent.governanca.audit import (
    current_state,
    record_event,
    session_id_of,
)
from bussola_agent.governanca.clock import iso
from bussola_agent.governanca.text import collapse_spaces, normalize
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import Consentimento, TipoEvento

PENDING = "pendente"
ACCEPTED = "aceito"
REFUSED = "recusado"

CHIP_YES = "Sim, autorizo"
CHIP_NO = "Agora não"
CONSENT_CHIPS: tuple[str, ...] = (CHIP_YES, CHIP_NO)

MAX_SUMMARY_LENGTH = 160
MAX_AMBIGUOUS_WORDS = 8

MSG_REFUSED = (
    "Tudo bem, não fiz nada. Sua decisão fica registrada e você pode mudar de ideia quando quiser."
)
MSG_CONFIRM = "Só para confirmar: posso seguir com essa ação? Responda sim ou não."
MSG_RECORD_FAILED = (
    "Não consegui registrar a sua autorização agora, então não fiz nada. "
    "Pode responder sim de novo em instantes?"
)
MSG_GATE_REQUIRED = (
    "Esta ação precisa da autorização explícita do cliente. Chame solicitar_consentimento, "
    "apresente o pedido e espere o cliente responder sim."
)
MSG_GATE_REFUSED = (
    "O cliente recusou esta ação. Não tente de novo sem um novo pedido e um novo sim."
)
MSG_NOT_ALLOWED = (
    "A Bússola não compartilha dados do cliente com terceiros. Esta ação não é permitida."
)
MSG_NOT_SENSITIVE = "Essa ação não precisa de autorização. Pode seguir sem pedir."
MSG_UNKNOWN_ACTION = "Ação desconhecida. Peça autorização só para ações sensíveis do catálogo."

INSTRUCTION_ACCEPTED = (
    "O cliente acabou de autorizar a ação {acao}. Chame a ferramenta {acao} agora, uma única "
    "vez, sem pedir autorização de novo. Depois, conte o resultado em poucas palavras."
)
INSTRUCTION_ASK_AGAIN = (
    "Há um pedido de autorização pendente para {acao}, e a última mensagem do cliente não "
    "respondeu sim nem não. Responda à mensagem e, no fim, pergunte de novo se pode seguir "
    "(sim ou não). Não execute a ação."
)

# Chips after a refusal, by action (generic continuation for the others).
REFUSAL_CHIPS: dict[str, tuple[str, ...]] = {
    "criar_plano": ("Me mostra os caminhos", "O que você pode fazer?"),
    "ajustar_plano": ("Manter o plano", "Avançar um mês"),
}
DEFAULT_REFUSAL_CHIPS: tuple[str, ...] = ("Continuar o plano", "O que você pode fazer?")

# Copy of the consent card (front: o que faz / o que não faz / dados usados).
_DOES_NOT = "Mover dinheiro, contratar produtos ou compartilhar seus dados."
CARD_COPY: dict[str, tuple[str, str, str]] = {
    "criar_plano": (
        "Registrar o plano com o caminho escolhido e acompanhar seu progresso mês a mês.",
        _DOES_NOT,
        "Seu objetivo, o caminho escolhido e o resumo do seu extrato.",
    ),
    "ajustar_plano": (
        "Ajustar o aporte e o prazo do seu plano para a rota escolhida.",
        _DOES_NOT,
        "O resultado do mês e o seu plano atual.",
    ),
    "ativar_lembretes": (
        "Ativar lembretes do seu plano, sem envio real nesta demonstração.",
        _DOES_NOT,
        "O valor e a data do aporte do seu plano.",
    ),
    "simular_contratacao": (
        "Registrar uma simulação genérica do produto, sem taxas, só como referência.",
        "Contratar produtos, fazer análise de crédito ou compartilhar seus dados.",
        "O produto escolhido e o seu plano.",
    ),
}
_DEFAULT_CARD = (
    "Executar a ação pedida, só nesta conversa.",
    _DOES_NOT,
    "Os dados da sua jornada nesta conversa.",
)

_log = obter_logger(__name__)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Decision(StrEnum):
    ACCEPT = "aceito"
    REFUSE = "recusado"
    AMBIGUOUS = "ambiguo"
    NONE = "nenhuma"


_NEGATION = re.compile(r"\b(nao|recuso|cancela\w*|nunca|negativo)\b")
_ACCEPT = re.compile(r"\b(sim|pode|autorizo|ok|confirmo)\b")
_DOUBT = re.compile(r"\b(mas|talvez|depois|sera|duvida)\b|\?")
_DOUBT_ALONE = re.compile(r"\b(talvez|sera|duvida)\b")
_DONT_KNOW = re.compile(r"\bnao sei\b")


def parse_reply(text: object) -> Decision:
    """Customer reply to a consent request. Negation beats acceptance.

    Same vocabulary as ``lerConsentimento`` in ``web/src/simulado``: "sim, mas…",
    "talvez" and "não sei" are ambiguous; a long message mixing signals, or one
    with no signal at all, is not an answer (:attr:`Decision.NONE`). One
    difference: "?", "mas" and "depois" only count as doubt next to a yes or a
    no, so a short unrelated question ("quanto gasto com mercado?") goes to the
    model instead of getting the fixed "só para confirmar" reply.
    """
    if not isinstance(text, str):
        return Decision.NONE
    t = normalize(text)
    if not t:
        return Decision.NONE
    negation = bool(_NEGATION.search(t))
    accept = bool(_ACCEPT.search(t))
    doubt = bool(_DOUBT.search(t))
    if _DONT_KNOW.search(t):
        return Decision.AMBIGUOUS
    if accept and not negation and not doubt:
        return Decision.ACCEPT
    if negation and not accept and not doubt:
        return Decision.REFUSE
    if accept or negation or _DOUBT_ALONE.search(t):
        return Decision.AMBIGUOUS if len(t.split(" ")) <= MAX_AMBIGUOUS_WORDS else Decision.NONE
    return Decision.NONE


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def consents_of(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Copy of ``consentimentos`` (only well-formed entries)."""
    raw = state.get(CHAVE_CONSENTIMENTOS)
    if not isinstance(raw, Mapping):
        return {}
    return {str(k): dict(v) for k, v in raw.items() if isinstance(v, Mapping)}


def pending_entry(state: Mapping[str, Any]) -> tuple[str, dict[str, Any]] | None:
    """The pending request (at most one; the latest wins if the state has more)."""
    found = None
    for action, entry in consents_of(state).items():
        if entry.get("status") == PENDING:
            found = (action, entry)
    return found


def _save(state: Any, consents: dict[str, dict[str, Any]]) -> None:
    state[CHAVE_CONSENTIMENTOS] = consents


def known_action(action: str) -> bool:
    return action in catalogo.SENSITIVE_ACTIONS or action in extensoes.ferramentas_sensiveis()


def presented_text(action: str, summary: str) -> str:
    """Standard consent text (ciclo §3.2), stored in ``consentimentos.texto_apresentado``."""
    return f"Posso {catalogo.action_label(action)}: {summary}? Responda **sim** ou **não**."


def clean_summary(value: object, action: str) -> str:
    """Short single-line summary; falls back to a default when empty or unsafe."""
    default = catalogo.action_label(action)
    default = default[0].upper() + default[1:]
    if not isinstance(value, str):
        return default
    text = collapse_spaces(value).strip("?").strip()
    text = re.sub(r"[{}<>\[\]`*]", "", text)
    if not text:
        return default
    from bussola_agent.governanca.guardrails import check_output_rules

    if check_output_rules(text, set()) is not None:
        return default
    if len(text) > MAX_SUMMARY_LENGTH:
        text = text[: MAX_SUMMARY_LENGTH - 1].rstrip() + "…"
    return text


# ---------------------------------------------------------------------------
# Tool: solicitar_consentimento
# ---------------------------------------------------------------------------


async def solicitar_consentimento(acao: str, resumo: str, tool_context: ToolContext) -> dict:
    """Pede ao cliente autorização explícita para uma ação sensível.

    Chame antes de criar_plano, ativar_lembretes, simular_contratacao ou
    ajustar_plano. Depois, apresente o pedido e espere o cliente responder sim
    ou não. Não chame a ação no mesmo turno.

    Args:
        acao: nome da ação sensível (ex.: criar_plano).
        resumo: frase curta, em pt-BR, do que será feito (até 160 caracteres).

    Returns:
        Envelope com consent_id, acao, resumo, status, o_que_faz,
        o_que_nao_faz e dados_usados, ou erro.
    """
    action = acao.strip() if isinstance(acao, str) else ""
    state = tool_context.state
    if catalogo.is_forbidden(action):
        await record_event(
            tool_context,
            TipoEvento.GUARDRAIL_BLOQUEIO,
            {"motivo": "compartilhar_dados", "etapa": "consentimento"},
            ferramenta=catalogo.REQUEST_CONSENT_TOOL,
        )
        return envelope.error(envelope.NOT_ALLOWED, MSG_NOT_ALLOWED)
    if catalogo.is_free(action):
        return envelope.error(envelope.INVALID_INPUT, MSG_NOT_SENSITIVE)
    if not known_action(action):
        return envelope.error(envelope.INVALID_INPUT, MSG_UNKNOWN_ACTION)

    clock = services.get_clock()
    summary = clean_summary(resumo, action)
    consent_id = str(uuid.uuid4())
    consents = {
        name: entry for name, entry in consents_of(state).items() if entry.get("status") != PENDING
    }
    consents[action] = {
        "consent_id": consent_id,
        "status": PENDING,
        "ts": iso(clock.now()),
        "resumo": summary,
        "invocation_id": tool_context.invocation_id,
    }
    _save(state, consents)

    stage = current_state(state)
    if stage not in (EstadoJornada.AGIR, EstadoJornada.ACOMPANHAR):
        definir_estado_jornada(state, EstadoJornada.AGIR)

    await record_event(
        tool_context,
        TipoEvento.CONSENTIMENTO_SOLICITADO,
        {"acao": action, "consent_id": consent_id},
        ferramenta=catalogo.REQUEST_CONSENT_TOOL,
    )
    _log.info(
        "Consentimento solicitado.",
        extra={
            "evento": "consentimento_solicitado",
            "consentimento": PENDING,
            "ferramenta": action,
            "session_id": session_id_of(tool_context),
        },
    )
    does, does_not, data_used = CARD_COPY.get(action, _DEFAULT_CARD)
    return envelope.ok(
        {
            "consent_id": consent_id,
            "acao": action,
            "resumo": summary,
            "status": PENDING,
            "texto": presented_text(action, summary),
            "o_que_faz": does,
            "o_que_nao_faz": does_not,
            "dados_usados": data_used,
        },
        ferramenta=catalogo.REQUEST_CONSENT_TOOL,
        tabelas=(),
        ate_anomes=None,
    )


# ---------------------------------------------------------------------------
# before_model 20: reader
# ---------------------------------------------------------------------------


def user_text(content: Any) -> str:
    parts = getattr(content, "parts", None) or []
    texts = [p.text for p in parts if isinstance(getattr(p, "text", None), str)]
    return " ".join(texts).strip()


def fixed_reply(text: str, chips: tuple[str, ...], **extra: Any) -> LlmResponse:
    """Deterministic model reply with its own ``customMetadata.bussola``.

    ``after_model`` is not called for a reply returned by ``before_model``,
    so the chips go here.
    """
    bussola: dict[str, Any] = {"respostas_rapidas": list(chips), **extra}
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=text)]),
        custom_metadata={"bussola": bussola},
        turn_complete=True,
    )


async def _record_decision(
    callback_context: Any, action: str, entry: Mapping[str, Any], decision: str
) -> None:
    """Writes the ``consentimentos`` row. Raises if the registry fails."""
    state = callback_context.state
    plano_id = state.get(CHAVE_PLANO_ID)
    row = Consentimento(
        consent_id=str(entry.get("consent_id") or uuid.uuid4()),
        session_id=session_id_of(callback_context) or "desconhecida",
        plano_id=plano_id if isinstance(plano_id, str) and plano_id else None,
        acao=action,
        decisao=decision,  # type: ignore[arg-type]
        texto_apresentado=presented_text(action, str(entry.get("resumo") or "")),
        ts=services.get_clock().now(),
    )
    registry = services.get_registry()
    await asyncio.to_thread(registry.registrar_consentimento, row)


def _decide(callback_context: Any, action: str, entry: Mapping[str, Any], decision: str) -> None:
    consents = consents_of(callback_context.state)
    decided = {k: v for k, v in entry.items() if k != "invocation_id"}
    decided.update(status=decision, ts=iso(services.get_clock().now()))
    consents[action] = decided
    _save(callback_context.state, consents)


async def read_reply(callback_context: Any, llm_request: Any) -> LlmResponse | None:
    """``before_model`` 20: decides a pending request from the customer's message."""
    pending = pending_entry(callback_context.state)
    if pending is None:
        return None
    action, entry = pending
    if entry.get("invocation_id") == callback_context.invocation_id:
        return None  # same turn that asked: wait for the customer
    decision = parse_reply(user_text(callback_context.user_content))
    base_log = {
        "ferramenta": action,
        "session_id": session_id_of(callback_context),
    }

    if decision is Decision.ACCEPT:
        try:
            await _record_decision(callback_context, action, entry, ACCEPTED)
        except Exception as exc:
            _log.error(
                "Falha ao registrar o consentimento; o pedido continua pendente.",
                extra={**base_log, "evento": "consentimento_decidido", "erro_codigo": "REGISTRO"},
                exc_info=exc,
            )
            return fixed_reply(MSG_RECORD_FAILED, CONSENT_CHIPS)
        _decide(callback_context, action, entry, ACCEPTED)
        await _after_decision(callback_context, action, entry, ACCEPTED, base_log)
        llm_request.append_instructions([INSTRUCTION_ACCEPTED.format(acao=action)])
        return None

    if decision is Decision.REFUSE:
        try:
            await _record_decision(callback_context, action, entry, REFUSED)
        except Exception as exc:
            # The refusal holds even if it could not be recorded.
            _log.error(
                "Falha ao registrar a recusa; a recusa vale mesmo assim.",
                extra={**base_log, "evento": "consentimento_decidido", "erro_codigo": "REGISTRO"},
                exc_info=exc,
            )
        _decide(callback_context, action, entry, REFUSED)
        await _after_decision(callback_context, action, entry, REFUSED, base_log)
        return fixed_reply(MSG_REFUSED, REFUSAL_CHIPS.get(action, DEFAULT_REFUSAL_CHIPS))

    if decision is Decision.AMBIGUOUS:
        _log.info(
            "Resposta ambígua ao pedido de consentimento.",
            extra={**base_log, "evento": "consentimento_ambiguo", "consentimento": PENDING},
        )
        return fixed_reply(MSG_CONFIRM, CONSENT_CHIPS)

    llm_request.append_instructions([INSTRUCTION_ASK_AGAIN.format(acao=action)])
    return None


async def _after_decision(
    callback_context: Any,
    action: str,
    entry: Mapping[str, Any],
    decision: str,
    base_log: dict[str, Any],
) -> None:
    await record_event(
        callback_context,
        TipoEvento.CONSENTIMENTO_DECIDIDO,
        {"acao": action, "consent_id": entry.get("consent_id"), "decisao": decision},
        ferramenta=action,
    )
    _log.info(
        "Consentimento decidido.",
        extra={**base_log, "evento": "consentimento_decidido", "consentimento": decision},
    )


# ---------------------------------------------------------------------------
# before_tool 20: gate
# ---------------------------------------------------------------------------

# Consent ids already released in this process. Parallel calls of the same
# model turn do not see each other's state delta, so the gate also checks here.
_MAX_USED_IDS = 10_000
_used_ids: OrderedDict[str, None] = OrderedDict()


def _mark_used(consent_id: str) -> bool:
    """True if ``consent_id`` was free and is now used (atomic in the event loop)."""
    if consent_id in _used_ids:
        return False
    _used_ids[consent_id] = None
    while len(_used_ids) > _MAX_USED_IDS:
        _used_ids.popitem(last=False)
    return True


def reset_used_ids() -> None:
    """Forgets released ids. Only for tests."""
    _used_ids.clear()


async def gate(tool: Any, args: dict[str, Any], tool_context: Any) -> dict | None:
    """``before_tool`` 20: sensitive tools need an unused ``aceito`` consent."""
    name = getattr(tool, "name", None) or ""
    if catalogo.is_free(name):
        return None
    base_log = {"ferramenta": name, "session_id": session_id_of(tool_context)}
    if catalogo.is_forbidden(name):
        await record_event(
            tool_context,
            TipoEvento.GUARDRAIL_BLOQUEIO,
            {"motivo": "compartilhar_dados", "etapa": "gate"},
            ferramenta=name,
        )
        _log.warning(
            "Ação proibida bloqueada.",
            extra={**base_log, "evento": "gate_bloqueio", "erro_codigo": envelope.NOT_ALLOWED},
        )
        return envelope.error(envelope.NOT_ALLOWED, MSG_NOT_ALLOWED)

    consents = consents_of(tool_context.state)
    entry = consents.get(name)
    consent_id = str(entry.get("consent_id") or "") if entry else ""
    if (
        entry is not None
        and entry.get("status") == ACCEPTED
        and not entry.get("usado")
        and consent_id
        and _mark_used(consent_id)
    ):
        consents[name] = {**entry, "usado": True}
        _save(tool_context.state, consents)
        _log.info(
            "Consentimento usado.",
            extra={**base_log, "evento": "consentimento_usado", "consentimento": ACCEPTED},
        )
        return None

    refused = entry is not None and entry.get("status") == REFUSED
    _log.info(
        "Ação sensível sem consentimento válido.",
        extra={
            **base_log,
            "evento": "gate_bloqueio",
            "erro_codigo": envelope.CONSENT_REQUIRED,
            "consentimento": entry.get("status") if entry else None,
        },
    )
    return envelope.error(
        envelope.CONSENT_REQUIRED, MSG_GATE_REFUSED if refused else MSG_GATE_REQUIRED
    )
