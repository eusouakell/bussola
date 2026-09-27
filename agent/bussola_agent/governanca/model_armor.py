"""Model Armor adapter for the guardrail port (ciclo §3.5, P1).

- :class:`ModelArmorClient` is the port: ``sanitizeUserPrompt`` and
  ``sanitizeModelResponse`` of the Model Armor REST API.
- :class:`HttpModelArmorClient` is the real adapter (regional endpoint taken
  from the template name, ADC token, short timeout). Tests use a fake client
  or ``httpx.MockTransport``; nothing here is called against the real API in
  ``make test``.
- :class:`ModelArmorScreener` maps the filters to the front reasons.
- :class:`LayeredScreener` runs the deterministic rules first and Model Armor
  after them. If Model Armor fails, the rules' verdict stands (logged with
  ``erro_codigo``), so the turn goes on.
- :func:`build_screener` returns the rules alone when ``MODEL_ARMOR_TEMPLATE``
  is empty or invalid.
"""

import asyncio
import re
import threading
from collections.abc import Callable, Mapping
from typing import Any, Protocol

import httpx

from bussola_agent import config
from bussola_agent.governanca.guardrails import (
    IGNORE_INSTRUCTIONS,
    INFRA,
    OUT_OF_SCOPE,
    Finding,
    RuleScreener,
    Screener,
)
from bussola_agent.logging_json import obter_logger

ORIGIN_MODEL_ARMOR = "model_armor"
DEFAULT_TIMEOUT_S = config.TIMEOUT_MODEL_ARMOR_S
SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)
TEMPLATE_RE = re.compile(
    r"^projects/(?P<project>[a-z][a-z0-9-]{4,28}[a-z0-9])"
    r"/locations/(?P<location>[a-z0-9-]{2,40})/templates/(?P<template>[A-Za-z0-9_-]{1,63})$"
)

# Filter → reason, in priority order (first match wins).
INPUT_FILTERS: tuple[tuple[str, str], ...] = (
    ("pi_and_jailbreak", IGNORE_INSTRUCTIONS),
    ("sdp", INFRA),
    ("malicious_uris", OUT_OF_SCOPE),
    ("rai", OUT_OF_SCOPE),
    ("csam", OUT_OF_SCOPE),
)
OUTPUT_FILTERS: tuple[tuple[str, str], ...] = (
    ("sdp", INFRA),
    ("pi_and_jailbreak", OUT_OF_SCOPE),
    ("malicious_uris", OUT_OF_SCOPE),
    ("rai", OUT_OF_SCOPE),
    ("csam", OUT_OF_SCOPE),
)

_log = obter_logger(__name__)


class ModelArmorError(RuntimeError):
    """Model Armor could not answer. The message never carries the text."""


class ModelArmorClient(Protocol):
    async def sanitize_user_prompt(self, text: str) -> Mapping[str, Any]: ...

    async def sanitize_model_response(self, text: str) -> Mapping[str, Any]: ...


def parse_template(template: str) -> tuple[str, str]:
    """``(location, template)`` of a full template name. Raises ``ValueError``."""
    match = TEMPLATE_RE.fullmatch(template.strip())
    if match is None:
        raise ValueError("MODEL_ARMOR_TEMPLATE inválido.")
    return match["location"], match.group(0)


class _AdcTokens:
    """Access tokens from Application Default Credentials (refreshed when needed)."""

    def __init__(self) -> None:
        self._credentials: Any = None
        self._lock = threading.Lock()

    def __call__(self) -> str:
        import google.auth
        from google.auth.transport.requests import Request

        with self._lock:
            if self._credentials is None:
                self._credentials, _ = google.auth.default(scopes=list(SCOPES))
            if not self._credentials.valid:
                self._credentials.refresh(Request())
            return self._credentials.token


