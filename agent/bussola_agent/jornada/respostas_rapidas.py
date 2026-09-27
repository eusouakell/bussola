"""Respostas rápidas (chips do composer) na mensagem final do agente, sem LLM.

O front lê ``customMetadata.bussola.respostas_rapidas`` da última mensagem do
agente (``specs/008-front-web/contracts/eventos-agente.md`` §5). Sem esse
campo, ele cai nas sugestões do ``estado_jornada``, que o agente hello não
avança: o cliente via sempre os objetivos iniciais e precisava digitar.

As sugestões saem de regras sobre a sessão, e não do modelo. Assim nenhuma
traz número inventado nem pede o que as ferramentas não atendem. As regras são:

- a sugestão que aciona uma ferramenta some depois que ela respondeu sem erro
  (os dados não mudam dentro da sessão);
- o valor de exemplo aparece só antes da primeira simulação, e os caminhos,
  só depois de ``comparar_cenarios``;
- o que o cliente já escreveu não volta como sugestão.

O 004 troca estas regras pela máquina de estados da jornada.
"""

import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# Depois do guardrail de saída (10) e da verificação de números (50), contratos §6.
ORDEM = 90
MAX_SUGESTOES = 3

_SIMULACOES = frozenset({"simular_objetivo", "comparar_cenarios"})


@dataclass(frozen=True)
class Sugestao:
    texto: str
    ferramenta: str | None = None
    """Ferramenta que a sugestão aciona. Depois que ela responde, a sugestão some."""
    exige: frozenset[str] = frozenset()
    """Aparece só depois que uma destas ferramentas respondeu."""
    antes_de: frozenset[str] = frozenset()
    """Some quando qualquer uma destas ferramentas respondeu."""


# Em ordem de prioridade: o próximo passo da jornada vem antes da exploração.
SUGESTOES: tuple[Sugestao, ...] = (
    Sugestao("Quero juntar R$ 30 mil em 2 anos", antes_de=_SIMULACOES),
    Sugestao(
        "Me mostra os caminhos",
        ferramenta="comparar_cenarios",
        exige=frozenset({"simular_objetivo"}),
    ),
    Sugestao("Quero o caminho acelerado", exige=frozenset({"comparar_cenarios"})),
    Sugestao("Quero o caminho equilibrado", exige=frozenset({"comparar_cenarios"})),
    Sugestao("Quanto consigo guardar por mês?", ferramenta="capacidade_poupanca"),
    Sugestao("Onde posso economizar?", ferramenta="oportunidades_corte"),
    Sugestao("Tenho parcelas em aberto?", ferramenta="dividas_e_parcelas"),
    Sugestao("Como foi meu último mês?", ferramenta="resumo_mes"),
    Sugestao("Como está meu perfil financeiro?", ferramenta="perfil_financeiro"),
)


def _normalizar(texto: str) -> str:
    return " ".join(texto.casefold().split()).rstrip("?!. ")


def sugerir(ferramentas: set[str], ditos: Iterable[str]) -> list[str]:
    """Até ``MAX_SUGESTOES`` textos de :data:`SUGESTOES`.

    ``ferramentas`` são as que responderam sem erro na sessão e ``ditos``, as
    mensagens do cliente.
    """
    ja_ditos = {_normalizar(t) for t in ditos}
    escolhidas = [
        s.texto
        for s in SUGESTOES
        if s.ferramenta not in ferramentas
        and (not s.exige or s.exige & ferramentas)
        and not s.antes_de & ferramentas
        and _normalizar(s.texto) not in ja_ditos
    ]
    return escolhidas[:MAX_SUGESTOES]


def _falhou(resposta: Any) -> bool:
    """``isError`` do MCP ou envelope ``{erro}``, nos embrulhos que o front também lê."""
    if not isinstance(resposta, dict):
        return False
    if resposta.get("isError") is True or resposta.get("is_error") is True:
        return True
    if isinstance(resposta.get("erro"), dict):
        return True
    if any(_falhou(resposta.get(chave)) for chave in ("result", "structuredContent")):
        return True
    conteudo = resposta.get("content")
    for parte in conteudo if isinstance(conteudo, list) else ():
        if isinstance(parte, dict) and parte.get("type") == "text":
            try:
                if _falhou(json.loads(parte.get("text") or "")):
                    return True
            except ValueError:
                continue
    return False


def _partes(evento: Any) -> list[Any]:
    conteudo = getattr(evento, "content", None)
    return list(getattr(conteudo, "parts", None) or [])


def _ler_sessao(eventos: Iterable[Any]) -> tuple[set[str], list[str]]:
    ferramentas: set[str] = set()
    ditos: list[str] = []
    for evento in eventos:
        for parte in _partes(evento):
            resposta = parte.function_response
            if resposta is not None and resposta.name and not _falhou(resposta.response):
                ferramentas.add(resposta.name)
            elif evento.author == "user" and parte.text:
                ditos.append(parte.text)
    return ferramentas, ditos


def _eh_mensagem_final(llm_response: Any) -> bool:
    """Texto completo do modelo, sem chamada de ferramenta pendente."""
    if llm_response.partial or llm_response.error_code:
        return False
    partes = _partes(llm_response)
    if any(p.function_call for p in partes):
        return False
    return any(p.text and not p.thought for p in partes)


def anexar(callback_context: Any, llm_response: Any) -> None:
    """``after_model``: põe as sugestões em ``custom_metadata.bussola``.

    Altera a resposta no lugar e devolve ``None``, para não interromper a
    cadeia. Não sobrescreve sugestões que outro callback já tenha posto.
    """
    if not _eh_mensagem_final(llm_response):
        return None
    metadados = dict(llm_response.custom_metadata or {})
    bussola = dict(metadados.get("bussola") or {})
    if "respostas_rapidas" in bussola:
        return None
    ferramentas, ditos = _ler_sessao(callback_context.session.events)
    sugestoes = sugerir(ferramentas, ditos)
    if sugestoes:
        bussola["respostas_rapidas"] = sugestoes
        metadados["bussola"] = bussola
        llm_response.custom_metadata = metadados
    return None
