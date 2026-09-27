"""Simulated sensitive actions of the AGIR state (ciclo §3.3).

All are registered with ``sensivel=True``: the gate (``before_tool`` 20) only
lets them run with an unused ``aceito`` consent. None has an external effect
besides writing to ``bussola_app`` through the registry. They never raise:
failures come back as ``{erro: {codigo, mensagem}}``.

Numbers come from the session (``objetivo``, ``cenarios`` and tool results),
never from the model's arguments: the model only names the scenario, the
frequency or the product id.
"""

import asyncio
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from google.adk.tools.tool_context import ToolContext

from bussola_agent.estado import (
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_CENARIOS,
    CHAVE_OBJETIVO,
    CHAVE_PLANO_ID,
    CHAVE_ULTIMAS_FONTES,
    obter_ate_anomes,
    obter_id_usuario,
)
from bussola_agent.governanca import catalogo, envelope, services
from bussola_agent.governanca.audit import record_event, session_id_of
from bussola_agent.governanca.consent import MSG_NOT_ALLOWED
from bussola_agent.governanca.text import collapse_spaces, normalize
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import Plano, TipoEvento

PLANS_TABLE = "bussola_app.planos"
SCENARIOS: tuple[str, ...] = ("conservador", "equilibrado", "acelerado")
OTHER_SCENARIO = "outro"
FREQUENCIES: tuple[str, ...] = ("mensal", "quinzenal", "semanal")
MAX_GOAL_TEXT = 80

NEXT_STEPS: tuple[dict[str, str], ...] = (
    {"texto": "Separar o aporte no início de cada mês, logo depois de receber."},
    {"texto": "Montar uma reserva de emergência antes de acelerar (sugestão)."},
    {"texto": "Ativar lembretes mensais", "acao": "ativar_lembretes"},
    {"texto": "Simular um financiamento", "acao": "simular_contratacao"},
)

MSG_NO_SCOPE = "A sessão está sem cliente ou mês válido. Recomece a conversa."
MSG_PLAN_ACTIVE = (
    "Já existe um plano ativo nesta conversa. Para mudar valor ou prazo, ajuste o plano."
)
MSG_NO_GOAL = "Registre o objetivo, com valor e prazo, antes de criar o plano."
MSG_UNKNOWN_SCENARIO = "Cenário desconhecido. Use conservador, equilibrado, acelerado ou outro."
MSG_NO_NUMBERS = "Não encontrei os números desse caminho. Compare os cenários de novo."
MSG_SAVE_FAILED = "Não consegui registrar o plano agora e nada foi criado. Tente de novo."
MSG_BAD_FREQUENCY = "Frequência inválida. Use mensal, quinzenal ou semanal."
MSG_NOT_IN_CATALOG = (
    "Esse produto não está no catálogo de simulações. Posso simular só os produtos do catálogo."
)
MSG_REMINDERS_OK = "Lembretes ativados. Vou te avisar uma vez por mês, no dia do seu aporte."
MSG_REMINDERS_OK_BY_FREQUENCY = {
    "mensal": MSG_REMINDERS_OK,
    "quinzenal": "Lembretes ativados. Vou te avisar a cada 15 dias, sem envio real nesta "
    "demonstração.",
    "semanal": "Lembretes ativados. Vou te avisar uma vez por semana, sem envio real nesta "
    "demonstração.",
}
MSG_SIMULATION_OK = (
    "Registrei uma simulação genérica, sem taxas, só como referência. Nada foi contratado e "
    "nenhuma análise de crédito foi feita."
)
SIMULATION_WARNING = "simulação, sem contratação e sem análise de crédito"

_log = obter_logger(__name__)


# ---------------------------------------------------------------------------
# Reading the session
# ---------------------------------------------------------------------------


