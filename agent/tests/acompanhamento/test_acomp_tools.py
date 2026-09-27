"""Ferramentas do ACOMPANHAR chamadas direto, com MCP e registro fakes (unidade).

``avancar_mes``, ``status_plano`` e ``ajustar_plano`` recebem um
``ToolContext`` mínimo (``state`` + ``session.id``). Os números esperados vêm
das fixtures do cliente âncora (``contracts/fixtures/``).
"""

import io
import json
import shutil
import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from bussola_agent.acompanhamento import envelopes, ports
from bussola_agent.acompanhamento.fakes import (
    ANCHOR_USER_ID,
    CONTROL_USER_ID,
    FIXTURES_DIR,
    FixtureMcp,
    FixtureMcpGateway,
    plan_state,
    tool_context,
)
from bussola_agent.acompanhamento.plan_context import CONTEXT_KEY
from bussola_agent.acompanhamento.tools import (
    GOVERNANCE_PACKAGE,
    WARNING_ADJUSTMENT,
    ajustar_plano,
    avancar_mes,
    status_plano,
)
from bussola_agent.logging_json import CAMPOS_PERMITIDOS, configurar_logging
from bussola_agent.persistencia import RegistroEmMemoria

pytestmark = pytest.mark.usefixtures("gateway")

CONSENT = {"ajustar_plano": {"consent_id": "consent-1", "status": "aceito", "ts": "t"}}


