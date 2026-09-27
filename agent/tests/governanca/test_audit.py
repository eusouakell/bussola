"""Audit trail: minimized summaries, statuses, state changes and failures."""

import json

import pytest
from governance_support import cb_ctx, fake_tool, journey_state, tool_ctx

from bussola_agent.governanca import audit, services
from bussola_agent.governanca.clock import FixedClock
from bussola_agent.persistencia import RegistroEmMemoria, TipoEvento


def test_summary_keeps_names_numbers_and_options_only() -> None:
    summary = audit.summarize_args(
        {
            "cenario": "equilibrado",
            "resumo": "Plano para a minha casa em Moema",
            "aporte": 1250.0,
            "nome": "Nome Com Espaço",
            "ativo": True,
        }
    )
    assert summary == {
        "args": ["aporte", "ativo", "cenario", "nome", "resumo"],
        "numeros": {"aporte": 1250.0},
        "opcoes": {"cenario": "equilibrado"},
    }
    assert "Moema" not in json.dumps(summary)
    assert audit.summarize_args(None) == {"args": []}


async def _call(tool: str, response: dict, ctx, *, remember: bool = True) -> None:  # noqa: ANN001
    if remember:
        audit.remember_tool_call(fake_tool(tool), {"cenario": "equilibrado"}, ctx)
    await audit.record_tool_call(fake_tool(tool), {"cenario": "equilibrado"}, ctx, response)


@pytest.mark.parametrize(
    ("response", "remember", "status", "code"),
    [
        ({"dados": {}}, True, "ok", None),
        (
            {"erro": {"codigo": "CONSENTIMENTO_NECESSARIO", "mensagem": ""}},
            False,
            "bloqueado",
            "CONSENTIMENTO_NECESSARIO",
        ),
        ({"erro": {"codigo": "ESCOPO", "mensagem": ""}}, False, "bloqueado", "ESCOPO"),
        ({"erro": {"codigo": "INDISPONIVEL", "mensagem": ""}}, True, "erro", "INDISPONIVEL"),
        ({"isError": True, "content": []}, True, "erro", "ERRO"),
    ],
)
async def test_tool_call_status(
    response: dict, remember: bool, status: str, code: str | None, registry: RegistroEmMemoria
) -> None:
    await _call("criar_plano", response, tool_ctx(), remember=remember)
    event = registry.eventos[0]
    assert event.tipo_evento == TipoEvento.FERRAMENTA_CHAMADA
    assert event.ferramenta == "criar_plano"
    assert event.resumo["status"] == status
    assert event.resumo.get("erro_codigo") == code
    assert ("latencia_ms" in event.resumo) is remember


async def test_latency_and_state_change(registry: RegistroEmMemoria, clock: FixedClock) -> None:
    ctx = tool_ctx(journey_state(estado_jornada="ORIENTAR"), call_id="c-7")
    audit.remember_tool_call(fake_tool("solicitar_consentimento"), {}, ctx)
    clock.advance(0.25)
    ctx.state["estado_jornada"] = "AGIR"
    await audit.record_tool_call(fake_tool("solicitar_consentimento"), {}, ctx, {"dados": {}})

    call, change = registry.eventos
    assert call.resumo["latencia_ms"] == 250
    assert call.estado == "ORIENTAR"
    assert change.tipo_evento == TipoEvento.ESTADO_ALTERADO
    assert change.resumo == {"de": "ORIENTAR", "para": "AGIR"}
    assert change.estado == "AGIR"


async def test_registry_failure_never_breaks_the_turn() -> None:
    class Broken(RegistroEmMemoria):
        def registrar_evento(self, e):  # noqa: ANN001, ANN201
            raise RuntimeError("bq fora")

    services.configure(registry=Broken())
    ok = await audit.record_event(tool_ctx(), TipoEvento.ACAO_EXECUTADA, {"acao": "x"})
    assert ok is False
    await _call("criar_plano", {"dados": {}}, tool_ctx())  # does not raise


async def test_session_start_once(registry: RegistroEmMemoria) -> None:
    ctx = cb_ctx(session_id="s-1", invocation_id="inv-1")
    await audit.record_session_start(ctx, None)
    await audit.record_session_start(ctx, None)
    await audit.record_session_start(cb_ctx(session_id="s-2"), None)
    starts = [e.session_id for e in registry.eventos if e.tipo_evento == TipoEvento.SESSAO_INICIADA]
    assert starts == ["s-1", "s-2"]


async def test_session_start_skipped_for_an_older_session(registry: RegistroEmMemoria) -> None:
    from types import SimpleNamespace

    older = SimpleNamespace(invocation_id="inv-0", author="bussola", content=None)
    await audit.record_session_start(cb_ctx(invocation_id="inv-5", events=[older]), None)
    assert registry.eventos == []


async def test_events_use_the_clock_and_the_journey_state(
    registry: RegistroEmMemoria, clock: FixedClock
) -> None:
    await audit.record_event(
        tool_ctx(journey_state(estado_jornada="AGIR")), TipoEvento.ACAO_EXECUTADA
    )
    event = registry.eventos[0]
    assert event.ts == clock.now()
    assert event.estado == "AGIR"
    assert event.resumo == {}