def normalize_scenario(name: object) -> str | None:
    """``"Caminho Acelerado"`` → ``"acelerado"``; unknown → ``None``."""
    if not isinstance(name, str):
        return None
    folded = normalize(name).strip(" .!?")
    for prefix in ("o caminho ", "caminho ", "cenario ", "o "):
        if folded.startswith(prefix):
            folded = folded[len(prefix) :].strip()
    if folded in SCENARIOS or folded == OTHER_SCENARIO:
        return folded
    if folded in ("outro caminho", "personalizado"):
        return OTHER_SCENARIO
    return None


def success_data(response: Any) -> dict[str, Any] | None:
    """``dados`` of a successful envelope, also inside the MCP wrappers."""
    if not isinstance(response, Mapping) or envelope.error_code(response):
        return None
    dados = response.get("dados")
    if isinstance(dados, Mapping):
        return dict(dados)
    for key in ("structuredContent", "result"):
        nested = success_data(response.get(key))
        if nested is not None:
            return nested
    content = response.get("content")
    for part in content if isinstance(content, list) else ():
        if isinstance(part, Mapping) and part.get("type") == "text":
            try:
                nested = success_data(json.loads(part.get("text") or ""))
            except ValueError:
                continue
            if nested is not None:
                return nested
    return None


def latest_success(events: Iterable[Any], tool_name: str) -> dict[str, Any] | None:
    """``dados`` of the latest successful call of ``tool_name`` in the session."""
    latest = None
    for event in events:
        parts = getattr(getattr(event, "content", None), "parts", None) or []
        for part in parts:
            response = getattr(part, "function_response", None)
            if response is not None and response.name == tool_name:
                data = success_data(response.response)
                if data is not None:
                    latest = data
    return latest


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or value != value:
        return None
    return float(value)


def scenario_numbers(
    state: Mapping[str, Any], events: Iterable[Any], name: str
) -> dict[str, float | int] | None:
    """``valor_alvo``, ``aporte_mensal`` and ``prazo_meses`` of the chosen path."""
    goal = state.get(CHAVE_OBJETIVO)
    goal = goal if isinstance(goal, Mapping) else {}
    if name == OTHER_SCENARIO:
        events = list(events)
        source = latest_success(events, "escolher_cenario")
        details = source.get("detalhes") if source and source.get("cenario") == name else None
        if not isinstance(details, Mapping):
            details = latest_success(events, "simular_objetivo") or {}
    else:
        scenarios = state.get(CHAVE_CENARIOS)
        items = scenarios.get("cenarios") if isinstance(scenarios, Mapping) else None
        details = next(
            (
                item
                for item in (items if isinstance(items, list) else ())
                if isinstance(item, Mapping) and item.get("nome") == name
            ),
            {},
        )
    target = _number(details.get("valor_alvo")) or _number(goal.get("valor_alvo"))
    monthly = _number(details.get("aporte_mensal"))
    months = _number(details.get("prazo_meses"))
    if target is None or target <= 0 or monthly is None or monthly < 0 or months is None:
        return None
    if months != int(months) or not 1 <= months <= 360:
        return None
    return {
        "valor_alvo": round(target, 2),
        "aporte_mensal": round(monthly, 2),
        "prazo_meses": int(months),
    }


def goal_text(state: Mapping[str, Any]) -> str | None:
    goal = state.get(CHAVE_OBJETIVO)
    if not isinstance(goal, Mapping):
        return None
    for key in ("descricao", "tipo"):
        value = goal.get(key)
        if isinstance(value, str) and collapse_spaces(value):
            text = re.sub(r"[{}<>\[\]`]", "", collapse_spaces(value))
            return text[:MAX_GOAL_TEXT].rstrip() or None
    return None


