"""Local journey tools exposed to the model (004 §3.3; spec FR-009, FR-010).

Both tools only validate and answer with the contract envelope (contratos §5).
They never write ``session.state``: the ``after_tool`` callback of
:mod:`bussola_agent.escopo` is the single writer of the journey, so a tool
result and the state never disagree.

Customer-facing messages are pt-BR and never echo the rejected value.
"""

import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

from bussola_agent.estado import (
    CHAVE_CENARIOS,
    CHAVE_OBJETIVO,
    CHAVE_PLANO_ID,
    EstadoJornada,
    obter_estado_jornada,
)
from bussola_agent.jornada.state_machine import (
    MAX_TARGET_MONTHS,
    OTHER_SCENARIO,
    SCENARIO_NAMES,
)
from bussola_agent.jornada.tool_results import success_data, tool_outcomes

REGISTER_GOAL = "registrar_objetivo"
CHOOSE_SCENARIO = "escolher_cenario"
SIMULATE_GOAL = "simular_objetivo"
LOCAL_TOOL_NAMES: tuple[str, ...] = (REGISTER_GOAL, CHOOSE_SCENARIO)

ERROR_INVALID_INPUT = "ENTRADA_INVALIDA"
ERROR_IMPLAUSIBLE_TERM = "PRAZO_IMPLAUSIVEL"

REQUIRED_GOAL_FIELDS: tuple[str, ...] = ("valor_alvo", "prazo_meses")
PRIORITIES: tuple[str, ...] = ("alta", "media", "baixa")
MAX_TEXT_LENGTH = 80
MAX_TYPE_LENGTH = 30
DEFAULT_GOAL_TYPE = "outro"

MSG_INVALID_VALUE = "valor_alvo deve ser um número maior que zero."
MSG_INVALID_TERM = "prazo_meses deve ser um número inteiro de meses entre 1 e 360."
MSG_PLAN_ACTIVE = (
    "Já existe um plano ativo para este objetivo. Para mudar valor ou prazo, ajuste o plano."
)
MSG_NO_SCENARIOS = "Compare os cenários com comparar_cenarios antes de escolher um caminho."
MSG_UNKNOWN_SCENARIO = "Cenário desconhecido. Use conservador, equilibrado, acelerado ou outro."
MSG_OTHER_NEEDS_SIMULATION = (
    "Para escolher outro caminho, simule antes com simular_objetivo o aporte ou prazo desejado."
)
MSG_WRONG_STAGE = "Só é possível escolher um caminho depois de comparar os cenários."

_UNSAFE_TEXT = re.compile(r"[{}<>\[\]\r\n\t`]+")
_SPACES = re.compile(r"\s+")
_THOUSANDS_ONLY = re.compile(r"\d{1,3}(?:\.\d{3})+")


def _envelope(tool: str, data: dict[str, Any], warnings: Iterable[str] = ()) -> dict[str, Any]:
    return {
        "dados": data,
        "fonte": {"ferramenta": tool, "tabelas": [], "periodo": None},
        "avisos": list(warnings),
    }


def _error(code: str, message: str) -> dict[str, Any]:
    return {"erro": {"codigo": code, "mensagem": message}}


def _fold(text: str) -> str:
    """Casefold without accents: ``"Média"`` → ``"media"``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def clean_text(value: object, limit: int = MAX_TEXT_LENGTH) -> str | None:
    """Single-line text without template or markup characters, capped at ``limit``."""
    if value is None:
        return None
    text = _SPACES.sub(" ", _UNSAFE_TEXT.sub(" ", str(value))).strip()
    return text[:limit].rstrip() or None


def parse_target_value(value: object) -> float | None:
    """``valor_alvo`` as BRL ``float`` with 2 decimals, or ``None`` when invalid.

    Accepts ``int``, ``float`` and numeric strings (``"60000"``, ``"60.000,00"``);
    rejects ``bool``, non-finite and non-positive values.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace("R$", "").replace(" ", "")
        if "," in text or _THOUSANDS_ONLY.fullmatch(text):
            text = text.replace(".", "").replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            return None
    if not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        return None
    return round(number, 2)


