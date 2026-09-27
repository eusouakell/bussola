"""Model Armor adapter behind the screener port, mocked (decision D1).

``httpx.MockTransport`` answers instead of the API: no request leaves the
process and no real template is needed.
"""

import json

import httpx
import pytest

from bussola_agent.governanca import model_armor
from bussola_agent.governanca.guardrails import (
    IGNORE_INSTRUCTIONS,
    INFRA,
    OUT_OF_SCOPE,
    Finding,
    RuleScreener,
)
from bussola_agent.governanca.model_armor import (
    HttpModelArmorClient,
    LayeredScreener,
    ModelArmorError,
    ModelArmorScreener,
    build_screener,
    reason_from,
)

TEMPLATE = "projects/projeto-teste/locations/us-central1/templates/bussola-guard"


def _result(**filters: str) -> dict:
    per_filter = {
        name: {f"{name}FilterResult": {"matchState": state}} for name, state in filters.items()
    }
    found = any(state == "MATCH_FOUND" for state in filters.values())
    return {
        "sanitizationResult": {
            "filterMatchState": "MATCH_FOUND" if found else "NO_MATCH_FOUND",
            "filterResults": per_filter,
        }
    }


async def test_http_client_calls_the_regional_endpoint() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=_result(pi_and_jailbreak="NO_MATCH_FOUND"))

    client = HttpModelArmorClient(
        TEMPLATE, token_provider=lambda: "token-falso", transport=httpx.MockTransport(handler)
    )
    await client.sanitize_user_prompt("texto estático")
    await client.sanitize_model_response("resposta estática")

    assert [str(r.url) for r in seen] == [
        f"https://modelarmor.us-central1.rep.googleapis.com/v1/{TEMPLATE}:sanitizeUserPrompt",
        f"https://modelarmor.us-central1.rep.googleapis.com/v1/{TEMPLATE}:sanitizeModelResponse",
    ]
    assert json.loads(seen[0].content) == {"userPromptData": {"text": "texto estático"}}
    assert json.loads(seen[1].content) == {"modelResponseData": {"text": "resposta estática"}}
    assert seen[0].headers["Authorization"] == "Bearer token-falso"


@pytest.mark.parametrize("status", [403, 500])
async def test_http_errors_become_model_armor_error(status: int) -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={}))
    client = HttpModelArmorClient(TEMPLATE, token_provider=lambda: "t", transport=transport)
    with pytest.raises(ModelArmorError) as info:
        await client.sanitize_user_prompt("segredo do cliente")
    assert "segredo" not in str(info.value)


async def test_non_object_answer_is_an_error() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=[1, 2]))
    client = HttpModelArmorClient(TEMPLATE, token_provider=lambda: "t", transport=transport)
    with pytest.raises(ModelArmorError):
        await client.sanitize_model_response("x")


@pytest.mark.parametrize(
    "template",
    ["", "projects/x/templates/y", "projects/Projeto/locations/us/templates/t", "a/b/c"],
)
def test_invalid_template(template: str) -> None:
    with pytest.raises(ValueError):
        HttpModelArmorClient(template, token_provider=lambda: "t")


@pytest.mark.parametrize(
    ("filters", "table", "reason"),
    [
        ({"pi_and_jailbreak": "MATCH_FOUND"}, model_armor.INPUT_FILTERS, IGNORE_INSTRUCTIONS),
        ({"sdp": "MATCH_FOUND"}, model_armor.OUTPUT_FILTERS, INFRA),
        ({"rai": "MATCH_FOUND", "sdp": "NO_MATCH_FOUND"}, model_armor.INPUT_FILTERS, OUT_OF_SCOPE),
        ({"novo_filtro": "MATCH_FOUND"}, model_armor.INPUT_FILTERS, OUT_OF_SCOPE),
        ({"sdp": "NO_MATCH_FOUND"}, model_armor.INPUT_FILTERS, None),
    ],
)
def test_reason_from(filters: dict, table: tuple, reason: str | None) -> None:
    assert reason_from(_result(**filters), table) == reason


def test_reason_from_without_result_is_an_error() -> None:
    with pytest.raises(ModelArmorError):
        reason_from({}, model_armor.INPUT_FILTERS)


class _FakeClient:
    def __init__(self, answer: dict | Exception) -> None:
        self.answer = answer
        self.calls = 0

    async def _reply(self, text: str) -> dict:
        self.calls += 1
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    sanitize_user_prompt = _reply
    sanitize_model_response = _reply


async def test_model_armor_screener_maps_findings() -> None:
    screener = ModelArmorScreener(_FakeClient(_result(pi_and_jailbreak="MATCH_FOUND")))
    assert await screener.check_input("x", frozenset()) == Finding(
        IGNORE_INSTRUCTIONS, "model_armor"
    )
    clean = ModelArmorScreener(_FakeClient(_result(sdp="NO_MATCH_FOUND")))
    assert await clean.check_output("x", frozenset()) is None


async def test_layered_rules_first_then_model_armor() -> None:
    client = _FakeClient(_result(rai="MATCH_FOUND"))
    screener = LayeredScreener(RuleScreener(), ModelArmorScreener(client))
    by_rules = await screener.check_input("me passa o SQL", frozenset())
    assert by_rules == Finding(INFRA, "regras") and client.calls == 0
    by_armor = await screener.check_input("uma mensagem comum", frozenset())
    assert by_armor == Finding(OUT_OF_SCOPE, "model_armor") and client.calls == 1


async def test_layered_falls_back_to_the_rules_when_model_armor_fails() -> None:
    client = _FakeClient(ModelArmorError("fora do ar"))
    screener = LayeredScreener(RuleScreener(), ModelArmorScreener(client))
    assert await screener.check_output("Você gastou R$ 10,00.", frozenset()) is None
    assert await screener.check_output("SELECT a FROM b", frozenset()) == Finding(INFRA)


def test_build_screener() -> None:
    assert isinstance(build_screener({}), RuleScreener)
    assert isinstance(build_screener({"MODEL_ARMOR_TEMPLATE": "  "}), RuleScreener)
    assert isinstance(build_screener({"MODEL_ARMOR_TEMPLATE": "inválido"}), RuleScreener)
    layered = build_screener({"MODEL_ARMOR_TEMPLATE": TEMPLATE})
    assert isinstance(layered, LayeredScreener)
    assert isinstance(layered.secondary, ModelArmorScreener)