def plan_period(state: Mapping[str, Any], ate_anomes: int) -> dict[str, Any]:
    """Period of the latest ``comparar_cenarios`` source, or ``ate_anomes``."""
    sources = state.get(CHAVE_ULTIMAS_FONTES)
    for source in reversed(sources if isinstance(sources, list) else []):
        if isinstance(source, Mapping) and source.get("ferramenta") == "comparar_cenarios":
            period = source.get("periodo")
            if isinstance(period, Mapping) and period.get("fim"):
                return dict(period)
    return {"inicio": ate_anomes, "fim": ate_anomes}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def criar_plano(cenario: str, tool_context: ToolContext) -> dict:
    """Cria o plano do cliente com o caminho escolhido. Ação sensível.

    Só funciona depois que o cliente autorizou com sim (solicitar_consentimento).
    Os valores vêm da comparação de cenários, não dos argumentos.

    Args:
        cenario: conservador, equilibrado, acelerado ou outro.

    Returns:
        Envelope com plano_id, cenario, valor_alvo, aporte_mensal,
        prazo_meses, criado_em_anomes e proximos_passos, ou erro.
    """
    state = tool_context.state
    try:
        id_usuario = obter_id_usuario(state)
        ate_anomes = obter_ate_anomes(state)
    except ValueError:
        return envelope.error(envelope.INVALID_INPUT, MSG_NO_SCOPE)
    if state.get(CHAVE_PLANO_ID):
        return envelope.error(envelope.INVALID_INPUT, MSG_PLAN_ACTIVE)
    objective = goal_text(state)
    if objective is None:
        return envelope.error(envelope.INVALID_INPUT, MSG_NO_GOAL)
    name = normalize_scenario(cenario) or normalize_scenario(state.get(CHAVE_CENARIO_ESCOLHIDO))
    if name is None:
        return envelope.error(envelope.INVALID_INPUT, MSG_UNKNOWN_SCENARIO)
    session = getattr(tool_context, "session", None)
    numbers = scenario_numbers(state, getattr(session, "events", None) or [], name)
    if numbers is None:
        return envelope.error(envelope.INVALID_INPUT, MSG_NO_NUMBERS)

    session_id = session_id_of(tool_context) or "desconhecida"
    plan = Plano(
        session_id=session_id,
        id_usuario=id_usuario,
        objetivo=objective,
        cenario=name,
        ate_anomes=ate_anomes,
        criado_em=services.get_clock().now(),
        **numbers,
    )
    try:
        await asyncio.to_thread(services.get_registry().registrar_plano, plan)
    except Exception as exc:
        _log.error(
            "Falha ao registrar o plano.",
            extra={
                "evento": "plano_criado",
                "ferramenta": "criar_plano",
                "session_id": session_id,
                "erro_codigo": envelope.UNAVAILABLE,
            },
            exc_info=exc,
        )
        return envelope.error(envelope.UNAVAILABLE, MSG_SAVE_FAILED)

    state[CHAVE_PLANO_ID] = plan.plano_id
    await record_event(
        tool_context,
        TipoEvento.PLANO_CRIADO,
        {"plano_id": plan.plano_id, "cenario": name, "ate_anomes": ate_anomes, **numbers},
        ferramenta="criar_plano",
    )
    _log.info(
        "Plano criado.",
        extra={
            "evento": "plano_criado",
            "ferramenta": "criar_plano",
            "session_id": session_id,
            "ate_anomes": ate_anomes,
        },
    )
    return envelope.ok(
        {
            "plano_id": plan.plano_id,
            "cenario": name,
            **numbers,
            "criado_em_anomes": ate_anomes,
            "proximos_passos": [dict(step) for step in NEXT_STEPS],
        },
        ferramenta="criar_plano",
        tabelas=(PLANS_TABLE,),
        ate_anomes=ate_anomes,
        periodo=plan_period(state, ate_anomes),
    )


