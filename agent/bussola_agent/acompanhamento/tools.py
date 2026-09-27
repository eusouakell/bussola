"""Ferramentas ADK do ACOMPANHAR: ``avancar_mes``, ``status_plano`` e ``ajustar_plano``.

As três leem o escopo (``id_usuario`` e ``ate_anomes``) só do
``session.state``; o modelo não escolhe argumentos de escopo. Os números vêm
de ``resumo_mes`` e ``simular_objetivo`` (MCP) e das funções puras de
``desvio``, ``progress`` e ``routes``. O retorno segue o envelope §5 no
formato que o front exibe (``web/src/simulado/locais.ts``).
"""

import asyncio
import math
from collections.abc import Mapping
from typing import Any

from google.adk.tools import ToolContext

from bussola_agent.acompanhamento import envelopes, ports
from bussola_agent.acompanhamento.audit import record_event, record_follow_up, suggested_action
from bussola_agent.acompanhamento.desvio import (
    STATUS_DEVIATION,
    baseline_by_macro,
    compute_deviation,
    deviation_category,
)
from bussola_agent.acompanhamento.money import format_brl, format_months, money
from bussola_agent.acompanhamento.periods import month_range, next_month
from bussola_agent.acompanhamento.plan_context import (
    ActivePlan,
    history_for,
    lineage,
    read_context,
    resolve_active_plan,
    write_context,
)
from bussola_agent.acompanhamento.progress import compute_progress
from bussola_agent.acompanhamento.routes import build_routes
from bussola_agent.estado import (
    ANOMES_MAX,
    ANOMES_MIN,
    CHAVE_ACOMPANHAMENTO,
    CHAVE_ATE_ANOMES,
    CHAVE_CONSENTIMENTOS,
    CHAVE_ID_USUARIO,
    CHAVE_OBJETIVO,
    CHAVE_PLANO_ID,
    EstadoJornada,
    definir_estado_jornada,
    obter_ate_anomes,
    obter_id_usuario,
)
from bussola_agent.mcp_conexao import MSG_ESCOPO_INVALIDO
from bussola_agent.persistencia import Plano, TipoEvento

TOOL_ADVANCE = "avancar_mes"
TOOL_STATUS = "status_plano"
TOOL_ADJUST = "ajustar_plano"

GOVERNANCE_PACKAGE = "bussola_agent.governanca"
"""Nome do pacote do 005. Só o arnês de teste/eval usa, para compor a jornada
com ou sem governança; a guarda de consentimento **não** olha ``sys.modules``."""

ERROR_NO_DATA = "DADOS_INSUFICIENTES"
_EPSILON = 0.005

WARNING_ADJUSTMENT = "Ajuste simulado: nenhum dinheiro foi movido e nenhum produto foi contratado."


# ---------------------------------------------------------------------------
# Apoio
# ---------------------------------------------------------------------------


def _scope(state: Mapping[str, Any]) -> tuple[str, int] | None:
    try:
        return obter_id_usuario(state), obter_ate_anomes(state)
    except ValueError:
        return None


def _session_id(tool_context: Any) -> str:
    session = getattr(tool_context, "session", None)
    value = getattr(session, "id", None)
    return value if isinstance(value, str) and value else "desconhecida"


