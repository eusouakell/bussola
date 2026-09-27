"""Camada anticorrupção sobre os objetos do ADK (``LlmResponse``, ``Event``, ``Part``).

O agente lê esses objetos por reflexão em vários pontos — parte de texto,
``function_call``, ``partial``, ``error_code``. Com ``getattr(..., None)``
espalhado, uma mudança de forma numa atualização do ``google-adk`` não quebra
nada: a verificação de números (constituição I) e a detecção de ação sem
ferramenta simplesmente param de achar texto e viram **no-op sem erro, sem log
e com os testes verdes**.

Este módulo concentra essa leitura e é o único lugar que conhece os nomes de
atributo do SDK. Quando um atributo esperado **não existe**, o acesso devolve o
mesmo default de antes (nada quebra em produção) mas registra
``evento=forma_adk_inesperada`` **uma vez por atributo**, com o nome da classe
e do atributo na mensagem. Nenhum conteúdo do turno é logado.

É o mesmo padrão que :mod:`bussola_agent.jornada.tool_results` aplica aos
envelopes §5: em vez de ler a forma do SDK em cada chamada, há um lugar só que
traduz a forma externa para o vocabulário do agente.
"""

from typing import Any

from bussola_agent.logging_json import obter_logger

EVENT_UNEXPECTED_SHAPE = "forma_adk_inesperada"
ERROR_UNEXPECTED_SHAPE = "FORMA_ADK_INESPERADA"

_log = obter_logger(__name__)
_MISSING = object()
_reported: set[str] = set()


def reset_reported() -> None:
    """Esquece as formas já reportadas. Só para testes."""
    _reported.clear()


def _read(holder: Any, name: str, default: Any) -> Any:
    """``holder.name``, ou ``default`` com um aviso único se o atributo sumiu."""
    value = getattr(holder, name, _MISSING)
    if value is not _MISSING:
        return value
    key = f"{type(holder).__name__}.{name}"
    if key not in _reported:
        _reported.add(key)
        _log.error(
            f"Objeto do ADK sem o atributo esperado ({key}); a leitura caiu no default.",
            extra={"evento": EVENT_UNEXPECTED_SHAPE, "erro_codigo": ERROR_UNEXPECTED_SHAPE},
        )
    return default


def content_parts(content: Any) -> list[Any]:
    """Partes de um ``Content`` do ADK; ``[]`` quando é ``None`` ou não tem parte."""
    if content is None:
        return []
    return list(_read(content, "parts", None) or [])


def parts(holder: Any) -> list[Any]:
    """Partes de ``holder.content`` (``LlmResponse`` ou ``Event``); ``[]`` sem conteúdo."""
    if holder is None:
        return []
    return content_parts(_read(holder, "content", None))


def text_parts(holder: Any) -> list[Any]:
    """Partes de texto visível ao cliente: com ``text`` não vazio e sem ``thought``."""
    return [p for p in parts(holder) if _read(p, "text", None) and not _read(p, "thought", False)]


def has_function_call(holder: Any) -> bool:
    """``True`` se alguma parte carrega uma chamada de ferramenta."""
    return any(_read(p, "function_call", None) for p in parts(holder))


def final_text(holder: Any) -> str:
    """Texto visível ao cliente, concatenado na ordem das partes."""
    return "".join(p.text for p in text_parts(holder))


def is_final_text(llm_response: Any) -> bool:
    """Texto completo do modelo, sem chamada de ferramenta pendente.

    ``partial`` (streaming) e ``error_code`` (turno derrubado) não são resposta
    final; um turno que só chama ferramenta também não.
    """
    if _read(llm_response, "partial", False) or _read(llm_response, "error_code", None):
        return False
    if has_function_call(llm_response):
        return False
    return bool(text_parts(llm_response))


def append_text(llm_response: Any, suffix: str, separator: str = "\n\n") -> bool:
    """Acrescenta ``suffix`` à última parte de texto, no lugar. ``False`` se não houver."""
    found = text_parts(llm_response)
    if not found:
        return False
    last = found[-1]
    last.text = f"{last.text.rstrip()}{separator}{suffix}"
    return True
