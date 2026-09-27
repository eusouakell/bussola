"""Answers that claim an action nobody performed (BUG-04, layer b).

``after_model`` order 60. A card only exists in the front when a
``functionResponse`` reaches it, so a turn that answers "Seu objetivo foi
registrado com sucesso" without calling ``registrar_objetivo`` produces a plain
text bubble and leaves the journey where it was — the state machine only runs
inside ``after_tool``, so nothing else notices the omission.

This callback closes that blind spot. When the final text of a turn claims a
finished tool action (:data:`CLAIMS`) and **no** tool answered in the
invocation, it:

- logs ``evento=acao_sem_ferramenta`` with the claimed tool and the journey
  step (never the answer, never the customer's text);
- marks the message with ``custom_metadata.bussola.acao_sem_ferramenta``
  (the claimed tool), so the front can react later.

It never blocks and never rewrites the answer: the response is changed in
place and the callback returns ``None``.

Only completed claims count. Each sentence is read on its own and a sentence
with a hedge ("ainda não registrei", "posso registrar", "vou registrar") is
ignored, so a question or an offer is never flagged. A turn where any tool
answered is left alone, even if the claim is about another tool: forcing that
judgement would need the model's intent, and this check stays deterministic.
"""

import re
import unicodedata
from typing import Any

from bussola_agent.estado import CHAVE_ESTADO_JORNADA
from bussola_agent.jornada import llm_view
from bussola_agent.jornada.tool_results import tool_outcomes
from bussola_agent.logging_json import obter_logger

ORDER = 60
EVENT_CLAIM_WITHOUT_TOOL = "acao_sem_ferramenta"
ERROR_CLAIM_WITHOUT_TOOL = "ACAO_SEM_FERRAMENTA"
METADATA_KEY = "acao_sem_ferramenta"

_log = obter_logger(__name__)

# Claim → tool that had to answer in the turn, first match wins.
CLAIMS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "registrar_objetivo",
        re.compile(
            r"\b(objetivo|meta) (foi |ja foi |esta )?(registrad[oa]|salv[oa]|anotad[oa])\b"
            r"|\b(registrei|anotei|salvei|guardei) (o |a |seu |sua )*(objetivo|meta)\b"
        ),
    ),
    (
        "ajustar_plano",
        re.compile(
            r"\bplano (foi |ja foi )?(ajustado|atualizado)\b"
            r"|\b(ajustei|atualizei) (o |seu )*plano\b"
        ),
    ),
    (
        "criar_plano",
        re.compile(
            r"\bplano (foi |ja foi )?(criado|ativado|registrado)\b"
            r"|\b(criei|ativei|registrei) (o |seu )*plano\b"
            r"|\bplano (ja )?(esta|ficou) ativo\b"
        ),
    ),
    (
        "ativar_lembretes",
        re.compile(
            r"\blembretes? (ja )?(foram |foi |estao |esta )?(ativad[oa]s?|ligad[oa]s?)\b"
            r"|\bativei os lembretes\b"
        ),
    ),
    (
        "escolher_cenario",
        re.compile(
            r"\b(caminho|cenario|rota|escolha)( \w+)? (foi |ja foi )?"
            r"(registrad[oa]|confirmad[oa])\b"
            r"|\b(registrei|confirmei) (o |a |seu |sua )*(caminho|cenario|escolha)\b"
        ),
    ),
    (
        "comparar_cenarios",
        re.compile(r"\bcomparei\b|\bcomparacao (dos|entre os) (caminhos|cenarios)\b"),
    ),
    (
        "simular_objetivo",
        re.compile(
            r"\b(simulei|rodei a simulacao|fiz a simulacao|refiz a simulacao)\b"
            r"|\bsimulacao (ja )?(foi |esta )?(feita|refeita|pronta|atualizada)\b"
        ),
    ),
)

_SPACES = re.compile(r"\s+")
_SENTENCES = re.compile(r"[.!?;:\n]+")
_HEDGE = re.compile(
    r"\b(nao|nunca|nem|ainda|vou|vamos|posso|podemos|poderia|poderiamos|gostaria"
    r"|quer que|se voce|assim que|antes de|preciso|falta|faltam|basta"
    r"|confirme|confirma|autoriza|autorizar)\b"
)


def _normalize(text: str) -> str:
    """Lowercase, no accents, single spaces.

    Same normalization as ``governanca.text.normalize`` and the front
    simulator, written here so the journey (004) does not depend on the
    governance extension package.
    """
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _SPACES.sub(" ", stripped.lower()).strip()


def claimed_tool(text: str) -> str | None:
    """Tool the answer says it already used, or ``None``.

    Each sentence is read on its own; a sentence with a hedge does not count.
    """
    for sentence in _SENTENCES.split(_normalize(text)):
        if not sentence or _HEDGE.search(sentence):
            continue
        for tool, pattern in CLAIMS:
            if pattern.search(sentence):
                return tool
    return None


def _tool_answered(callback_context: Any) -> bool:
    session = getattr(callback_context, "session", None)
    events = list(getattr(session, "events", None) or [])
    invocation_id = getattr(callback_context, "invocation_id", None)
    return any(True for _ in tool_outcomes(events, invocation_id))


def check_action_claims(callback_context: Any, llm_response: Any) -> None:
    """``after_model`` order 60: flags an action claimed without any tool in the turn."""
    if not llm_view.is_final_text(llm_response) or _tool_answered(callback_context):
        return None
    tool = claimed_tool(llm_view.final_text(llm_response))
    if tool is None:
        return None
    state = getattr(callback_context, "state", None) or {}
    _log.warning(
        "Resposta afirma uma ação que nenhuma ferramenta executou neste turno.",
        extra={
            "evento": EVENT_CLAIM_WITHOUT_TOOL,
            "erro_codigo": ERROR_CLAIM_WITHOUT_TOOL,
            "ferramenta": tool,
            "estado_jornada": state.get(CHAVE_ESTADO_JORNADA),
            "session_id": getattr(getattr(callback_context, "session", None), "id", None),
        },
    )
    metadata = dict(llm_response.custom_metadata or {})
    bussola = dict(metadata.get("bussola") or {})
    bussola.setdefault(METADATA_KEY, tool)
    metadata["bussola"] = bussola
    llm_response.custom_metadata = metadata
    return None
