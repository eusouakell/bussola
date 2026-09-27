"""Tool runner: validation, error codes, envelope and log line (contratos §5 and §9).

Every tool goes through :meth:`ToolRunner.run`:

1. validates the arguments with the ``Entrada*`` model of the tool. A term
   (``prazo_meses``) outside 1–360 as the only problem → ``PRAZO_IMPLAUSIVEL``;
   anything else → ``ENTRADA_INVALIDA`` citing only field names;
2. unknown client → ``USUARIO_INEXISTENTE``;
3. calls the tool computation with the injected ports;
4. builds ``{dados, fonte, avisos}`` with ``fonte.tabelas`` from
   ``TABELAS_FERRAMENTA`` and the period actually considered;
5. ``DomainError`` → its code; ``BackendUnavailable`` or any other exception →
   ``INDISPONIVEL`` (detail only in the log, as the exception class name);
6. logs one ``ferramenta_chamada`` line with ``ferramenta``, ``latencia_ms``,
   ``erro_codigo`` and ``ate_anomes``. Never the question, texts or ids.

Business errors are tool results, never exceptions nor ``isError``.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from bussola_mcp.contratos import (
    FERRAMENTAS,
    TABELAS_FERRAMENTA,
    CodigoErro,
    EntradaComum,
    Fonte,
    Resposta,
    envelope_erro,
    mensagem_entrada_invalida,
)
from bussola_mcp.ferramentas.ports import (
    BackendUnavailable,
    Computation,
    DomainError,
    ToolDependencies,
)

logger = logging.getLogger("bussola_mcp.ferramentas")

type Compute = Callable[[ToolDependencies, Any], Computation]

TERM_FIELD = "prazo_meses"
_TERM_RANGE_ERRORS = frozenset({"greater_than_equal", "less_than_equal"})


def is_implausible_term(exc: ValidationError, argumentos: dict[str, Any]) -> bool:
    """True when the only problem is ``prazo_meses`` outside 1–360 (cycle §3.3).

    With ``aporte_mensal`` also given, the input breaks the "exactly one" rule
    and stays ``ENTRADA_INVALIDA`` (the model check runs only on valid fields).
    """
    if argumentos.get("aporte_mensal") is not None:
        return False
    errors = exc.errors(include_input=False, include_url=False)
    return bool(errors) and all(
        erro["type"] in _TERM_RANGE_ERRORS and tuple(erro["loc"]) == (TERM_FIELD,)
        for erro in errors
    )


class ToolRunner:
    """Runs a tool computation and returns the serialized envelope."""

    def __init__(self, deps: ToolDependencies) -> None:
        self.deps = deps

    def run(self, ferramenta: str, argumentos: dict[str, Any], compute: Compute) -> dict[str, Any]:
        """Success or error envelope of ``ferramenta``, with one log line."""
        inicio = time.perf_counter()
        entrada: EntradaComum | None = None
        try:
            entrada = FERRAMENTAS[ferramenta][0].model_validate(argumentos)
        except ValidationError as exc:
            if is_implausible_term(exc, argumentos):
                envelope = envelope_erro(CodigoErro.PRAZO_IMPLAUSIVEL)
            else:
                envelope = envelope_erro(
                    CodigoErro.ENTRADA_INVALIDA, mensagem_entrada_invalida(exc)
                )
        else:
            envelope = self._execute(ferramenta, entrada, compute)
        self._log(ferramenta, entrada, envelope, inicio)
        return envelope

    def _execute(self, ferramenta: str, entrada: EntradaComum, compute: Compute) -> dict[str, Any]:
        try:
            if not self.deps.repository.usuario_existe(entrada.id_usuario):
                return envelope_erro(CodigoErro.USUARIO_INEXISTENTE)
            computation = compute(self.deps, entrada)
            return self._envelope(ferramenta, computation)
        except DomainError as exc:
            return envelope_erro(exc.codigo, exc.mensagem)
        except BackendUnavailable as exc:
            logger.warning(
                "backend indisponível",
                exc_info=_cause_info(exc),
                extra={"evento": "backend_indisponivel", "ferramenta": ferramenta},
            )
            return envelope_erro(CodigoErro.INDISPONIVEL, exc.mensagem)
        except Exception:
            logger.exception(
                "falha inesperada na ferramenta",
                extra={"evento": "ferramenta_falhou", "ferramenta": ferramenta},
            )
            return envelope_erro(CodigoErro.INDISPONIVEL)

    @staticmethod
    def _envelope(ferramenta: str, computation: Computation) -> dict[str, Any]:
        dados_cls = FERRAMENTAS[ferramenta][1]
        fonte = Fonte(
            ferramenta=ferramenta,
            tabelas=list(TABELAS_FERRAMENTA[ferramenta]),
            periodo=computation.periodo,
        )
        resposta = Resposta[dados_cls](
            dados=dados_cls.model_validate(computation.dados.model_dump()),
            fonte=fonte,
            avisos=list(computation.avisos),
        )
        return resposta.model_dump(mode="json")

    @staticmethod
    def _log(
        ferramenta: str,
        entrada: EntradaComum | None,
        envelope: dict[str, Any],
        inicio: float,
    ) -> None:
        erro = envelope.get("erro")
        codigo = erro["codigo"] if isinstance(erro, dict) else None
        logger.log(
            logging.WARNING if codigo == CodigoErro.INDISPONIVEL else logging.INFO,
            "ferramenta chamada",
            extra={
                "evento": "ferramenta_chamada",
                "ferramenta": ferramenta,
                "latencia_ms": round((time.perf_counter() - inicio) * 1000, 2),
                "erro_codigo": codigo,
                "ate_anomes": entrada.ate_anomes if entrada is not None else None,
            },
        )


def _cause_info(exc: BaseException) -> Any:
    """``exc_info`` of the underlying cause (the log keeps only its class name)."""
    causa = exc.__cause__ or exc
    return (type(causa), causa, causa.__traceback__)