def _finite(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def _scoped_state(user_id: str, cut: int) -> dict[str, Any]:
    """State mínimo que o gateway recebe (só as chaves de escopo)."""
    return {CHAVE_ID_USUARIO: user_id, CHAVE_ATE_ANOMES: cut}


def _passthrough_error(envelope: Any) -> dict[str, Any]:
    """Erro §5 vindo do MCP, ou ``INDISPONIVEL`` se o envelope veio malformado."""
    if isinstance(envelope, Mapping) and isinstance(envelope.get("erro"), Mapping):
        err = envelope["erro"]
        code, message = err.get("codigo"), err.get("mensagem")
        if isinstance(code, str) and code and isinstance(message, str) and message:
            return envelopes.error(code, message)
    return envelopes.error(envelopes.ERROR_UNAVAILABLE, envelopes.MSG_UNAVAILABLE)


async def _baseline(
    gateway: ports.McpGateway, user_id: str, cut: int, start: int
) -> dict[str, float] | None:
    """Média por macro de 202501 até ``start`` (mês sem dados conta 0).

    Devolve ``None`` se algum mês falhar por outro motivo (a linha de base não
    é guardada e o mês sai sem categoria, com aviso).
    """
    months = month_range(ANOMES_MIN, start)
    scoped = _scoped_state(user_id, cut)
    results = await asyncio.gather(*(gateway.monthly_summary(m, scoped) for m in months))
    monthly: list[Any] = []
    for month, envelope in zip(months, results, strict=True):
        code = envelopes.error_code(envelope)
        if code == ERROR_NO_DATA:
            monthly.append(None)
            continue
        if code is not None or not envelopes.within_cut(envelope, cut):
            return None
        dados = envelope["dados"]
        if dados.get("anomes") != month:
            return None
        monthly.append(dados.get("gastos_macro"))
    return baseline_by_macro(monthly)


def _compact_route(route: Mapping[str, Any]) -> dict[str, Any]:
    simulation = route.get("simulacao")
    dados = simulation.get("dados") if isinstance(simulation, Mapping) else None
    viavel = dados.get("viavel") if isinstance(dados, Mapping) else None
    return {
        "id": route["id"],
        "aporte_mensal": route["aporte_mensal"],
        "prazo_meses": route["prazo_meses"],
        "prazo_total_meses": route["prazo_total_meses"],
        "viavel": viavel if isinstance(viavel, bool) else None,
    }


def _new_lineage(plan: ActivePlan) -> dict[str, Any]:
    return {
        "plano_inicial_id": plan.plano_id,
        "planos": [plan.plano_id],
        "inicio_anomes": plan.inicio_anomes,
        "linha_base": None,
        "plano_vigente": plan.snapshot(),
        "rotas": [],
        "rotas_anomes": None,
    }


# ---------------------------------------------------------------------------
# avancar_mes
# ---------------------------------------------------------------------------


async def avancar_mes(tool_context: ToolContext) -> dict[str, Any]:
    """Avança a simulação em um mês e compara o planejado com o realizado.

    Use quando o cliente pedir para avançar um mês (por exemplo, "avançar um
    mês" ou "próximo mês"). Não recebe argumentos: o mês e o cliente vêm da
    sessão. Devolve planejado, realizado, desvio, status, progresso da meta
    e, se houver desvio, a categoria e as rotas A e B recalculadas.
    """
    state = tool_context.state
    scope = _scope(state)
    if scope is None:
        return envelopes.error(envelopes.ERROR_INVALID_INPUT, MSG_ESCOPO_INVALIDO)
    user_id, cut = scope

    registry = ports.get_registry()
    plan = resolve_active_plan(state, registry)
    if plan is None:
        return envelopes.error(envelopes.ERROR_NO_ACTIVE_PLAN, envelopes.MSG_NO_ACTIVE_PLAN)
    if cut >= ANOMES_MAX:
        return envelopes.error(envelopes.ERROR_END_OF_REPLAY, envelopes.MSG_END_OF_REPLAY)

    gateway = ports.get_gateway()
    new_cut = next_month(cut)
    scoped = _scoped_state(user_id, new_cut)
    summary = await gateway.monthly_summary(new_cut, scoped)
    if envelopes.error_code(summary) is not None:
        return _passthrough_error(summary)
    month_data = summary["dados"]
    realized = _finite(month_data.get("sobra"))
    if (
        month_data.get("anomes") != new_cut
        or realized is None
        or not envelopes.within_cut(summary, new_cut)
    ):
        return envelopes.error(envelopes.ERROR_UNAVAILABLE, envelopes.MSG_UNAVAILABLE)

    # A partir daqui o mês está revelado: o novo corte vale para tudo.
    state[CHAVE_ATE_ANOMES] = new_cut

    context = read_context(state)
    if plan.plano_id not in lineage(context):
        context = _new_lineage(plan)
    start = int(context["inicio_anomes"])
    plan_ids = lineage(context)

    result = compute_deviation(plan.aporte_mensal, realized)
    history = history_for(state, plan_ids)
    progress = compute_progress(
        plan.valor_alvo,
        plan.prazo_meses,
        start,
        new_cut,
        [*(float(h.get("realizado", 0.0)) for h in history), result.actual],
    )

    warnings: list[str] = []
    category: dict[str, Any] | None = None
    routes: list[dict[str, Any]] = []
    if result.status == STATUS_DEVIATION:
        baseline = context.get("linha_base")
        if not isinstance(baseline, Mapping):
            baseline = await _baseline(gateway, user_id, new_cut, start)
            context["linha_base"] = baseline
        if baseline is None:
            warnings.append(envelopes.WARNING_CATEGORY_UNAVAILABLE)
        else:
            category = deviation_category(month_data.get("gastos_macro"), baseline)
        routes, route_warnings = await build_routes(
            gateway,
            scoped,
            remaining=progress.remaining,
            contribution=plan.aporte_mensal,
            months_remaining=progress.months_remaining,
            months_elapsed=progress.months_elapsed,
            cut=new_cut,
        )
        warnings.extend(route_warnings)

    item = {
        "plano_id": plan.plano_id,
        "anomes": new_cut,
        "planejado": result.planned,
        "realizado": result.actual,
        "desvio": result.deviation,
        "status": result.status,
        "categoria_desvio": category["macro"] if category else None,
    }

    session_id = _session_id(tool_context)
    estado = EstadoJornada.ACOMPANHAR
    record_event(
        registry,
        session_id=session_id,
        estado=estado,
        tipo=TipoEvento.ACOMPANHAMENTO_MES_AVANCADO,
        ferramenta=TOOL_ADVANCE,
        resumo={
            "plano_id": plan.plano_id,
            "anomes_anterior": cut,
            "anomes": new_cut,
            "status": result.status,
        },
    )
    if result.status == STATUS_DEVIATION:
        record_event(
            registry,
            session_id=session_id,
            estado=estado,
            tipo=TipoEvento.DESVIO_DETECTADO,
            ferramenta=TOOL_ADVANCE,
            resumo={
                "plano_id": plan.plano_id,
                "anomes": new_cut,
                **result.as_dict(),
                "categoria_desvio": item["categoria_desvio"],
            },
        )
        if routes:
            record_event(
                registry,
                session_id=session_id,
                estado=estado,
                tipo=TipoEvento.ROTA_RECALCULADA,
                ferramenta=TOOL_ADVANCE,
                resumo={
                    "plano_id": plan.plano_id,
                    "anomes": new_cut,
                    "rotas": [_compact_route(r) for r in routes],
                },
            )
    record_follow_up(
        registry,
        session_id=session_id,
        row={
            "plano_id": plan.plano_id,
            "anomes": new_cut,
            "planejado": result.planned,
            "realizado": result.actual,
            "desvio": result.deviation,
            "categoria_desvio": item["categoria_desvio"],
            "acao_sugerida": suggested_action(result.status, bool(routes)),
        },
    )

    definir_estado_jornada(state, estado)
    previous = state.get(CHAVE_ACOMPANHAMENTO)
    state[CHAVE_ACOMPANHAMENTO] = [*(previous if isinstance(previous, list) else []), item]
    context["plano_vigente"] = plan.snapshot()
    context["rotas"] = [_compact_route(r) for r in routes]
    context["rotas_anomes"] = new_cut if routes else None
    write_context(state, context)

    return {
        "dados": {
            "plano_id": plan.plano_id,
            "anomes": new_cut,
            **result.as_dict(),
            "categoria_desvio": category,
            "acumulado": progress.accumulated,
            "percentual": progress.percent,
            "restante": progress.remaining,
            "meses_decorridos": progress.months_elapsed,
            "meses_restantes": progress.months_remaining,
            "resumo_mes": {
                "dados": dict(month_data),
                "fonte": summary.get("fonte"),
                "avisos": envelopes.warnings_of(summary),
            },
            "rotas": routes,
        },
        "fonte": {
            "ferramenta": TOOL_ADVANCE,
            "tabelas": list((summary.get("fonte") or {}).get("tabelas") or []),
            "periodo": {"inicio": new_cut, "fim": new_cut},
        },
        "avisos": [envelopes.WARNING_REPLAY, *warnings],
    }


# ---------------------------------------------------------------------------
# status_plano
# ---------------------------------------------------------------------------


async def status_plano(tool_context: ToolContext) -> dict[str, Any]:
    """Resumo do plano ativo: meta, aporte, prazo, progresso e histórico mensal.

    Use quando o cliente pedir o status ou o resumo do plano (por exemplo,
    "Ver status do plano"). Não recebe argumentos e não avança o mês.
    """
    state = tool_context.state
    if _scope(state) is None:
        return envelopes.error(envelopes.ERROR_INVALID_INPUT, MSG_ESCOPO_INVALIDO)
    plan = resolve_active_plan(state, ports.get_registry())
    if plan is None:
        return envelopes.error(envelopes.ERROR_NO_ACTIVE_PLAN, envelopes.MSG_NO_ACTIVE_PLAN)

    context = read_context(state)
    plan_ids = lineage(context) if plan.plano_id in lineage(context) else [plan.plano_id]
    history = history_for(state, plan_ids)
    last = history[-1] if history else None
    progress = compute_progress(
        plan.valor_alvo,
        plan.prazo_meses,
        plan.inicio_anomes,
        last["anomes"] if last else None,
        [float(h.get("realizado", 0.0)) for h in history],
    )
    objetivo = state.get(CHAVE_OBJETIVO)
    return {
        "dados": {
            "objetivo": dict(objetivo)
            if isinstance(objetivo, Mapping)
            else {"descricao": plan.objetivo},
            "plano": plan.public(),
            "meses_decorridos": progress.months_elapsed,
            "meses_restantes": progress.months_remaining,
            "acumulado": progress.accumulated,
            "percentual": progress.percent,
            "restante": progress.remaining,
            "ultimo_status": last.get("status") if last else None,
            "historico": history,
        },
        "fonte": {
            "ferramenta": TOOL_STATUS,
            "tabelas": [],
            "periodo": (
                {"inicio": next_month(plan.inicio_anomes), "fim": last["anomes"]} if last else None
            ),
        },
        "avisos": [envelopes.WARNING_REPLAY],
    }


# ---------------------------------------------------------------------------
# ajustar_plano (sensível)
# ---------------------------------------------------------------------------


def _consent_accepted(state: Mapping[str, Any]) -> bool:
    """True se há consentimento ``aceito`` para ``ajustar_plano`` neste estado.

    Não olha ``usado``, de propósito: o gate do 005 (``before_tool`` 20) consome
    o consentimento **antes** da execução da ferramenta (contratos §6, campo
    ``usado``), mantendo ``status: aceito``. Exigir ``usado`` falso aqui
    rejeitaria o fluxo legítimo. Quem impede o replay é o gate; esta guarda só
    garante que nenhuma execução acontece sem um "sim" registrado, mesmo que o
    gate não esteja na cadeia.
    """
    consents = state.get(CHAVE_CONSENTIMENTOS)
    entry = consents.get(TOOL_ADJUST) if isinstance(consents, Mapping) else None
    if not isinstance(entry, Mapping):
        return False
    consent_id = entry.get("consent_id")
    return entry.get("status") == "aceito" and isinstance(consent_id, str) and bool(consent_id)


def _normalize_route_id(value: str) -> str:
    text = value.strip().upper()
    text = text.removeprefix("ROTA").strip()
    return text


def _matches_values(route: Mapping[str, Any], contribution: float | None, term: int | None) -> bool:
    if contribution is not None and abs(float(route["aporte_mensal"]) - money(contribution)) > (
        _EPSILON
    ):
        return False
    return term is None or term in (route["prazo_meses"], route["prazo_total_meses"])


def _select_route(
    routes: list[Mapping[str, Any]],
    rota: str | None,
    contribution: float | None,
    term: int | None,
) -> Mapping[str, Any] | dict[str, Any]:
    """A rota escolhida, ou um envelope de erro ``ENTRADA_INVALIDA``.

    - ``rota`` (A ou B) tem prioridade; valores informados junto precisam
      bater com ela (o modelo não inventa aporte nem prazo);
    - sem ``rota``, aporte e/ou prazo precisam apontar uma única rota;
    - sem nada, vale a rota única, se só houver uma.
    """
    if not routes:
        return envelopes.error(envelopes.ERROR_INVALID_INPUT, envelopes.MSG_NO_ROUTE)
    which = envelopes.error(envelopes.ERROR_INVALID_INPUT, envelopes.MSG_WHICH_ROUTE)
    if isinstance(rota, str) and rota.strip():
        wanted = _normalize_route_id(rota)
        found = [r for r in routes if str(r.get("id", "")).upper() == wanted]
        if len(found) != 1 or not _matches_values(found[0], contribution, term):
            return which
        return found[0]
    if contribution is not None or term is not None:
        found = [r for r in routes if _matches_values(r, contribution, term)]
        return found[0] if len(found) == 1 else which
    return routes[0] if len(routes) == 1 else which


async def ajustar_plano(
    tool_context: ToolContext,
    rota: str | None = None,
    aporte_mensal: float | None = None,
    prazo_meses: int | None = None,
) -> dict[str, Any]:
    """Adota a rota recalculada (A ou B) e grava um novo plano. Ação sensível.

    Só chame depois que o cliente aceitar o consentimento pedido com
    ``solicitar_consentimento(acao="ajustar_plano", ...)``. Informe ``rota``
    ("A" ou "B") como o cliente escolheu. Não informe valores que não vieram
    da rota: o aporte e o prazo são os da rota recalculada por ``avancar_mes``.
    """
    state = tool_context.state
    scope = _scope(state)
    if scope is None:
        return envelopes.error(envelopes.ERROR_INVALID_INPUT, MSG_ESCOPO_INVALIDO)
    user_id, cut = scope

    registry = ports.get_registry()
    plan = resolve_active_plan(state, registry)
    if plan is None:
        return envelopes.error(envelopes.ERROR_NO_ACTIVE_PLAN, envelopes.MSG_NO_ACTIVE_PLAN)

    # Ação sensível (contratos §6): sem "sim" registrado, não executa. A guarda
    # é incondicional; o gate do 005 (before_tool 20) é a primeira linha, esta é
    # a última, para o caso de o gate não estar na cadeia.
    if not _consent_accepted(state):
        return envelopes.error(envelopes.ERROR_CONSENT_REQUIRED, envelopes.MSG_CONSENT_REQUIRED)

    context = read_context(state)
    current = context.get("plano_vigente")
    raw_routes = context.get("rotas")
    routes = (
        [r for r in raw_routes if isinstance(r, Mapping)]
        if isinstance(raw_routes, list)
        and isinstance(current, Mapping)
        and current.get("plano_id") == plan.plano_id
        else []
    )
    selected = _select_route(routes, rota, aporte_mensal, prazo_meses)
    if "erro" in selected:
        return dict(selected)

    total_term = int(selected["prazo_total_meses"])
    contribution = money(selected["aporte_mensal"])
    try:
        new_plan = Plano(
            session_id=_session_id(tool_context),
            id_usuario=user_id,
            objetivo=plan.objetivo,
            valor_alvo=plan.valor_alvo,
            prazo_meses=total_term,
            cenario=plan.cenario,
            aporte_mensal=contribution,
            ate_anomes=cut,
        )
        registry.registrar_plano(new_plan)
    except Exception:  # registro indisponível: o plano atual continua valendo
        return envelopes.error(envelopes.ERROR_UNAVAILABLE, envelopes.MSG_UNAVAILABLE)

    record_event(
        registry,
        session_id=new_plan.session_id,
        estado=EstadoJornada.ACOMPANHAR,
        tipo=TipoEvento.PLANO_AJUSTADO,
        ferramenta=TOOL_ADJUST,
        resumo={
            "plano_id": new_plan.plano_id,
            "plano_anterior_id": plan.plano_id,
            "rota": selected["id"],
            "aporte_mensal": contribution,
            "prazo_meses": total_term,
            "anomes": cut,
        },
    )

    adjusted = ActivePlan(
        plano_id=new_plan.plano_id,
        cenario=plan.cenario,
        valor_alvo=plan.valor_alvo,
        aporte_mensal=contribution,
        prazo_meses=total_term,
        criado_em_anomes=cut,
        inicio_anomes=plan.inicio_anomes,
        objetivo=plan.objetivo,
    )
    if plan.plano_id not in lineage(context):
        context = _new_lineage(plan)
    context["planos"] = [*lineage(context), new_plan.plano_id]
    context["plano_vigente"] = adjusted.snapshot()
    context["rotas"] = []
    context["rotas_anomes"] = None
    state[CHAVE_PLANO_ID] = new_plan.plano_id
    definir_estado_jornada(state, EstadoJornada.ACOMPANHAR)
    write_context(state, context)

    remaining_term = int(selected["prazo_meses"])
    return {
        "dados": {
            "plano_id": new_plan.plano_id,
            "plano_anterior_id": plan.plano_id,
            "rota": selected["id"],
            "aporte_mensal": contribution,
            "prazo_meses": total_term,
            "prazo_restante_meses": remaining_term,
            "mensagem": (
                f"Plano ajustado: {format_brl(contribution)} por mês, "
                f"{format_months(remaining_term)} até a meta. Nenhum dinheiro foi movido."
            ),
        },
        "fonte": {"ferramenta": TOOL_ADJUST, "tabelas": [], "periodo": None},
        "avisos": [WARNING_ADJUSTMENT],
    }
