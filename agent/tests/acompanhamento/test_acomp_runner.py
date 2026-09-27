"""Conversa completa no ADK: ``InMemoryRunner`` + ``ScriptedLlm`` + MCP de fixtures (integração).

O agente é montado como o ``root_agent`` do 004 (prompt base + instruções das
extensões, ferramentas locais e das extensões e os 4 agregados de callbacks),
com a composição real: escopo e verificação de números do 004, consentimento,
guardrails e auditoria do 005 e o acompanhamento do 006. O transporte MCP é o
de fixtures: nada sai da máquina e nenhum modelo real é chamado.
"""

import importlib
import sys
from collections.abc import Iterator
from typing import Any

import pytest

import bussola_agent
import bussola_agent.acompanhamento as acompanhamento
import bussola_agent.agent  # noqa: F401  (primeiro import fora dos testes, como em produção)
from bussola_agent import extensoes, mcp_conexao, persistencia_bq
from bussola_agent.acompanhamento.fakes import (
    CONTROL_USER_ID,
    Call,
    Conversation,
    FixtureMcp,
    Turn,
    build_conversation,
    command_router,
    fake_transport,
    install_journey,
    numbers_in_text,
    periods_in,
    plan_state,
    render_tool_answer,
    unbacked_numbers,
)
from bussola_agent.acompanhamento.plan_context import CONTEXT_KEY
from bussola_agent.acompanhamento.tools import GOVERNANCE_PACKAGE
from bussola_agent.governanca import audit, consent, guardrails, services
from bussola_agent.governanca.clock import FixedClock
from bussola_agent.governanca.guardrails import RuleScreener
from bussola_agent.persistencia import RegistroEmMemoria, TipoEvento

FOLLOW_UP_EVENTS = {
    TipoEvento.ACOMPANHAMENTO_MES_AVANCADO.value,
    TipoEvento.DESVIO_DETECTADO.value,
    TipoEvento.ROTA_RECALCULADA.value,
    TipoEvento.PLANO_AJUSTADO.value,
}


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch) -> FixtureMcp:
    fixture_mcp = FixtureMcp()
    monkeypatch.setattr(mcp_conexao, "_chamar_mcp", fake_transport(fixture_mcp))
    return fixture_mcp


@pytest.fixture
def registry(monkeypatch: pytest.MonkeyPatch) -> Iterator[RegistroEmMemoria]:
    """Registro do processo único para 005 e 006, relógio fixo e só as regras locais."""
    monkeypatch.delenv("MODEL_ARMOR_TEMPLATE", raising=False)
    shared = RegistroEmMemoria()
    persistencia_bq.set_default_registry(shared)
    services.configure(clock=FixedClock(), screener=RuleScreener())
    consent.reset_used_ids()
    audit.reset()
    guardrails.reset()
    yield shared
    services.reset()
    consent.reset_used_ids()
    audit.reset()
    guardrails.reset()


@pytest.fixture
def no_governance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, GOVERNANCE_PACKAGE, raising=False)


async def _conversation(state: dict[str, Any], *, governance: bool = True) -> Conversation:
    install_journey(governance=governance)
    return await build_conversation(state)


def _assert_faithful(turn: Turn) -> None:
    """Todo número do texto final está em alguma resposta de ferramenta do turno."""
    assert numbers_in_text(turn.text), turn.text
    assert unbacked_numbers(turn) == [], turn.text


pytestmark = pytest.mark.usefixtures("transport", "registry")


async def test_replay_conversation_from_june_to_september(registry: RegistroEmMemoria) -> None:
    chat = await _conversation(plan_state())

    # 1. O front envia TEXTO_AVANCAR; o modelo tenta um escopo falso, que é ignorado.
    bogus = {"id_usuario": CONTROL_USER_ID, "ate_anomes": 202512}
    first = await chat.say("avançar um mês", Call("avancar_mes", bogus), render_tool_answer)
    (name, envelope), *_ = first.responses
    assert name == "avancar_mes"
    assert first.state["ate_anomes"] == 202507
    assert first.state["id_usuario"] == plan_state()["id_usuario"]
    assert envelope["dados"]["realizado"] == 884.53
    assert envelope["dados"]["status"] == "desvio"
    assert [r["id"] for r in envelope["dados"]["rotas"]] == ["A", "B"]
    assert "R$ 884,53" in first.text and "Viagens" in first.text
    assert "rota A" in first.text and "rota B" in first.text
    _assert_faithful(first)

    # 2. Pedido de ajuste: o modelo pede consentimento antes de ajustar_plano.
    ask = Call("solicitar_consentimento", {"acao": "ajustar_plano", "resumo": "Adotar a rota A"})
    second = await chat.say("Quero adotar a rota A", ask, render_tool_answer)
    assert second.state["consentimentos"]["ajustar_plano"]["status"] == "pendente"
    assert "autorização" in second.text
    assert second.state["plano_id"] == "plano-inicial"

    # 3. "sim" aceita o consentimento (005); argumentos extras do modelo são descartados.
    adjust = Call("ajustar_plano", {"rota": "A", "plano_id": "outro", "consent_id": "falso"})
    third = await chat.say("sim", adjust, render_tool_answer)
    (name, envelope), *_ = third.responses
    assert name == "ajustar_plano"
    assert envelope["dados"]["aporte_mensal"] == 2570.24
    assert third.text == (
        "Plano ajustado: R$ 2.570,24 por mês, 23 meses até a meta. Nenhum dinheiro foi movido."
    )
    assert third.state["plano_id"] == envelope["dados"]["plano_id"] != "plano-inicial"
    assert third.state["estado_jornada"] == "ACOMPANHAR"
    assert third.state["ate_anomes"] == 202507

    # 4. Agosto sob o plano ajustado.
    fourth = await chat.say("avançar um mês", command_router, render_tool_answer)
    (_, envelope), *_ = fourth.responses
    assert (envelope["dados"]["planejado"], envelope["dados"]["realizado"]) == (2570.24, 4218.74)
    assert envelope["dados"]["status"] == "folga"
    assert envelope["dados"]["acumulado"] == 5103.27
    _assert_faithful(fourth)

    # 5. Setembro e status: o status não avança o mês.
    await chat.say("avançar um mês", command_router, render_tool_answer)
    status = await chat.say("Ver status do plano", command_router, render_tool_answer)
    (name, envelope), *_ = status.responses
    assert name == "status_plano"
    assert status.state["ate_anomes"] == 202509
    assert envelope["dados"]["percentual"] == 14.71
    assert envelope["fonte"]["periodo"] == {"inicio": 202507, "fim": 202509}
    assert "14,71%" in status.text and "R$ 51.173,26" in status.text
    _assert_faithful(status)

    # Contexto do acompanhamento e trilha de eventos no registro.
    context = status.state[CONTEXT_KEY]
    assert context["planos"] == ["plano-inicial", third.state["plano_id"]]
    assert [h["anomes"] for h in status.state["acompanhamento"]] == [202507, 202508, 202509]
    events = [e.tipo_evento.value for e in registry.eventos]
    follow_up = [e for e in events if e in FOLLOW_UP_EVENTS]
    assert follow_up[:3] == ["acompanhamento_mes_avancado", "desvio_detectado", "rota_recalculada"]
    assert "plano_ajustado" in follow_up
    assert follow_up.count("acompanhamento_mes_avancado") == 3
    # O mesmo registro recebe a trilha do 005: pedido e decisão do consentimento.
    assert {"consentimento_solicitado", "consentimento_decidido"} <= set(events)
    (decision,) = registry.consentimentos
    assert (decision.acao, decision.decisao) == ("ajustar_plano", "aceito")