def parse_term_months(value: object) -> int | None:
    """``prazo_meses`` as ``int`` in 1–360, or ``None`` when invalid.

    Integral floats (``24.0``) and digit strings are accepted.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            return None
        value = int(text)
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    if not isinstance(value, int) or not 1 <= value <= MAX_TARGET_MONTHS:
        return None
    return value


def parse_priority(value: object) -> str | None:
    """``alta``, ``media`` or ``baixa``; anything else becomes ``None``."""
    text = clean_text(value, 20)
    if text is None:
        return None
    folded = _fold(text)
    return folded if folded in PRIORITIES else None


def missing_fields(goal: Mapping[str, Any]) -> list[str]:
    """Required fields still empty (spec D-01: priority is optional)."""
    return [field for field in REQUIRED_GOAL_FIELDS if goal.get(field) is None]


def _current_goal(tool_context: Any) -> dict[str, Any]:
    state = getattr(tool_context, "state", None)
    current = state.get(CHAVE_OBJETIVO) if state is not None else None
    return dict(current) if isinstance(current, Mapping) else {}


def registrar_objetivo(
    tipo: str,
    descricao: str,
    valor_alvo: float | None = None,
    prazo_meses: int | None = None,
    prioridade: str | None = None,
    tool_context: Any = None,
) -> dict[str, Any]:
    """Registra ou completa o objetivo financeiro do cliente.

    Chame assim que o cliente disser o objetivo, mesmo sem valor ou prazo, e
    de novo quando ele informar o que faltava. Campos omitidos mantêm o valor
    já registrado. Nunca pergunte a renda: ela vem dos dados.

    Args:
        tipo: categoria curta do objetivo, por exemplo imovel, veiculo,
            reserva, educacao, viagem ou outro.
        descricao: descrição curta nas palavras do cliente, por exemplo
            "Entrada do primeiro apartamento".
        valor_alvo: valor a juntar em reais, maior que zero. Omita se o
            cliente ainda não disse.
        prazo_meses: prazo em meses, inteiro de 1 a 360. Omita se o cliente
            ainda não disse.
        prioridade: alta, media ou baixa. Opcional.

    Returns:
        Envelope com dados.objetivo e dados.faltando (campos que ainda
        precisam ser perguntados), ou erro.
    """
    current = _current_goal(tool_context)
    goal: dict[str, Any] = {
        "tipo": clean_text(tipo, MAX_TYPE_LENGTH) or current.get("tipo") or DEFAULT_GOAL_TYPE,
        "descricao": clean_text(descricao) or current.get("descricao"),
        "valor_alvo": current.get("valor_alvo"),
        "prazo_meses": current.get("prazo_meses"),
        "prioridade": current.get("prioridade"),
    }
    warnings: list[str] = []

    if valor_alvo is not None:
        parsed_value = parse_target_value(valor_alvo)
        if parsed_value is None:
            return _error(ERROR_INVALID_INPUT, MSG_INVALID_VALUE)
        goal["valor_alvo"] = parsed_value
    if prazo_meses is not None:
        parsed_term = parse_term_months(prazo_meses)
        if parsed_term is None:
            return _error(ERROR_IMPLAUSIBLE_TERM, MSG_INVALID_TERM)
        goal["prazo_meses"] = parsed_term
    if prioridade is not None:
        parsed_priority = parse_priority(prioridade)
        if parsed_priority is None:
            warnings.append("Prioridade não reconhecida; use alta, media ou baixa.")
        else:
            goal["prioridade"] = parsed_priority

    state = getattr(tool_context, "state", None)
    plan_active = state is not None and state.get(CHAVE_PLANO_ID)
    changed = any(
        current.get(field) is not None and goal[field] != current.get(field)
        for field in REQUIRED_GOAL_FIELDS
    )
    if plan_active and changed:
        return _error(ERROR_INVALID_INPUT, MSG_PLAN_ACTIVE)

    return _envelope(REGISTER_GOAL, {"objetivo": goal, "faltando": missing_fields(goal)}, warnings)


def normalize_scenario_name(name: object) -> str | None:
    """``"Caminho Acelerado"`` → ``"acelerado"``; unknown names → ``None``."""
    if not isinstance(name, str):
        return None
    folded = _SPACES.sub(" ", _fold(name)).strip(" .!?")
    for prefix in ("o caminho ", "caminho ", "cenario ", "o "):
        if folded.startswith(prefix):
            folded = folded[len(prefix) :]
    folded = folded.strip()
    if folded in SCENARIO_NAMES or folded == OTHER_SCENARIO:
        return folded
    if folded in ("outro caminho", "personalizado"):
        return OTHER_SCENARIO
    return None


def latest_simulation(events: Iterable[Any]) -> dict[str, Any] | None:
    """``dados`` of the latest successful ``simular_objetivo`` in the session."""
    latest = None
    for outcome in tool_outcomes(events):
        if outcome.name == SIMULATE_GOAL:
            data = success_data(outcome.response)
            if data is not None:
                latest = data
    return latest


def _scenario_details(scenarios: object, name: str) -> dict[str, Any] | None:
    items = scenarios.get("cenarios") if isinstance(scenarios, Mapping) else None
    for item in items if isinstance(items, list) else ():
        if isinstance(item, Mapping) and item.get("nome") == name:
            return {
                key: item.get(key)
                for key in ("aporte_mensal", "prazo_meses", "viavel", "pct_capacidade")
            }
    return None


def _session_events(tool_context: Any) -> list[Any]:
    session = getattr(tool_context, "session", None)
    return list(getattr(session, "events", None) or [])


def escolher_cenario(nome: str, tool_context: Any = None) -> dict[str, Any]:
    """Registra o caminho escolhido pelo cliente depois da comparação de cenários.

    Use só quando o cliente escolher explicitamente um caminho. Para "outro",
    simule antes com simular_objetivo o aporte ou o prazo que o cliente pediu.

    Args:
        nome: conservador, equilibrado, acelerado ou outro.

    Returns:
        Envelope com dados.cenario e dados.detalhes (aporte, prazo e
        viabilidade vindos das ferramentas), ou erro.
    """
    state = getattr(tool_context, "state", None)
    if state is None:
        return _error(ERROR_INVALID_INPUT, MSG_NO_SCENARIOS)
    if state.get(CHAVE_PLANO_ID):
        return _error(ERROR_INVALID_INPUT, MSG_PLAN_ACTIVE)
    scenarios = state.get(CHAVE_CENARIOS)
    if not scenarios:
        return _error(ERROR_INVALID_INPUT, MSG_NO_SCENARIOS)
    try:
        stage = obter_estado_jornada(state)
    except ValueError:
        return _error(ERROR_INVALID_INPUT, MSG_WRONG_STAGE)
    if stage not in (EstadoJornada.ORIENTAR, EstadoJornada.AGIR):
        return _error(ERROR_INVALID_INPUT, MSG_WRONG_STAGE)

    chosen = normalize_scenario_name(nome)
    if chosen is None:
        return _error(ERROR_INVALID_INPUT, MSG_UNKNOWN_SCENARIO)
    if chosen == OTHER_SCENARIO:
        simulation = latest_simulation(_session_events(tool_context))
        if simulation is None:
            return _error(ERROR_INVALID_INPUT, MSG_OTHER_NEEDS_SIMULATION)
        details = {
            key: simulation.get(key)
            for key in ("valor_alvo", "aporte_mensal", "prazo_meses", "viavel", "modo")
        }
    else:
        details = _scenario_details(scenarios, chosen)
        if details is None:
            return _error(ERROR_INVALID_INPUT, MSG_UNKNOWN_SCENARIO)
    return _envelope(CHOOSE_SCENARIO, {"cenario": chosen, "detalhes": details})