@pytest.fixture
def no_governance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o 005 carregado: vale a guarda local de consentimento."""
    monkeypatch.delitem(sys.modules, GOVERNANCE_PACKAGE, raising=False)


def _events(registry: RegistroEmMemoria) -> list[str]:
    return [e.tipo_evento.value for e in registry.eventos]


def _code(envelope: dict[str, Any]) -> str:
    return envelope["erro"]["codigo"]


async def _advanced(**state_overrides: Any) -> tuple[dict[str, Any], Any]:
    ctx = tool_context(plan_state(**state_overrides))
    return await avancar_mes(ctx), ctx


# --- avancar_mes ------------------------------------------------------------


async def test_advance_reveals_the_next_month_and_detects_the_deviation(
    mcp: FixtureMcp, registry: RegistroEmMemoria
) -> None:
    result, ctx = await _advanced()
    state, dados = ctx.state, result["dados"]

    assert state["ate_anomes"] == 202507
    assert state["estado_jornada"] == "ACOMPANHAR"
    assert {k: dados[k] for k in ("anomes", "planejado", "realizado", "desvio", "tolerancia")} == {
        "anomes": 202507,
        "planejado": 2500.0,
        "realizado": 884.53,
        "desvio": -1615.47,
        "tolerancia": 250.0,
    }
    assert dados["status"] == "desvio"
    assert dados["categoria_desvio"] == {
        "macro": "Viagens",
        "valor_mes": 935.14,
        "media_base": 6.51,
        "aumento": 928.63,
    }
    assert (dados["acumulado"], dados["restante"], dados["percentual"]) == (884.53, 59115.47, 1.47)
    assert (dados["meses_decorridos"], dados["meses_restantes"]) == (1, 23)
    assert [(r["id"], r["aporte_mensal"], r["prazo_meses"]) for r in dados["rotas"]] == [
        ("A", 2570.24, 23),
        ("B", 2500.0, 24),
    ]
    assert dados["resumo_mes"]["dados"]["anomes"] == 202507
    assert result["fonte"]["ferramenta"] == "avancar_mes"
    assert result["fonte"]["periodo"] == {"inicio": 202507, "fim": 202507}
    assert result["avisos"][0] == envelopes.WARNING_REPLAY

    assert state["acompanhamento"] == [
        {
            "plano_id": "plano-inicial",
            "anomes": 202507,
            "planejado": 2500.0,
            "realizado": 884.53,
            "desvio": -1615.47,
            "status": "desvio",
            "categoria_desvio": "Viagens",
        }
    ]
    assert [r["id"] for r in state[CONTEXT_KEY]["rotas"]] == ["A", "B"]
    assert _events(registry) == [
        "acompanhamento_mes_avancado",
        "desvio_detectado",
        "rota_recalculada",
    ]
    (row,) = registry.acompanhamentos
    assert (row.anomes, row.acao_sugerida, row.categoria_desvio) == (
        202507,
        "rota_recalculada",
        "Viagens",
    )
    # Nenhuma chamada ao MCP passa do mês revelado.
    assert all(args["ate_anomes"] <= 202507 for _, args in mcp.calls)
    assert all(args.get("anomes", 0) <= args["ate_anomes"] for _, args in mcp.calls)


@pytest.mark.parametrize(
    ("aporte", "status", "action"),
    [(900.0, "no_plano", "manter_plano"), (500.0, "folga", "manter_ou_antecipar")],
)
async def test_months_without_deviation_have_no_routes(
    registry: RegistroEmMemoria, aporte: float, status: str, action: str
) -> None:
    result, _ = await _advanced(aporte_mensal=aporte)
    dados = result["dados"]
    assert (dados["status"], dados["categoria_desvio"], dados["rotas"]) == (status, None, [])
    assert result["avisos"] == [envelopes.WARNING_REPLAY]
    assert _events(registry) == ["acompanhamento_mes_avancado"]
    assert registry.acompanhamentos[0].acao_sugerida == action


async def test_the_baseline_is_fetched_once_per_lineage(mcp: FixtureMcp) -> None:
    ctx = tool_context(plan_state(aporte_mensal=5000.0))
    first = await avancar_mes(ctx)
    second = await avancar_mes(ctx)
    assert (first["dados"]["status"], second["dados"]["status"]) == ("desvio", "desvio")
    summaries = [args["anomes"] for tool, args in mcp.calls if tool == "resumo_mes"]
    assert summaries == [202507, 202501, 202502, 202503, 202504, 202505, 202506, 202508]
    assert second["dados"]["categoria_desvio"]["macro"] == "Produtos financeiros"


async def test_a_baseline_month_without_data_counts_as_zero(mcp: FixtureMcp) -> None:
    mcp.fail_months[202506] = "DADOS_INSUFICIENTES"
    result, ctx = await _advanced()
    assert result["dados"]["categoria_desvio"]["macro"] == "Viagens"
    assert envelopes.WARNING_CATEGORY_UNAVAILABLE not in result["avisos"]
    assert ctx.state[CONTEXT_KEY]["linha_base"]["Casa"] < 2600


async def test_a_failed_baseline_month_leaves_the_month_without_category(
    mcp: FixtureMcp,
) -> None:
    mcp.fail_months[202503] = "INDISPONIVEL"
    result, ctx = await _advanced()
    assert result["dados"]["categoria_desvio"] is None
    assert envelopes.WARNING_CATEGORY_UNAVAILABLE in result["avisos"]
    assert [r["id"] for r in result["dados"]["rotas"]] == ["A", "B"]
    assert ctx.state[CONTEXT_KEY]["linha_base"] is None


async def test_end_of_replay_does_not_touch_the_state(mcp: FixtureMcp) -> None:
    result, ctx = await _advanced(ate_anomes=202512)
    assert _code(result) == "FIM_DO_REPLAY"
    assert result["erro"]["mensagem"] == envelopes.MSG_END_OF_REPLAY
    assert ctx.state["ate_anomes"] == 202512
    assert mcp.calls == []


async def test_no_active_plan(mcp: FixtureMcp) -> None:
    result, ctx = await _advanced(plano_id=None)
    assert _code(result) == "SEM_PLANO_ATIVO"
    assert ctx.state["ate_anomes"] == 202506
    assert mcp.calls == []


@pytest.mark.parametrize(
    ("key", "value"), [("id_usuario", "não-é-uuid"), ("ate_anomes", 202413), ("ate_anomes", None)]
)
async def test_invalid_scope_is_rejected_before_any_call(
    mcp: FixtureMcp, key: str, value: Any
) -> None:
    state = plan_state()
    state[key] = value
    for tool in (avancar_mes, status_plano, ajustar_plano):
        result = await tool(tool_context(state))
        assert _code(result) == "ENTRADA_INVALIDA"
        assert "não-é-uuid" not in json.dumps(result, ensure_ascii=False)
    assert mcp.calls == []


async def test_mcp_errors_pass_through_and_keep_the_month(mcp: FixtureMcp) -> None:
    mcp.fail_tools["resumo_mes"] = "INDISPONIVEL"
    result, ctx = await _advanced()
    assert _code(result) == "INDISPONIVEL"
    assert result["erro"]["mensagem"] == "Dados de exemplo indisponíveis."
    assert ctx.state["ate_anomes"] == 202506
    assert ctx.state["acompanhamento"] == []


async def test_a_client_without_a_recorded_golden_is_still_served(mcp: FixtureMcp) -> None:
    """BUG-05: a persona de controle tem 12 meses; não ter golden não é não ter dados."""
    result, ctx = await _advanced(user_id=CONTROL_USER_ID)
    assert "erro" not in result, result
    assert result["dados"]["anomes"] == 202507
    assert ctx.state["ate_anomes"] == 202507
    assert {tool for tool, _ in mcp.calls} == {"resumo_mes", "simular_objetivo"}
    assert all(args["id_usuario"] == CONTROL_USER_ID for _, args in mcp.calls)


async def test_no_month_until_the_cut_is_insufficient_data(tmp_path: Path) -> None:
    """Única razão honesta de ``DADOS_INSUFICIENTES``: nenhum mês até o corte."""
    shutil.copytree(FIXTURES_DIR, tmp_path / "fixtures")
    perfil = tmp_path / "fixtures" / "bussola_dados" / "perfil_mensal.json"
    linhas = json.loads(perfil.read_text(encoding="utf-8"))
    perfil.write_text(
        json.dumps([row for row in linhas if row["id_usuario"] != CONTROL_USER_ID]),
        encoding="utf-8",
    )
    mcp = FixtureMcp(fixtures_dir=tmp_path / "fixtures")
    scope = {"ate_anomes": 202506, "anomes": 202503}
    assert "dados" in mcp.call("resumo_mes", {"id_usuario": ANCHOR_USER_ID, **scope})
    recusa = mcp.call("resumo_mes", {"id_usuario": CONTROL_USER_ID, **scope})
    assert recusa["erro"]["codigo"] == "DADOS_INSUFICIENTES"
    assert "mock" not in recusa["erro"]["mensagem"]


class _LeakyGateway(FixtureMcpGateway):
    """``resumo_mes`` com período depois do mês pedido."""

    async def monthly_summary(self, anomes: int, state: Any) -> dict[str, Any]:
        envelope = await super().monthly_summary(anomes, state)
        envelope["fonte"]["periodo"]["fim"] = 202512
        return envelope


async def test_a_summary_beyond_the_cut_is_refused() -> None:
    ports.configure_gateway(_LeakyGateway())
    result, ctx = await _advanced()
    assert _code(result) == "INDISPONIVEL"
    assert ctx.state["ate_anomes"] == 202506


class _BrokenRegistry(RegistroEmMemoria):
    def registrar_evento(self, e: Any) -> str:
        raise RuntimeError("tabela fora do ar")

    def registrar_acompanhamento(self, a: Any) -> None:
        raise RuntimeError("tabela fora do ar")


@pytest.fixture
def json_logs() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    configurar_logging(nivel="DEBUG", stream=buffer)
    yield buffer
    configurar_logging()


def _lines(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


async def test_registry_failures_do_not_break_the_month(json_logs: io.StringIO) -> None:
    ports.configure_registry(_BrokenRegistry())
    result, ctx = await _advanced()
    assert result["dados"]["status"] == "desvio"
    assert ctx.state["ate_anomes"] == 202507
    warnings = [line for line in _lines(json_logs) if line["severity"] == "WARNING"]
    assert len(warnings) == 4
    assert {line["erro_codigo"] for line in warnings} == {"REGISTRO_INDISPONIVEL"}
    assert "tabela fora do ar" not in json_logs.getvalue()


async def test_logs_carry_only_the_allowed_fields(json_logs: io.StringIO) -> None:
    await _advanced()
    lines = _lines(json_logs)
    assert lines, "o 006 registra os eventos em log"
    base = {"severity", "message", "servico", "timestamp"}
    assert all(set(line) <= base | set(CAMPOS_PERMITIDOS) for line in lines)
    text = json_logs.getvalue()
    for secret in ("884.53", "Viagens", "Reserva de emergência", "36a21505"):
        assert secret not in text


# --- ajustar_plano ----------------------------------------------------------


@pytest.mark.usefixtures("no_governance")
async def test_adjust_is_blocked_without_consent(registry: RegistroEmMemoria) -> None:
    _, ctx = await _advanced()
    result = await ajustar_plano(ctx, rota="A")
    assert _code(result) == "CONSENTIMENTO_NECESSARIO"
    assert registry.planos == []
    assert ctx.state["plano_id"] == "plano-inicial"

    ctx.state["consentimentos"] = {"ajustar_plano": {"status": "recusado", "consent_id": "c"}}
    assert _code(await ajustar_plano(ctx, rota="A")) == "CONSENTIMENTO_NECESSARIO"


async def test_the_governance_gate_replaces_the_local_guard(
    monkeypatch: pytest.MonkeyPatch, registry: RegistroEmMemoria
) -> None:
    monkeypatch.setitem(sys.modules, GOVERNANCE_PACKAGE, types.ModuleType(GOVERNANCE_PACKAGE))
    _, ctx = await _advanced()
    result = await ajustar_plano(ctx, rota="A")
    assert result["dados"]["rota"] == "A"
    assert len(registry.planos) == 1


@pytest.mark.usefixtures("no_governance")
async def test_adjust_adopts_route_a_and_the_next_month_follows_it(
    registry: RegistroEmMemoria,
) -> None:
    _, ctx = await _advanced()
    ctx.state["consentimentos"] = CONSENT

    result = await ajustar_plano(ctx, rota="A")
    dados = result["dados"]
    (stored,) = registry.planos
    assert dados == {
        "plano_id": stored.plano_id,
        "plano_anterior_id": "plano-inicial",
        "rota": "A",
        "aporte_mensal": 2570.24,
        "prazo_meses": 24,
        "prazo_restante_meses": 23,
        "mensagem": (
            "Plano ajustado: R$ 2.570,24 por mês, 23 meses até a meta. Nenhum dinheiro foi movido."
        ),
    }
    assert result["fonte"] == {"ferramenta": "ajustar_plano", "tabelas": [], "periodo": None}
    assert result["avisos"] == [WARNING_ADJUSTMENT]
    assert (stored.aporte_mensal, stored.prazo_meses, stored.ate_anomes) == (2570.24, 24, 202507)
    assert (stored.valor_alvo, stored.cenario) == (60000.0, "equilibrado")
    assert ctx.state["plano_id"] == stored.plano_id
    assert ctx.state[CONTEXT_KEY]["planos"] == ["plano-inicial", stored.plano_id]
    assert ctx.state[CONTEXT_KEY]["rotas"] == []
    assert _events(registry)[-1] == "plano_ajustado"

    following = (await avancar_mes(ctx))["dados"]
    assert (following["planejado"], following["realizado"], following["status"]) == (
        2570.24,
        4218.74,
        "folga",
    )
    assert (following["acumulado"], following["meses_decorridos"]) == (5103.27, 2)
    assert following["meses_restantes"] == 22


@pytest.mark.usefixtures("no_governance")
@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"rota": "rota b"}, "B"),
        ({"rota": " a "}, "A"),
        ({"aporte_mensal": 2500.0}, "B"),
        ({"prazo_meses": 23}, "A"),
        ({"rota": "A", "aporte_mensal": 2570.24, "prazo_meses": 24}, "A"),
    ],
)
async def test_route_selection(kwargs: dict[str, Any], expected: str) -> None:
    _, ctx = await _advanced()
    ctx.state["consentimentos"] = CONSENT
    assert (await ajustar_plano(ctx, **kwargs))["dados"]["rota"] == expected


@pytest.mark.usefixtures("no_governance")
@pytest.mark.parametrize(
    "kwargs",
    [{}, {"rota": "C"}, {"rota": "A", "aporte_mensal": 3000.0}, {"aporte_mensal": 1.0}],
)
async def test_ambiguous_or_invented_routes_are_refused(
    kwargs: dict[str, Any], registry: RegistroEmMemoria
) -> None:
    _, ctx = await _advanced()
    ctx.state["consentimentos"] = CONSENT
    result = await ajustar_plano(ctx, **kwargs)
    assert result["erro"] == {"codigo": "ENTRADA_INVALIDA", "mensagem": envelopes.MSG_WHICH_ROUTE}
    assert registry.planos == []


@pytest.mark.usefixtures("no_governance")
async def test_there_is_no_route_before_a_deviation_nor_after_adopting_one() -> None:
    ctx = tool_context(plan_state())
    ctx.state["consentimentos"] = CONSENT
    no_route = await ajustar_plano(ctx, rota="A")
    assert no_route["erro"]["mensagem"] == envelopes.MSG_NO_ROUTE

    await avancar_mes(ctx)
    assert "dados" in await ajustar_plano(ctx, rota="A")
    again = await ajustar_plano(ctx, rota="B")
    assert again["erro"]["mensagem"] == envelopes.MSG_NO_ROUTE


class _NoPlanStorage(RegistroEmMemoria):
    def registrar_plano(self, plano: Any) -> str:
        raise RuntimeError("fora do ar")


@pytest.mark.usefixtures("no_governance")
async def test_adjust_keeps_the_current_plan_when_storage_fails() -> None:
    ports.configure_registry(_NoPlanStorage())
    _, ctx = await _advanced()
    ctx.state["consentimentos"] = CONSENT
    assert _code(await ajustar_plano(ctx, rota="A")) == "INDISPONIVEL"
    assert ctx.state["plano_id"] == "plano-inicial"
    assert [r["id"] for r in ctx.state[CONTEXT_KEY]["rotas"]] == ["A", "B"]


# --- status_plano -----------------------------------------------------------


async def test_status_without_history() -> None:
    state = plan_state()
    result = await status_plano(tool_context(state))
    dados = result["dados"]
    assert dados["objetivo"] == state["objetivo"]
    assert dados["plano"]["aporte_mensal"] == 2500.0
    assert (dados["meses_decorridos"], dados["meses_restantes"]) == (0, 24)
    assert (dados["acumulado"], dados["restante"], dados["percentual"]) == (0.0, 60000.0, 0.0)
    assert (dados["ultimo_status"], dados["historico"]) == (None, [])
    assert result["fonte"] == {"ferramenta": "status_plano", "tabelas": [], "periodo": None}


async def test_status_does_not_advance_the_month(mcp: FixtureMcp) -> None:
    state = plan_state()
    await status_plano(tool_context(state))
    assert state["ate_anomes"] == 202506
    assert mcp.calls == []


@pytest.mark.usefixtures("no_governance")
async def test_status_after_three_months_follows_the_lineage() -> None:
    ctx = tool_context(plan_state())
    await avancar_mes(ctx)
    ctx.state["consentimentos"] = CONSENT
    await ajustar_plano(ctx, rota="A")
    await avancar_mes(ctx)
    await avancar_mes(ctx)

    result = await status_plano(ctx)
    dados = result["dados"]
    assert (dados["acumulado"], dados["restante"], dados["percentual"]) == (
        8826.74,
        51173.26,
        14.71,
    )
    assert (dados["meses_decorridos"], dados["meses_restantes"]) == (3, 21)
    assert dados["plano"]["aporte_mensal"] == 2570.24
    assert dados["ultimo_status"] == "folga"
    assert [h["anomes"] for h in dados["historico"]] == [202507, 202508, 202509]
    assert result["fonte"]["periodo"] == {"inicio": 202507, "fim": 202509}


async def test_status_without_plan() -> None:
    result = await status_plano(tool_context(plan_state(plano_id=None)))
    assert _code(result) == "SEM_PLANO_ATIVO"


# --- envelopes ----------------------------------------------------------------


@pytest.mark.usefixtures("no_governance")
async def test_envelopes_never_leak_sql_project_or_future_periods() -> None:
    ctx = tool_context(plan_state())
    responses = [await avancar_mes(ctx)]
    ctx.state["consentimentos"] = CONSENT
    responses.append(await ajustar_plano(ctx, rota="B"))
    for _ in range(6):
        responses.append(await avancar_mes(ctx))
        responses.append(await status_plano(ctx))
    assert _code(responses[-2]) == "FIM_DO_REPLAY"

    text = json.dumps(responses, ensure_ascii=False).lower()
    for forbidden in ("select ", "batalha-time", "bussola_app.", "traceback"):
        assert forbidden not in text
    for envelope in responses:
        period = (envelope.get("fonte") or {}).get("periodo") or {}
        assert period.get("fim", 0) <= 202512
        for route in (envelope.get("dados") or {}).get("rotas", []):
            assert route["simulacao"]["fonte"]["periodo"]["fim"] <= envelope["dados"]["anomes"]


# --- contrato com o front (specs/008-front-web/contracts/eventos-agente.md §3) ---

FRONT_ADVANCE_KEYS = {
    "anomes",
    "planejado",
    "realizado",
    "desvio",
    "tolerancia",
    "status",
    "categoria_desvio",
    "acumulado",
    "percentual",
    "restante",
    "meses_decorridos",
    "meses_restantes",
    "resumo_mes",
    "rotas",
}
FRONT_STATUS_KEYS = {
    "objetivo",
    "plano",
    "meses_decorridos",
    "acumulado",
    "percentual",
    "ultimo_status",
    "historico",
}


async def test_envelopes_carry_every_field_the_front_reads() -> None:
    result, ctx = await _advanced()
    dados = result["dados"]
    assert FRONT_ADVANCE_KEYS <= set(dados)
    assert set(dados["categoria_desvio"]) == {"macro", "valor_mes", "media_base", "aumento"}
    assert set(dados["resumo_mes"]) == {"dados", "fonte", "avisos"}
    for route in dados["rotas"]:
        assert {"id", "titulo", "descricao", "simulacao"} <= set(route)
        assert {"dados", "fonte", "avisos"} <= set(route["simulacao"])
    status = await status_plano(ctx)
    assert FRONT_STATUS_KEYS <= set(status["dados"])
