"""Chaves e helpers de ``session.state`` (contratos §6).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``.

Os helpers aceitam qualquer objeto com ``get``/``__getitem__``/``__setitem__``
(``dict`` ou o ``State`` do ADK). As escritas sempre **reatribuem** a chave,
em vez de alterar listas ou dicts no lugar: o ``State`` do ADK só registra o
delta da sessão em ``__setitem__``.
"""

import re
from collections.abc import Mapping, MutableMapping
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Chaves (contratos §6)
# ---------------------------------------------------------------------------

CHAVE_ID_USUARIO = "id_usuario"
CHAVE_ATE_ANOMES = "ate_anomes"
CHAVE_ESTADO_JORNADA = "estado_jornada"
CHAVE_OBJETIVO = "objetivo"
CHAVE_CENARIOS = "cenarios"
CHAVE_CENARIO_ESCOLHIDO = "cenario_escolhido"
CHAVE_ULTIMAS_FONTES = "ultimas_fontes"
CHAVE_CONSENTIMENTOS = "consentimentos"
CHAVE_PLANO_ID = "plano_id"
CHAVE_ACOMPANHAMENTO = "acompanhamento"
CHAVE_MARCOS = "marcos"

CHAVES: tuple[str, ...] = (
    CHAVE_ID_USUARIO,
    CHAVE_ATE_ANOMES,
    CHAVE_ESTADO_JORNADA,
    CHAVE_OBJETIVO,
    CHAVE_CENARIOS,
    CHAVE_CENARIO_ESCOLHIDO,
    CHAVE_ULTIMAS_FONTES,
    CHAVE_CONSENTIMENTOS,
    CHAVE_PLANO_ID,
    CHAVE_ACOMPANHAMENTO,
    CHAVE_MARCOS,
)

# Limite de fontes guardadas em ``ultimas_fontes`` (as mais recentes ficam).
MAX_ULTIMAS_FONTES = 20

# Mesmos valores de ``bussola_mcp.contratos`` (o agente não depende do MCP).
ANOMES_MIN = 202501
ANOMES_MAX = 202512
UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class EstadoJornada(StrEnum):
    OBJETIVO = "OBJETIVO"
    ENTENDER = "ENTENDER"
    ANTECIPAR = "ANTECIPAR"
    ORIENTAR = "ORIENTAR"
    AGIR = "AGIR"
    ACOMPANHAR = "ACOMPANHAR"


# ---------------------------------------------------------------------------
# Validação (sem eco de valores nas mensagens)
# ---------------------------------------------------------------------------


def id_usuario_valido(valor: object) -> bool:
    """True se ``valor`` é uma string UUID v4 (sem diferenciar maiúsculas)."""
    return isinstance(valor, str) and UUID_V4_RE.fullmatch(valor) is not None


def anomes_valido(valor: object) -> bool:
    """True se ``valor`` é um inteiro ``AAAAMM`` entre 202501 e 202512."""
    return (
        isinstance(valor, int) and not isinstance(valor, bool) and ANOMES_MIN <= valor <= ANOMES_MAX
    )


def _validar_id_usuario(valor: object) -> str:
    if not id_usuario_valido(valor):
        raise ValueError("id_usuario ausente ou inválido: deve ser um UUID v4.")
    return str(valor).lower()


def _validar_ate_anomes(valor: object) -> int:
    if not anomes_valido(valor):
        raise ValueError("ate_anomes ausente ou inválido: deve estar entre 202501 e 202512.")
    return int(valor)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Estado inicial e helpers
# ---------------------------------------------------------------------------


def estado_inicial(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
    """Estado inicial da sessão: jornada em ``OBJETIVO``, listas vazias e ``None`` nos opcionais.

    ``id_usuario`` é validado como UUID v4 (e normalizado para minúsculas) e
    ``ate_anomes`` precisa estar entre 202501 e 202512. Levanta ``ValueError``.
    """
    return {
        CHAVE_ID_USUARIO: _validar_id_usuario(id_usuario),
        CHAVE_ATE_ANOMES: _validar_ate_anomes(ate_anomes),
        CHAVE_ESTADO_JORNADA: EstadoJornada.OBJETIVO.value,
        CHAVE_OBJETIVO: None,
        CHAVE_CENARIOS: None,
        CHAVE_CENARIO_ESCOLHIDO: None,
        CHAVE_ULTIMAS_FONTES: [],
        CHAVE_CONSENTIMENTOS: {},
        CHAVE_PLANO_ID: None,
        CHAVE_ACOMPANHAMENTO: [],
        CHAVE_MARCOS: None,
    }


def obter_id_usuario(state: Mapping[str, Any]) -> str:
    """``id_usuario`` do state. Levanta ``ValueError`` se ausente ou fora do formato UUID v4."""
    return _validar_id_usuario(state.get(CHAVE_ID_USUARIO))


def obter_ate_anomes(state: Mapping[str, Any]) -> int:
    """``ate_anomes`` do state. Levanta ``ValueError`` se ausente ou fora de 202501–202512."""
    return _validar_ate_anomes(state.get(CHAVE_ATE_ANOMES))


def obter_estado_jornada(state: Mapping[str, Any]) -> EstadoJornada:
    """Estado da jornada; ``OBJETIVO`` quando a chave ainda não existe.

    Um valor desconhecido levanta ``ValueError``.
    """
    valor = state.get(CHAVE_ESTADO_JORNADA)
    if valor is None:
        return EstadoJornada.OBJETIVO
    try:
        return EstadoJornada(valor)
    except ValueError:
        raise ValueError("estado_jornada inválido no session.state.") from None


def definir_estado_jornada(state: MutableMapping[str, Any], estado: EstadoJornada | str) -> None:
    """Grava o estado da jornada (como ``str``). Um valor desconhecido levanta ``ValueError``."""
    try:
        valor = EstadoJornada(estado)
    except ValueError:
        raise ValueError("estado_jornada inválido.") from None
    state[CHAVE_ESTADO_JORNADA] = valor.value


def adicionar_fonte(
    state: MutableMapping[str, Any],
    fonte: Mapping[str, Any],
    limite: int = MAX_ULTIMAS_FONTES,
) -> None:
    """Acrescenta ``fonte`` (envelope §5) a ``ultimas_fontes``, guardando só as ``limite`` últimas.

    A lista é reatribuída (não alterada no lugar), para o ADK registrar o delta.
    """
    if not isinstance(fonte, Mapping):
        raise TypeError("fonte deve ser um dicionário.")
    atuais = state.get(CHAVE_ULTIMAS_FONTES) or []
    novas = [*list(atuais), dict(fonte)]
    state[CHAVE_ULTIMAS_FONTES] = novas[-limite:] if limite > 0 else []
