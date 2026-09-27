"""Consent: parser, ``solicitar_consentimento``, reply reader and gate."""

import asyncio

import pytest
from google.adk.models import LlmRequest
from governance_support import cb_ctx, fake_tool, journey_state, tool_ctx

from bussola_agent.governanca import consent
from bussola_agent.governanca.consent import Decision, parse_reply
from bussola_agent.governanca.envelope import CONSENT_REQUIRED, INVALID_INPUT, NOT_ALLOWED
from bussola_agent.persistencia import RegistroEmMemoria, TipoEvento


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sim", Decision.ACCEPT),
        ("Sim, autorizo", Decision.ACCEPT),
        ("pode sim!", Decision.ACCEPT),
        ("ok, confirmo", Decision.ACCEPT),
        ("não", Decision.REFUSE),
        ("Agora não", Decision.REFUSE),
        ("NÃO, recuso", Decision.REFUSE),
        ("cancela", Decision.REFUSE),
        ("sim, mas depois", Decision.AMBIGUOUS),
        ("talvez", Decision.AMBIGUOUS),
        ("não sei", Decision.AMBIGUOUS),
        ("sim ou não?", Decision.AMBIGUOUS),
        ("pode?", Decision.AMBIGUOUS),
        ("quanto eu gasto com mercado por mês", Decision.NONE),
        ("quanto gasto com mercado?", Decision.NONE),
        ("depois do aporte, quanto sobra", Decision.NONE),
        ("será?", Decision.AMBIGUOUS),
        ("", Decision.NONE),
        (None, Decision.NONE),
        (
            "não entendi direito o que você falou sobre o aporte mas pode explicar melhor",
            Decision.NONE,
        ),
    ],
)
def test_parse_reply(text: object, expected: Decision) -> None:
    assert parse_reply(text) is expected


# ---------------------------------------------------------------------------
# solicitar_consentimento
# ---------------------------------------------------------------------------


async def test_request_creates_a_pending_entry(registry: RegistroEmMemoria) -> None:
    ctx = tool_ctx(invocation_id="inv-1")
    result = await consent.solicitar_consentimento("criar_plano", "Plano equilibrado", ctx)

    data = result["dados"]
    assert set(data) >= {
        "consent_id",
        "acao",
        "resumo",
        "status",
        "o_que_faz",
        "o_que_nao_faz",
        "dados_usados",
    }
    assert data["status"] == "pendente" and data["acao"] == "criar_plano"
    assert result["fonte"] == {
        "ferramenta": "solicitar_consentimento",
        "tabelas": [],
        "periodo": None,
    }
    entry = ctx.state["consentimentos"]["criar_plano"]
    assert entry == {
        "consent_id": data["consent_id"],
        "status": "pendente",
        "ts": "2026-09-26T12:00:00Z",
        "resumo": "Plano equilibrado",
        "invocation_id": "inv-1",
    }
    assert ctx.state["estado_jornada"] == "AGIR"
    assert [e.tipo_evento for e in registry.eventos] == [TipoEvento.CONSENTIMENTO_SOLICITADO]
    assert registry.consentimentos == []  # only a decision writes the row


async def test_new_request_replaces_older_pending_ones() -> None:
    state = journey_state(
        consentimentos={
            "ativar_lembretes": {"consent_id": "a", "status": "pendente", "ts": "x"},
            "criar_plano": {"consent_id": "b", "status": "aceito", "ts": "x", "usado": True},
        }
    )
    await consent.solicitar_consentimento("simular_contratacao", "Simular", tool_ctx(state))
    assert set(state["consentimentos"]) == {"criar_plano", "simular_contratacao"}


async def test_request_keeps_acompanhar_state() -> None:
    state = journey_state(estado_jornada="ACOMPANHAR")
    await consent.solicitar_consentimento("ajustar_plano", "Ajustar", tool_ctx(state))
    assert state["estado_jornada"] == "ACOMPANHAR"


