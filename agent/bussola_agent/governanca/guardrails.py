"""Input and output guardrails (ciclo §3.5).

- **Input** (``before_model`` 10, :func:`screen_input`): the customer's message
  is checked once per invocation. A hit ends the turn with a polite pt-BR
  refusal, without calling the model.
- **Output** (``after_model`` 10, :func:`screen_output`): the model's text is
  checked before reaching the customer. A hit replaces the response.

Both go through a :class:`Screener` port. The default is :class:`RuleScreener`
(deterministic rules below); with ``MODEL_ARMOR_TEMPLATE`` set,
:mod:`.model_armor` layers Model Armor after the rules. Every block carries
``customMetadata.bussola.guardrail`` (the reason, read by the front) and
quick replies, writes ``guardrail_bloqueio`` and logs without the text.

``after_model`` 10 also puts the "Sim, autorizo" / "Agora não" chips on the
final message while a consent request is pending.

Reasons (front contract): ``outro_cliente``, ``ignorar_instrucoes``,
``infra``, ``promessa_credito``, ``compartilhar_dados``, ``fora_do_escopo``.
"""

import os
import re
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from google.adk.models.llm_response import LlmResponse
from google.genai import types

from bussola_agent.estado import CHAVE_ID_USUARIO, CHAVE_PLANO_ID
from bussola_agent.governanca import services
from bussola_agent.governanca.audit import record_event, session_id_of
from bussola_agent.governanca.consent import (
    CONSENT_CHIPS,
    consents_of,
    fixed_reply,
    pending_entry,
    user_text,
)
from bussola_agent.governanca.text import normalize
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import TipoEvento

OTHER_CUSTOMER = "outro_cliente"
IGNORE_INSTRUCTIONS = "ignorar_instrucoes"
INFRA = "infra"
CREDIT_PROMISE = "promessa_credito"
SHARE_DATA = "compartilhar_dados"
OUT_OF_SCOPE = "fora_do_escopo"
REASONS: tuple[str, ...] = (
    OTHER_CUSTOMER,
    IGNORE_INSTRUCTIONS,
    INFRA,
    CREDIT_PROMISE,
    SHARE_DATA,
    OUT_OF_SCOPE,
)

ORIGIN_RULES = "regras"
STAGE_INPUT = "entrada"
STAGE_OUTPUT = "saida"

# Project of the PoC; GOOGLE_CLOUD_PROJECT is added at check time.
KNOWN_PROJECTS: tuple[str, ...] = ("batalha-time-07-lkbv",)

_CONTINUE = "Posso continuar ajudando com o seu objetivo."
MESSAGES: dict[str, str] = {
    OTHER_CUSTOMER: "Não posso fazer isso. Só consigo usar os seus dados, e só para o seu "
    "objetivo. " + _CONTINUE,
    IGNORE_INSTRUCTIONS: "Não posso fazer isso. Só consigo usar os seus dados, e só para o seu "
    "objetivo. " + _CONTINUE,
    INFRA: "Não posso compartilhar detalhes técnicos, credenciais ou acesso aos sistemas. "
    + _CONTINUE,
    SHARE_DATA: "Não compartilho seus dados com ninguém, nem com outros bancos. " + _CONTINUE,
    CREDIT_PROMISE: "Não consigo garantir aprovação de crédito, porque isso depende de uma "
    "análise do banco. Posso simular um financiamento genérico, sem taxas, só como referência.",
    OUT_OF_SCOPE: "Não posso ajudar com isso. " + _CONTINUE,
}
OUTPUT_MESSAGE = (
    "Não consegui montar uma resposta segura para isso, então preferi não mostrar. " + _CONTINUE
)

CHIPS_CONTINUE: tuple[str, ...] = ("Continuar o plano", "O que você pode fazer?")
CHIPS: dict[str, tuple[str, ...]] = {
    CREDIT_PROMISE: ("Simular um financiamento", "Continuar o plano"),
}

_log = obter_logger(__name__)


# ---------------------------------------------------------------------------
# Port
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    reason: str
    origin: str = ORIGIN_RULES


class Screener(Protocol):
    """Port: decides whether a text must be blocked (``None`` lets it through)."""

    async def check_input(self, text: str, known_ids: frozenset[str]) -> Finding | None: ...

    async def check_output(self, text: str, known_ids: frozenset[str]) -> Finding | None: ...


# ---------------------------------------------------------------------------
# Deterministic rules
# ---------------------------------------------------------------------------

UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)