class HttpModelArmorClient:
    """REST adapter: ``POST https://modelarmor.{location}.rep.googleapis.com/v1/{template}:…``."""

    def __init__(
        self,
        template: str,
        token_provider: Callable[[], str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        location, self.template = parse_template(template)
        self.base_url = f"https://modelarmor.{location}.rep.googleapis.com/v1/{self.template}"
        self._token_provider = token_provider or _AdcTokens()
        self._transport = transport
        self._timeout_s = timeout_s

    async def _post(self, method: str, body: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            token = await asyncio.to_thread(self._token_provider)
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout_s
            ) as client:
                response = await client.post(
                    f"{self.base_url}:{method}",
                    json=body,
                    headers={"Authorization": f"Bearer {token}"},
                )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise ModelArmorError(f"Falha na chamada {method} do Model Armor.") from exc
        if not isinstance(data, Mapping):
            raise ModelArmorError("Resposta inesperada do Model Armor.")
        return data

    async def sanitize_user_prompt(self, text: str) -> Mapping[str, Any]:
        return await self._post("sanitizeUserPrompt", {"userPromptData": {"text": text}})

    async def sanitize_model_response(self, text: str) -> Mapping[str, Any]:
        return await self._post("sanitizeModelResponse", {"modelResponseData": {"text": text}})


def _match_found(value: Any) -> bool:
    """True if any nested ``matchState`` is ``MATCH_FOUND``."""
    if isinstance(value, Mapping):
        if value.get("matchState") == "MATCH_FOUND":
            return True
        return any(_match_found(v) for v in value.values())
    if isinstance(value, list):
        return any(_match_found(v) for v in value)
    return False


def reason_from(result: Mapping[str, Any], filters: tuple[tuple[str, str], ...]) -> str | None:
    """Reason for a Model Armor result, or ``None`` when nothing matched."""
    sanitization = result.get("sanitizationResult")
    if not isinstance(sanitization, Mapping):
        raise ModelArmorError("Resposta do Model Armor sem sanitizationResult.")
    if sanitization.get("filterMatchState") != "MATCH_FOUND":
        return None
    per_filter = sanitization.get("filterResults")
    per_filter = per_filter if isinstance(per_filter, Mapping) else {}
    for name, reason in filters:
        if _match_found(per_filter.get(name)):
            return reason
    return OUT_OF_SCOPE


class ModelArmorScreener:
    def __init__(self, client: ModelArmorClient) -> None:
        self.client = client

    async def check_input(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        reason = reason_from(await self.client.sanitize_user_prompt(text), INPUT_FILTERS)
        return Finding(reason, ORIGIN_MODEL_ARMOR) if reason else None

    async def check_output(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        reason = reason_from(await self.client.sanitize_model_response(text), OUTPUT_FILTERS)
        return Finding(reason, ORIGIN_MODEL_ARMOR) if reason else None


class LayeredScreener:
    """Rules first; then the secondary screener. A secondary failure keeps the rules' verdict."""

    def __init__(self, primary: Screener, secondary: Screener) -> None:
        self.primary = primary
        self.secondary = secondary

    async def _run(self, stage: str, text: str, known_ids: frozenset[str]) -> Finding | None:
        finding = await getattr(self.primary, stage)(text, known_ids)
        if finding is not None:
            return finding
        try:
            return await getattr(self.secondary, stage)(text, known_ids)
        except Exception as exc:
            _log.warning(
                "Model Armor indisponível; valem só as regras.",
                extra={"evento": "guardrail_fallback", "erro_codigo": "MODEL_ARMOR_INDISPONIVEL"},
                exc_info=exc,
            )
            return None

    async def check_input(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        return await self._run("check_input", text, known_ids)

    async def check_output(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        return await self._run("check_output", text, known_ids)


def build_screener(env: Mapping[str, str] | None = None) -> Screener:
    """Rules alone without ``MODEL_ARMOR_TEMPLATE``; rules + Model Armor with it."""
    template = config.template_model_armor(env)
    if not template:
        _log.info("Guardrail por regras (sem Model Armor).", extra={"evento": "guardrail_regras"})
        return RuleScreener()
    try:
        client = HttpModelArmorClient(template)
    except ValueError:
        _log.error(
            "MODEL_ARMOR_TEMPLATE inválido; valem só as regras.",
            extra={"evento": "guardrail_regras", "erro_codigo": "CONFIGURACAO_INVALIDA"},
        )
        return RuleScreener()
    _log.info("Guardrail com Model Armor.", extra={"evento": "guardrail_model_armor"})
    return LayeredScreener(RuleScreener(), ModelArmorScreener(client))
