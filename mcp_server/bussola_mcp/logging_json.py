"""Logs estruturados em JSON (contratos §9, FR-011).

Uma linha JSON por evento em stdout, compatível com o Cloud Logging
(``severity``, ``message``). O formatador usa uma **lista de permitidos**
(research R-14): além de ``severity``, ``message``, ``servico`` e
``timestamp``, só saem os extras de §9 e o ``id_usuario`` sintético. Qualquer
outro extra é descartado. Uma exceção vira só ``excecao`` com o nome da classe,
sem mensagem nem traceback.

Uso::

    configurar_logging("bussola-mcp")
    logging.getLogger(__name__).info(
        "ferramenta executada", extra={"ferramenta": "perfil_financeiro", "latencia_ms": 12}
    )
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, TextIO

from bussola_mcp import config

CAMPOS_EXTRAS_PERMITIDOS: tuple[str, ...] = (
    "session_id",
    "estado_jornada",
    "ferramenta",
    "evento",
    "consentimento",
    "ate_anomes",
    "latencia_ms",
    "erro_codigo",
    "id_usuario",
)

NIVEL_PADRAO = config.NIVEL_LOG_PADRAO
"""Nível usado quando ``LOG_LEVEL`` está ausente ou não é um nível conhecido."""


class JsonFormatter(logging.Formatter):
    """Formata cada registro como uma linha JSON só com os campos permitidos."""

    def __init__(self, servico: str) -> None:
        super().__init__()
        self.servico = servico

    def format(self, record: logging.LogRecord) -> str:
        instante = datetime.fromtimestamp(record.created, tz=UTC)
        linha: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "servico": self.servico,
            "timestamp": instante.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }
        for campo in CAMPOS_EXTRAS_PERMITIDOS:
            valor = getattr(record, campo, None)
            if valor is not None:
                linha[campo] = valor
        if record.exc_info and record.exc_info[0] is not None:
            linha["excecao"] = record.exc_info[0].__name__
        return json.dumps(linha, ensure_ascii=False, default=str)


class _HandlerBussola(logging.StreamHandler):
    """Marca o handler instalado por :func:`configurar_logging` (idempotência)."""


def configurar_logging(servico: str, fluxo: TextIO | None = None) -> logging.Logger:
    """Instala o :class:`JsonFormatter` no logger raiz, com o nível de ``LOG_LEVEL``.

    O nível vem de :func:`bussola_mcp.config.nivel_log`; um valor desconhecido
    cai em :data:`NIVEL_PADRAO`.

    Pode ser chamada mais de uma vez: substitui o handler instalado antes, sem
    duplicar linhas. Devolve o logger raiz.
    """
    raiz = logging.getLogger()
    for handler in list(raiz.handlers):
        if isinstance(handler, _HandlerBussola):
            raiz.removeHandler(handler)
    handler = _HandlerBussola(fluxo if fluxo is not None else sys.stdout)
    handler.setFormatter(JsonFormatter(servico))
    raiz.addHandler(handler)
    nivel = config.nivel_log()
    if not isinstance(logging.getLevelName(nivel), int):
        nivel = NIVEL_PADRAO
    raiz.setLevel(nivel)
    return raiz