# Input rules, in the order of the front simulator (web/src/simulado).
_INPUT_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        IGNORE_INSTRUCTIONS,
        re.compile(
            r"\b(ignor[ae]\w*|esquec[ae]\w*|desconsider[ae]\w*)\b.*"
            r"\b(instruc\w*|regras?|prompt|orientac\w*)\b"
            r"|\b(system prompt|prompt do sistema|modo desenvolvedor|developer mode|jailbreak)\b"
            r"|\b(finja|fingir|aja como|atue como|voce agora e)\b.*"
            r"\b(sem (regras|restric\w*|limites|filtros?)|administrador|desenvolvedor)\b"
        ),
    ),
    (
        OTHER_CUSTOMER,
        re.compile(
            r"\b(outr[oa]s? (cliente|pessoa|usuari[oa]|conta)s?"
            r"|dados d[aeo]s? (meu|minha) (pai|mae|irma|irmao|esposa|marido|vizinh[oa]|chefe))\b"
        ),
    ),
    (
        INFRA,
        re.compile(
            r"\b(sql|bigquery|tabelas? (internas?|do sistema|do banco)|banco de dados"
            r"|credencia\w*|api key|chave de api|token|senha|dataset"
            r"|(seu|teu|o) prompt|prompt (do sistema|inicial|interno)"
            r"|instruc\w* (internas?|do sistema|iniciais)"
            r"|gcp|google cloud|cloud run|conta de servico|service account"
            r"|variave\w* de ambiente)\b"
        ),
    ),
    (
        SHARE_DATA,
        re.compile(
            r"\b(compartilh\w*|envi[ae]\w*|mand[ae]\w*|repass\w*)\b.*\b(dados|extrato)\b.*"
            r"\b(para|pra|com)\b(?! (mim|eu)\b)"
        ),
    ),
    (
        CREDIT_PROMISE,
        re.compile(
            r"\b(aprov\w*|garant\w*)\b.*\b(financiamento|credito|emprestimo)\b"
            r"|\b(financiamento|credito|emprestimo)\b.*\b(aprov\w*|garant\w*)\b"
        ),
    ),
)

_SQL = re.compile(
    r"\bselect\b[^;]{0,200}?\bfrom\b|\binsert\s+into\b|\bupdate\s+\S+\s+set\b"
    r"|\bdelete\s+from\b|\b(create|drop|alter)\s+(table|view|schema|dataset)\b"
    r"|\bmerge\s+into\b",
    re.I,
)
_CREDENTIALS = re.compile(
    r"AIza[0-9A-Za-z_\-]{30,}|ya29\.[0-9A-Za-z_\-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\bBearer\s+[A-Za-z0-9\-_.=]{20,}|\"private_key(_id)?\"\s*:",
)
_SENTENCES = re.compile(r"[.!?;\n]+")
_APPROVAL = re.compile(
    r"\b(aprovad[oa]s?|aprovacao|aprovar|aprovamos|aprovo|garantid[oa]s?|garanto|garantimos"
    r"|pre-?aprovad[oa]s?|liberad[oa]s?)\b"
)
_CREDIT = re.compile(r"\b(financiamentos?|credito|emprestimos?|consorcio)\b")
_HEDGE = re.compile(
    r"\b(nao|nunca|nem|sem|depende\w*|analise|pode\w*|talvez|chances?|possivel\w*|simulac\w*)\b"
)


def _foreign_uuid(text: str, known_ids: frozenset[str]) -> bool:
    return any(match.lower() not in known_ids for match in UUID_RE.findall(text))


def check_input_rules(text: str, known_ids: Iterable[str]) -> str | None:
    """Reason to block the customer's message, or ``None``."""
    known = frozenset(i.lower() for i in known_ids)
    normalized = normalize(text)
    for reason, pattern in _INPUT_RULES:
        if reason == OTHER_CUSTOMER and _foreign_uuid(text, known):
            return OTHER_CUSTOMER
        if pattern.search(normalized):
            return reason
    return None


def _projects() -> tuple[str, ...]:
    extra = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip().lower()
    return (*KNOWN_PROJECTS, extra) if len(extra) >= 6 else KNOWN_PROJECTS


def check_output_rules(text: str, known_ids: Iterable[str]) -> str | None:
    """Reason to block a model response, or ``None``.

    Dataset and table names are allowed: the answer cites its source
    (tool and period) and the ``fonte`` lists tables.
    """
    known = frozenset(i.lower() for i in known_ids)
    if _foreign_uuid(text, known):
        return OTHER_CUSTOMER
    if _SQL.search(text) or _CREDENTIALS.search(text):
        return INFRA
    lowered = text.lower()
    if any(project in lowered for project in _projects()):
        return INFRA
    for sentence in _SENTENCES.split(normalize(text)):
        if _APPROVAL.search(sentence) and _CREDIT.search(sentence) and not _HEDGE.search(sentence):
            return CREDIT_PROMISE
    return None