@pytest.mark.parametrize(
    ("action", "code"),
    [
        ("compartilhar_dados", NOT_ALLOWED),
        ("resumo_mes", INVALID_INPUT),
        ("transferir_pix", INVALID_INPUT),
        ("", INVALID_INPUT),
    ],
)
async def test_request_rejects(action: str, code: str) -> None:
    ctx = tool_ctx()
    result = await consent.solicitar_consentimento(action, "x", ctx)
    assert result["erro"]["codigo"] == code
    assert ctx.state["consentimentos"] == {}


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        ("  Criar o plano   equilibrado?  ", "Criar o plano equilibrado"),
        ("", "Criar o seu plano"),
        (None, "Criar o seu plano"),
        ("Rodar SELECT * FROM transacoes", "Criar o seu plano"),
        ("<b>plano</b> [x]", "bplano/b x"),
    ],
)
def test_clean_summary(summary: object, expected: str) -> None:
    assert consent.clean_summary(summary, "criar_plano") == expected


def test_clean_summary_is_capped() -> None:
    text = consent.clean_summary("a" * 500, "criar_plano")
    assert len(text) == consent.MAX_SUMMARY_LENGTH and text.endswith("…")


# ---------------------------------------------------------------------------
# read_reply
# ---------------------------------------------------------------------------


def _pending_state(invocation_id: str = "inv-1") -> dict:
    return journey_state(
        estado_jornada="AGIR",
        consentimentos={
            "criar_plano": {
                "consent_id": "c-1",
                "status": "pendente",
                "ts": "2026-09-26T11:59:00Z",
                "resumo": "Plano equilibrado",
                "invocation_id": invocation_id,
            }
        },
    )


async def test_accept_records_and_instructs(registry: RegistroEmMemoria) -> None:
    ctx = cb_ctx(_pending_state(), "sim")
    request = LlmRequest()
    assert await consent.read_reply(ctx, request) is None

    entry = ctx.state["consentimentos"]["criar_plano"]
    assert entry["status"] == "aceito"
    assert "invocation_id" not in entry and "usado" not in entry
    row = registry.consentimentos[0]
    assert (row.consent_id, row.acao, row.decisao) == ("c-1", "criar_plano", "aceito")
    assert row.texto_apresentado == (
        "Posso criar o seu plano: Plano equilibrado? Responda **sim** ou **não**."
    )
    assert consent.INSTRUCTION_ACCEPTED.format(acao="criar_plano") in str(
        request.config.system_instruction
    )
    decided = [e for e in registry.eventos if e.tipo_evento == TipoEvento.CONSENTIMENTO_DECIDIDO]
    assert decided[0].resumo == {"acao": "criar_plano", "consent_id": "c-1", "decisao": "aceito"}


async def test_refuse_returns_a_fixed_reply(registry: RegistroEmMemoria) -> None:
    ctx = cb_ctx(_pending_state(), "não quero")
    reply = await consent.read_reply(ctx, LlmRequest())

    assert reply.content.parts[0].text == consent.MSG_REFUSED
    assert reply.custom_metadata == {
        "bussola": {"respostas_rapidas": list(consent.REFUSAL_CHIPS["criar_plano"])}
    }
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "recusado"
    assert [c.decisao for c in registry.consentimentos] == ["recusado"]


async def test_ambiguous_asks_again(registry: RegistroEmMemoria) -> None:
    ctx = cb_ctx(_pending_state(), "talvez")
    reply = await consent.read_reply(ctx, LlmRequest())
    assert reply.content.parts[0].text == consent.MSG_CONFIRM
    assert reply.custom_metadata["bussola"]["respostas_rapidas"] == ["Sim, autorizo", "Agora não"]
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "pendente"
    assert registry.consentimentos == []


async def test_no_answer_tells_the_model_to_ask_again() -> None:
    ctx = cb_ctx(_pending_state(), "quanto gasto com mercado?")
    request = LlmRequest()
    assert await consent.read_reply(ctx, request) is None
    assert "pendente para criar_plano" in str(request.config.system_instruction)
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "pendente"


async def test_same_invocation_waits_for_the_customer(registry: RegistroEmMemoria) -> None:
    ctx = cb_ctx(_pending_state("inv-2"), "sim", invocation_id="inv-2")
    assert await consent.read_reply(ctx, LlmRequest()) is None
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "pendente"
    assert registry.consentimentos == []


