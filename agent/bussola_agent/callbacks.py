"""Encadeador de callbacks do agente (contratos §6; research R-13).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``.

Os ciclos 004, 005 e 006 registram funções por fase com :func:`registrar`, e
o ``agent.py`` instala só os quatro agregados (:func:`before_model`,
:func:`after_model`, :func:`before_tool`, :func:`after_tool`).

- A cadeia roda em ordem crescente de ``ordem``; empates seguem a ordem de
  registro.
- O primeiro retorno diferente de ``None`` interrompe a cadeia e é o
  resultado do agregado.
- Cada função recebe os argumentos do ADK **por palavra-chave** e pode ser
  sync ou async.

Ordens reservadas: ver contratos §6.
"""

import inspect
import itertools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

FASES: tuple[str, ...] = ("before_model", "after_model", "before_tool", "after_tool")


@dataclass(frozen=True)
class _Registro:
    ordem: int
    seq: int
    funcao: Callable[..., Any]


_registros: dict[str, list[_Registro]] = {fase: [] for fase in FASES}
_seq = itertools.count()


def _validar_fase(fase: str) -> None:
    if fase not in FASES:
        raise ValueError(f"Fase de callback inválida. Use uma de: {', '.join(FASES)}.")


def registrar(fase: str, funcao: Callable[..., Any], ordem: int) -> None:
    """Registra ``funcao`` na ``fase`` com a ``ordem`` dada.

    - ``fase`` fora de :data:`FASES` levanta ``ValueError``;
    - ``funcao`` não chamável ou ``ordem`` não inteira levantam ``TypeError``.
    """
    _validar_fase(fase)
    if not callable(funcao):
        raise TypeError("funcao deve ser chamável.")
    if not isinstance(ordem, int) or isinstance(ordem, bool):
        raise TypeError("ordem deve ser um inteiro.")
    lista = _registros[fase]
    lista.append(_Registro(ordem=ordem, seq=next(_seq), funcao=funcao))
    lista.sort(key=lambda r: (r.ordem, r.seq))


def registrados(fase: str) -> list[Callable[..., Any]]:
    """Funções registradas na ``fase``, na ordem de execução (para inspeção e testes)."""
    _validar_fase(fase)
    return [r.funcao for r in _registros[fase]]


def limpar() -> None:
    """Esvazia todos os registros. Só para testes."""
    for lista in _registros.values():
        lista.clear()


async def _executar(fase: str, **kwargs: Any) -> Any:
    for registro in tuple(_registros[fase]):
        resultado = registro.funcao(**kwargs)
        if inspect.isawaitable(resultado):
            resultado = await resultado
        if resultado is not None:
            return resultado
    return None


async def before_model(callback_context: Any, llm_request: Any) -> Any:
    """Agregado de ``before_model_callback``: devolve um ``LlmResponse`` para pular o modelo."""
    return await _executar(
        "before_model", callback_context=callback_context, llm_request=llm_request
    )


async def after_model(callback_context: Any, llm_response: Any) -> Any:
    """Agregado de ``after_model_callback``: um ``LlmResponse`` devolvido substitui a resposta."""
    return await _executar(
        "after_model", callback_context=callback_context, llm_response=llm_response
    )


async def before_tool(tool: Any, args: dict[str, Any], tool_context: Any) -> Any:
    """Agregado de ``before_tool_callback``: devolve um ``dict`` para pular a ferramenta."""
    return await _executar("before_tool", tool=tool, args=args, tool_context=tool_context)


async def after_tool(tool: Any, args: dict[str, Any], tool_context: Any, tool_response: Any) -> Any:
    """Agregado de ``after_tool_callback``: devolve um ``dict`` para substituir o resultado."""
    return await _executar(
        "after_tool",
        tool=tool,
        args=args,
        tool_context=tool_context,
        tool_response=tool_response,
    )
