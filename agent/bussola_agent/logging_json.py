"""Logger JSON estruturado do agente (contratos §9; research R-14).

Uma linha JSON por evento em stdout, compatível com o Cloud Logging
(``severity``, ``message``). A saída usa uma **lista de campos permitidos**:

- sempre: ``severity``, ``message``, ``servico`` e ``timestamp``;
- extras aceitos: os campos de §9 (``session_id``, ``estado_jornada``,
  ``ferramenta``, ``evento``, ``consentimento``, ``ate_anomes``,
  ``latencia_ms``, ``erro_codigo``) e ``id_usuario`` (sintético);
- exceções: só ``excecao`` com o **nome da classe**, sem traceback nem
  mensagem.

Campos com valor ``None`` e qualquer outro extra são descartados. Nunca
passe prompt, texto de lançamentos, chaves ou tokens em ``message``.

Uso::

    from bussola_agent.logging_json import obter_logger

    log = obter_logger(__name__)
    log.info("Ferramenta chamada.", extra={"ferramenta": "perfil_financeiro"})
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import IO, Any

SERVICO = "bussola-agent"

# Namespace dos loggers do agente. O handler JSON fica neste logger (sem
# propagar para o root), para não reformatar logs de bibliotecas.
LOGGER_RAIZ = "bussola_agent"

CAMPOS_PERMITIDOS: tuple[str, ...] = (
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

_MARCA_HANDLER = "_bussola_json"


def _valor_json(valor: Any) -> Any:
    """Converte o valor de um campo permitido em algo serializável em JSON."""
    if valor is None or isinstance(valor, bool | int | float | str):
        return valor
    return str(valor)


class JsonFormatter(logging.Formatter):
    """Formata cada registro como uma linha JSON com a lista de campos permitidos."""

    def __init__(self, servico: str = SERVICO) -> None:
        super().__init__()
        self.servico = servico

    def format(self, record: logging.LogRecord) -> str:
        instante = datetime.fromtimestamp(record.created, UTC)
        saida: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "servico": self.servico,
            "timestamp": instante.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        }
        for campo in CAMPOS_PERMITIDOS:
            valor = record.__dict__.get(campo)
            if valor is not None:
                saida[campo] = _valor_json(valor)
        if record.exc_info and record.exc_info[0] is not None:
            saida["excecao"] = record.exc_info[0].__name__
        return json.dumps(saida, ensure_ascii=False)


class _SaidaPadraoHandler(logging.StreamHandler):
    """``StreamHandler`` que sempre escreve no ``sys.stdout`` atual.

    Resolver o stream a cada escrita evita apontar para um ``stdout`` trocado
    depois da configuração (por exemplo, pela captura do pytest).
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    @property  # type: ignore[override]
    def stream(self) -> IO[str]:
        return sys.stdout

    @stream.setter
    def stream(self, _valor: IO[str]) -> None:
        pass


def _nivel(nivel: str | int | None) -> int:
    if isinstance(nivel, int):
        return nivel
    nome = (nivel or os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    valor = logging.getLevelName(nome)
    return valor if isinstance(valor, int) else logging.INFO


def configurar_logging(
    nivel: str | int | None = None,
    servico: str = SERVICO,
    stream: IO[str] | None = None,
) -> logging.Logger:
    """Instala o handler JSON no logger ``bussola_agent`` (idempotente).

    - ``nivel``: nome ou número do nível; padrão ``LOG_LEVEL`` (``INFO``).
    - ``stream``: destino; padrão ``sys.stdout``.

    Uma nova chamada substitui o handler instalado antes, sem duplicar linhas.
    """
    logger = logging.getLogger(LOGGER_RAIZ)
    for handler in list(logger.handlers):
        if getattr(handler, _MARCA_HANDLER, False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler(stream) if stream is not None else _SaidaPadraoHandler()
    handler.setFormatter(JsonFormatter(servico))
    setattr(handler, _MARCA_HANDLER, True)
    logger.addHandler(handler)
    logger.setLevel(_nivel(nivel))
    logger.propagate = False
    return logger


def obter_logger(nome: str | None = None) -> logging.Logger:
    """Devolve um logger sob ``bussola_agent``, configurando o handler na primeira vez."""
    raiz = logging.getLogger(LOGGER_RAIZ)
    if not any(getattr(h, _MARCA_HANDLER, False) for h in raiz.handlers):
        configurar_logging()
    if not nome or nome == LOGGER_RAIZ:
        return raiz
    if nome.startswith(LOGGER_RAIZ + "."):
        return logging.getLogger(nome)
    return logging.getLogger(f"{LOGGER_RAIZ}.{nome}")