async def test_no_tool_response_reveals_a_month_after_the_cut() -> None:
    chat = await _conversation(plan_state())
    for expected_cut in (202507, 202508, 202509):
        turn = await chat.say("avançar um mês", command_router, render_tool_answer)
        assert turn.state["ate_anomes"] == expected_cut
        for _, envelope in turn.responses:
            assert max(periods_in(envelope)) <= expected_cut


async def test_the_model_sees_the_006_instructions_and_the_three_tools() -> None:
    chat = await _conversation(plan_state())
    await chat.say("Ver status do plano", command_router, render_tool_answer)
    request = chat.llm.requests[0]
    assert "## Acompanhamento mês a mês" in str(request.config.system_instruction)
    declared = {
        d.name for tool in request.config.tools or [] for d in tool.function_declarations or []
    }
    assert {"avancar_mes", "status_plano", "ajustar_plano"} <= declared


async def test_the_consent_gate_blocks_ajustar_plano_without_consent() -> None:
    chat = await _conversation(plan_state())
    await chat.say("avançar um mês", command_router, render_tool_answer)
    turn = await chat.say("rota A", Call("ajustar_plano", {"rota": "A"}), render_tool_answer)
    (_, envelope), *_ = turn.responses
    assert envelope["erro"]["codigo"] == "CONSENTIMENTO_NECESSARIO"
    assert turn.state["plano_id"] == "plano-inicial"


@pytest.mark.usefixtures("no_governance")
async def test_the_local_guard_blocks_ajustar_plano_while_005_is_absent() -> None:
    chat = await _conversation(plan_state(), governance=False)
    await chat.say("avançar um mês", command_router, render_tool_answer)
    turn = await chat.say("rota A", Call("ajustar_plano", {"rota": "A"}), render_tool_answer)
    (_, envelope), *_ = turn.responses
    assert envelope["erro"]["codigo"] == "CONSENTIMENTO_NECESSARIO"
    assert turn.text == envelope["erro"]["mensagem"]
    assert turn.state["plano_id"] == "plano-inicial"


async def test_end_of_replay_is_reported_in_customer_words() -> None:
    chat = await _conversation(plan_state(ate_anomes=202512))
    turn = await chat.say("avançar um mês", command_router, render_tool_answer)
    (_, envelope), *_ = turn.responses
    assert envelope["erro"]["codigo"] == "FIM_DO_REPLAY"
    assert turn.state["ate_anomes"] == 202512
    assert turn.text == envelope["erro"]["mensagem"]


async def test_without_a_plan_the_customer_is_told_to_create_one() -> None:
    chat = await _conversation(plan_state(plano_id=None))
    turn = await chat.say("avançar um mês", command_router, render_tool_answer)
    (_, envelope), *_ = turn.responses
    assert envelope["erro"]["codigo"] == "SEM_PLANO_ATIVO"
    assert turn.state["ate_anomes"] == 202506


def test_hello_root_agent_exposes_the_006_tools_and_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Salvaguarda para a troca do ``agent.py`` pelo 004: o esqueleto continua compondo o 006.

    O pacote sai de ``sys.modules`` para que ``carregar_extensoes()`` o importe
    de fato, como no primeiro import em produção.
    """
    monkeypatch.setattr(bussola_agent, "acompanhamento", acompanhamento)
    monkeypatch.delitem(sys.modules, "bussola_agent.acompanhamento")
    monkeypatch.delitem(sys.modules, "bussola_agent.agent", raising=False)
    module = importlib.import_module("bussola_agent.agent")
    names = {getattr(t, "__name__", None) for t in module.root_agent.tools}
    assert {"avancar_mes", "status_plano", "ajustar_plano"} <= names
    assert "## Acompanhamento mês a mês" in module.root_agent.instruction
    assert "ajustar_plano" in extensoes.ferramentas_sensiveis()