async def ativar_lembretes(frequencia: str, tool_context: ToolContext) -> dict:
    """Ativa lembretes do plano (simulado, sem envio real). Ação sensível.

    Só funciona depois que o cliente autorizou com sim (solicitar_consentimento).

    Args:
        frequencia: mensal, quinzenal ou semanal.

    Returns:
        Envelope com acao, status e mensagem, ou erro.
    """
    value = normalize(frequencia) if isinstance(frequencia, str) else ""
    value = value or "mensal"
    if value not in FREQUENCIES:
        return envelope.error(envelope.INVALID_INPUT, MSG_BAD_FREQUENCY)
    await record_event(
        tool_context,
        TipoEvento.ACAO_EXECUTADA,
        {"acao": "ativar_lembretes", "frequencia": value, "simulada": True},
        ferramenta="ativar_lembretes",
    )
    _log.info(
        "Lembretes ativados (simulado).",
        extra={
            "evento": "acao_executada",
            "ferramenta": "ativar_lembretes",
            "session_id": session_id_of(tool_context),
        },
    )
    return envelope.ok(
        {
            "acao": "ativar_lembretes",
            "status": "ok",
            "frequencia": value,
            "mensagem": MSG_REMINDERS_OK_BY_FREQUENCY[value],
        },
        ferramenta="ativar_lembretes",
        tabelas=(),
        ate_anomes=None,
        avisos=("Simulação: nenhum lembrete é enviado de verdade.",),
    )


async def simular_contratacao(tipo_produto: str, tool_context: ToolContext) -> dict:
    """Simula a contratação de um produto do catálogo, sem contratar. Ação sensível.

    Só funciona depois que o cliente autorizou com sim (solicitar_consentimento).
    Aceita só produto_id do catálogo com simulação disponível: cofrinhos,
    controle_gastos, credito_imobiliario, consorcio_imoveis, consorcio_veiculos
    ou renegociacao. Não traz taxas nem condições.

    Args:
        tipo_produto: produto_id do catálogo.

    Returns:
        Envelope com acao, status, mensagem, nome, uso, cuidado e
        fonte_oficial, ou erro PRODUTO_FORA_DO_CATALOGO.
    """
    product = catalogo.simulable_product(tipo_produto)
    if product is None:
        _log.info(
            "Produto fora do catálogo de simulação.",
            extra={
                "evento": "acao_recusada",
                "ferramenta": "simular_contratacao",
                "session_id": session_id_of(tool_context),
                "erro_codigo": envelope.PRODUCT_NOT_IN_CATALOG,
            },
        )
        return envelope.error(envelope.PRODUCT_NOT_IN_CATALOG, MSG_NOT_IN_CATALOG)
    await record_event(
        tool_context,
        TipoEvento.ACAO_EXECUTADA,
        {"acao": "simular_contratacao", "produto_id": product.produto_id, "simulada": True},
        ferramenta="simular_contratacao",
    )
    _log.info(
        "Contratação simulada.",
        extra={
            "evento": "acao_executada",
            "ferramenta": "simular_contratacao",
            "session_id": session_id_of(tool_context),
        },
    )
    return envelope.ok(
        {
            "acao": "simular_contratacao",
            "status": "ok",
            "mensagem": MSG_SIMULATION_OK,
            "produto_id": product.produto_id,
            "nome": product.nome,
            "uso": product.uso,
            "cuidado": product.cuidado,
            "fonte_oficial": product.fonte_oficial,
        },
        ferramenta="simular_contratacao",
        tabelas=(),
        ate_anomes=None,
        avisos=(SIMULATION_WARNING,),
    )


async def compartilhar_dados(destino: str, tool_context: ToolContext) -> dict:
    """Compartilhar dados do cliente com terceiros. Sempre recusada na PoC.

    Args:
        destino: com quem compartilhar.

    Returns:
        Sempre erro NAO_PERMITIDO.
    """
    await record_event(
        tool_context,
        TipoEvento.GUARDRAIL_BLOQUEIO,
        {"motivo": "compartilhar_dados", "etapa": "acao"},
        ferramenta="compartilhar_dados",
    )
    return envelope.error(envelope.NOT_ALLOWED, MSG_NOT_ALLOWED)