class RuleScreener:
    """Deterministic fallback (no network)."""

    async def check_input(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        reason = check_input_rules(text, known_ids)
        return Finding(reason) if reason else None

    async def check_output(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        reason = check_output_rules(text, known_ids)
        return Finding(reason) if reason else None


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

_MAX_TRACKED = 2_000
_MAX_BUFFER = 20_000
_passed_inputs: OrderedDict[str, None] = OrderedDict()
_buffers: OrderedDict[str, str] = OrderedDict()
_tripped: OrderedDict[str, Finding] = OrderedDict()


def _bounded_set(store: OrderedDict, key: str, value: Any = None) -> None:
    store[key] = value
    store.move_to_end(key)
    while len(store) > _MAX_TRACKED:
        store.popitem(last=False)


def known_ids(context: Any) -> frozenset[str]:
    """Ids the customer may see: own id, plan, consents and the session."""
    state = context.state
    ids: set[Any] = {state.get(CHAVE_ID_USUARIO), state.get(CHAVE_PLANO_ID)}
    ids.add(session_id_of(context))
    ids.update(entry.get("consent_id") for entry in consents_of(state).values())
    return frozenset(i.lower() for i in ids if isinstance(i, str) and i)


def block_response(reason: str, stage: str) -> LlmResponse:
    text = MESSAGES.get(reason, MESSAGES[OUT_OF_SCOPE])
    if stage == STAGE_OUTPUT and reason != CREDIT_PROMISE:
        text = OUTPUT_MESSAGE
    return fixed_reply(text, CHIPS.get(reason, CHIPS_CONTINUE), guardrail=reason)


async def _record_block(context: Any, finding: Finding, stage: str) -> None:
    await record_event(
        context,
        TipoEvento.GUARDRAIL_BLOQUEIO,
        {"motivo": finding.reason, "etapa": stage, "origem": finding.origin},
    )
    _log.warning(
        "Guardrail bloqueou a mensagem.",
        extra={
            "evento": "guardrail_bloqueio",
            "erro_codigo": finding.reason,
            "session_id": session_id_of(context),
        },
    )


# Gemini safety settings, part of the fallback guardrail (ciclo §6). Applied
# only when the request has none, so a stricter setting from 004 wins.
SAFETY_SETTINGS: tuple[types.SafetySetting, ...] = tuple(
    types.SafetySetting(
        category=category, threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    )
    for category in (
        types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    )
)


def apply_safety_settings(llm_request: Any) -> None:
    config = getattr(llm_request, "config", None)
    if config is not None and not config.safety_settings:
        config.safety_settings = [s.model_copy() for s in SAFETY_SETTINGS]


async def screen_input(callback_context: Any, llm_request: Any) -> LlmResponse | None:
    """``before_model`` 10: safety settings on every call; the customer's message
    is checked once per invocation."""
    apply_safety_settings(llm_request)
    invocation_id = str(getattr(callback_context, "invocation_id", "") or "")
    if invocation_id and invocation_id in _passed_inputs:
        return None
    text = user_text(getattr(callback_context, "user_content", None))
    finding = None
    if text:
        finding = await services.get_screener().check_input(text, known_ids(callback_context))
    if finding is None:
        if invocation_id:
            _bounded_set(_passed_inputs, invocation_id)
        return None
    await _record_block(callback_context, finding, STAGE_INPUT)
    return block_response(finding.reason, STAGE_INPUT)


def response_text(llm_response: Any) -> str:
    parts = getattr(getattr(llm_response, "content", None), "parts", None) or []
    return "".join(p.text for p in parts if isinstance(p.text, str) and not p.thought)


def _has_function_call(llm_response: Any) -> bool:
    parts = getattr(getattr(llm_response, "content", None), "parts", None) or []
    return any(p.function_call for p in parts)


def _blank_partial() -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text="")]), partial=True
    )


def add_consent_chips(callback_context: Any, llm_response: Any) -> None:
    """Chips "Sim, autorizo" / "Agora não" on the final text while a request is pending."""
    if pending_entry(callback_context.state) is None:
        return
    if not response_text(llm_response).strip() or _has_function_call(llm_response):
        return
    metadata = dict(llm_response.custom_metadata or {})
    bussola = dict(metadata.get("bussola") or {})
    if "respostas_rapidas" in bussola:
        return
    bussola["respostas_rapidas"] = list(CONSENT_CHIPS)
    metadata["bussola"] = bussola
    llm_response.custom_metadata = metadata


async def screen_output(callback_context: Any, llm_response: Any) -> LlmResponse | None:
    """``after_model`` 10: checks the model's text; adds consent chips when pending."""
    if getattr(llm_response, "error_code", None):
        return None
    invocation_id = str(getattr(callback_context, "invocation_id", "") or "")
    text = response_text(llm_response)

    if getattr(llm_response, "partial", False):
        # Streaming: check what was streamed so far; blank the rest after a hit.
        if invocation_id in _tripped:
            return _blank_partial()
        if not text:
            return None
        buffer = (_buffers.get(invocation_id, "") + text)[-_MAX_BUFFER:]
        _bounded_set(_buffers, invocation_id, buffer)
        reason = check_output_rules(buffer, known_ids(callback_context))
        if reason is None:
            return None
        _bounded_set(_tripped, invocation_id, Finding(reason))
        return _blank_partial()

    _buffers.pop(invocation_id, None)
    finding = _tripped.pop(invocation_id, None)
    if finding is None and text.strip():
        finding = await services.get_screener().check_output(text, known_ids(callback_context))
    if finding is not None:
        await _record_block(callback_context, finding, STAGE_OUTPUT)
        return block_response(finding.reason, STAGE_OUTPUT)
    add_consent_chips(callback_context, llm_response)
    return None


def reset() -> None:
    """Forgets per-invocation caches. Only for tests."""
    _passed_inputs.clear()
    _buffers.clear()
    _tripped.clear()
