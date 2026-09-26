"""Pontos de extensão do agente (contratos §6; research R-12).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``.

Os ciclos 005 (``bussola_agent.governanca``) e 006
(``bussola_agent.acompanhamento``) acrescentam ferramentas, trechos de
instrução e callbacks sem editar o ``agent.py`` do 004. O ``__init__.py`` de
cada pacote registra o que for seu, e o ``agent.py`` chama
:func:`carregar_extensoes` antes de montar o ``root_agent``.

Ordens de instrução reservadas: 004 usa 0–49, 005 usa 50–69 e 006 usa 70–89.
"""

import importlib
import importlib.util
import itertools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google.adk.tools.base_tool import BaseTool

from bussola_agent.logging_json import obter_logger

PACOTES_EXTENSAO: tuple[str, ...] = (
    "bussola_agent.governanca",
    "bussola_agent.acompanhamento",
)

_log = obter_logger(__name__)


@dataclass(frozen=True)
class _Instrucao:
    ordem: int
    seq: int
    texto: str


_ferramentas: dict[str, Any] = {}
_sensiveis: set[str] = set()
_instrucoes: list[_Instrucao] = []
_seq = itertools.count()


def _nome_ferramenta(fn: Any) -> str:
    """Nome com que o ADK expõe a ferramenta ao modelo."""
    if isinstance(fn, BaseTool):
        nome = fn.name
    elif callable(fn):
        nome = getattr(fn, "__name__", None)
    else:
        raise TypeError("A ferramenta deve ser uma função ou um BaseTool do ADK.")
    if not isinstance(nome, str) or not nome or nome == "<lambda>":
        raise TypeError("A ferramenta precisa de um nome (use uma função nomeada).")
    return nome


def registrar_ferramenta(fn: Callable[..., Any], sensivel: bool = False) -> None:
    """Registra uma ferramenta ADK local (função ou ``BaseTool``).

    - ``sensivel=True`` marca a ferramenta como ação sensível (gate do 005).
    - Um nome já registrado levanta ``ValueError``.
    """
    nome = _nome_ferramenta(fn)
    if nome in _ferramentas:
        raise ValueError(f"Ferramenta já registrada: {nome}.")
    _ferramentas[nome] = fn
    if sensivel:
        _sensiveis.add(nome)


def registrar_instrucao(ordem: int, texto: str) -> None:
    """Registra um trecho do prompt. Os trechos são concatenados por ``ordem`` crescente."""
    if not isinstance(ordem, int) or isinstance(ordem, bool):
        raise TypeError("ordem deve ser um inteiro.")
    if not isinstance(texto, str):
        raise TypeError("texto deve ser uma string.")
    if not texto.strip():
        raise ValueError("texto da instrução não pode ser vazio.")
    _instrucoes.append(_Instrucao(ordem=ordem, seq=next(_seq), texto=texto.strip()))
    _instrucoes.sort(key=lambda i: (i.ordem, i.seq))


def ferramentas() -> list[Callable[..., Any]]:
    """Ferramentas registradas, na ordem de registro."""
    return list(_ferramentas.values())


def ferramentas_sensiveis() -> set[str]:
    """Nomes das ferramentas registradas com ``sensivel=True``."""
    return set(_sensiveis)


def instrucoes() -> str:
    """Trechos registrados, por ordem crescente, separados por linha em branco ("" se nenhum)."""
    return "\n\n".join(i.texto for i in _instrucoes)


def carregar_extensoes() -> None:
    """Importa os pacotes de extensão que existirem.

    - Pacote ausente (``find_spec`` devolve ``None``): é pulado.
    - Pacote presente com erro de import: o erro **propaga** (Q-04 do 000).

    Um pacote já importado não é reimportado (o ``import`` do Python é
    idempotente), então os registros do ``__init__.py`` rodam uma vez só.
    """
    for nome in PACOTES_EXTENSAO:
        if importlib.util.find_spec(nome) is None:
            _log.debug(
                "Pacote de extensão ausente; ignorado.", extra={"evento": "extensao_ausente"}
            )
            continue
        importlib.import_module(nome)
        _log.info("Pacote de extensão carregado.", extra={"evento": "extensao_carregada"})


def limpar() -> None:
    """Esvazia ferramentas, marcas de sensível e instruções. Só para testes."""
    _ferramentas.clear()
    _sensiveis.clear()
    _instrucoes.clear()