async def test_nothing_pending_does_nothing() -> None:
    request = LlmRequest()
    assert await consent.read_reply(cb_ctx(journey_state(), "sim"), request) is None
    assert request.config.system_instruction is None


class _FailingRegistry(RegistroEmMemoria):
    def registrar_consentimento(self, c):  # noqa: ANN001, ANN201
        raise RuntimeError("bq fora")


async def test_accept_stays_pending_when_the_row_fails() -> None:
    from bussola_agent.governanca import services

    services.configure(registry=_FailingRegistry())
    ctx = cb_ctx(_pending_state(), "sim")
    reply = await consent.read_reply(ctx, LlmRequest())
    assert reply.content.parts[0].text == consent.MSG_RECORD_FAILED
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "pendente"


async def test_refusal_holds_when_the_row_fails() -> None:
    from bussola_agent.governanca import services

    services.configure(registry=_FailingRegistry())
    ctx = cb_ctx(_pending_state(), "não")
    reply = await consent.read_reply(ctx, LlmRequest())
    assert reply.content.parts[0].text == consent.MSG_REFUSED
    assert ctx.state["consentimentos"]["criar_plano"]["status"] == "recusado"


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------


def _accepted_state(**extra: object) -> dict:
    entry = {"consent_id": "c-9", "status": "aceito", "ts": "x", **extra}
    return journey_state(consentimentos={"criar_plano": entry})


async def test_gate_lets_free_tools_through() -> None:
    assert await consent.gate(fake_tool("resumo_mes"), {}, tool_ctx()) is None
    assert await consent.gate(fake_tool("solicitar_consentimento"), {}, tool_ctx()) is None


@pytest.mark.parametrize("name", ["criar_plano", "transferir_pix"])
async def test_gate_blocks_without_consent(name: str) -> None:
    result = await consent.gate(fake_tool(name), {}, tool_ctx())
    assert result == {"erro": {"codigo": CONSENT_REQUIRED, "mensagem": consent.MSG_GATE_REQUIRED}}


async def test_gate_blocks_a_pending_request() -> None:
    state = journey_state(consentimentos={"criar_plano": {"consent_id": "p", "status": "pendente"}})
    result = await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(state))
    assert result["erro"]["codigo"] == CONSENT_REQUIRED


async def test_gate_consumes_the_consent_once() -> None:
    state = _accepted_state()
    assert await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(state)) is None
    assert state["consentimentos"]["criar_plano"]["usado"] is True
    second = await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(state))
    assert second["erro"]["codigo"] == CONSENT_REQUIRED


async def test_gate_does_not_reuse_a_released_id_from_a_stale_state() -> None:
    assert await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(_accepted_state())) is None
    stale = await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(_accepted_state()))
    assert stale["erro"]["codigo"] == CONSENT_REQUIRED


async def test_gate_parallel_calls_release_once() -> None:
    results = await asyncio.gather(
        *(consent.gate(fake_tool("criar_plano"), {}, tool_ctx(_accepted_state())) for _ in range(5))
    )
    assert sum(r is None for r in results) == 1


async def test_gate_consent_is_per_action() -> None:
    result = await consent.gate(fake_tool("ativar_lembretes"), {}, tool_ctx(_accepted_state()))
    assert result["erro"]["codigo"] == CONSENT_REQUIRED


async def test_gate_after_refusal_says_so() -> None:
    state = journey_state(consentimentos={"criar_plano": {"consent_id": "r", "status": "recusado"}})
    result = await consent.gate(fake_tool("criar_plano"), {}, tool_ctx(state))
    assert result["erro"]["mensagem"] == consent.MSG_GATE_REFUSED


async def test_gate_forbids_share_data_even_with_consent(registry: RegistroEmMemoria) -> None:
    state = journey_state(
        consentimentos={"compartilhar_dados": {"consent_id": "z", "status": "aceito"}}
    )
    result = await consent.gate(fake_tool("compartilhar_dados"), {}, tool_ctx(state))
    assert result["erro"]["codigo"] == NOT_ALLOWED
    assert registry.eventos[0].tipo_evento == TipoEvento.GUARDRAIL_BLOQUEIO
