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

Com ``estado_jornada`` no state (agente da jornada do 004), a etapa define as
candidatas (:data:`POR_ETAPA`): o exemplo só em OBJETIVO, os caminhos em
ANTECIPAR, a escolha do recomendado e "outro caminho" em ORIENTAR. Em AGIR e
ACOMPANHAR o campo fica ausente: valem as sugestões que 005 e 006 puserem ou as
do front para a etapa. As regras de ferramenta já usada, do que o cliente
escreveu e do máximo continuam valendo. Sem ``estado_jornada``, valem as regras
acima.
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from bussola_agent.estado import CHAVE_CENARIOS, CHAVE_ESTADO_JORNADA, EstadoJornada
from bussola_agent.jornada.annotations import recommended_scenario

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

EXEMPLO = SUGESTOES[0]
MOSTRAR_CAMINHOS = Sugestao("Me mostra os caminhos")
"""Em ANTECIPAR os cenários ainda não existem, mesmo que já tenham sido comparados antes."""
OUTRO_CAMINHO = Sugestao("Quero outro caminho")
CENARIOS = frozenset({"conservador", "equilibrado", "acelerado"})
"""Nomes fixos dos cenários (``comparar_cenarios``); outro nome não vira chip."""
_POR_FERRAMENTA = {s.ferramenta: s for s in SUGESTOES if s.ferramenta}


def _dados(*ferramentas: str) -> tuple[Sugestao, ...]:
    return tuple(_POR_FERRAMENTA[f] for f in ferramentas)


_EXPLORAR = _dados(
    "capacidade_poupanca",
    "oportunidades_corte",
    "dividas_e_parcelas",
    "resumo_mes",
    "perfil_financeiro",
)
POR_ETAPA: Mapping[EstadoJornada, tuple[Sugestao, ...]] = {
    EstadoJornada.OBJETIVO: (EXEMPLO, *_EXPLORAR),
    EstadoJornada.ENTENDER: _dados(
        "capacidade_poupanca",
        "perfil_financeiro",
        "dividas_e_parcelas",
        "oportunidades_corte",
        "resumo_mes",
    ),
    EstadoJornada.ANTECIPAR: (MOSTRAR_CAMINHOS, *_EXPLORAR),
    EstadoJornada.ORIENTAR: (OUTRO_CAMINHO, *_dados("oportunidades_corte"), *_EXPLORAR),
    EstadoJornada.AGIR: (),
    EstadoJornada.ACOMPANHAR: (),
}


def _normalizar(texto: str) -> str:
    return " ".join(texto.casefold().split()).rstrip("?!. ")


def _etapa(valor: Any) -> EstadoJornada | None:
    try:
        return EstadoJornada(valor)
    except ValueError:
        return None


def _candidatas(etapa: EstadoJornada, recomendado: str | None) -> tuple[Sugestao, ...]:
    candidatas = POR_ETAPA[etapa]
    if etapa is EstadoJornada.ORIENTAR and recomendado in CENARIOS:
        return (Sugestao(f"Quero o caminho {recomendado}"), *candidatas)
    return candidatas


def sugerir(
    ferramentas: set[str],
    ditos: Iterable[str],
    estado: str | None = None,
    recomendado: str | None = None,
) -> list[str]:
    """Até ``MAX_SUGESTOES`` textos, sem repetição.

    ``ferramentas`` são as que responderam sem erro na sessão e ``ditos``, as
    mensagens do cliente. Com ``estado`` (``estado_jornada``) válido, as
    candidatas vêm de :data:`POR_ETAPA`; ``recomendado`` é o cenário da regra
    R9, sugerido primeiro em ORIENTAR. Sem ``estado``, valem :data:`SUGESTOES`.
    """
    ja_ditos = {_normalizar(t) for t in ditos}
    etapa = _etapa(estado) if estado is not None else None
    if etapa is None:
        candidatas = [
            s
            for s in SUGESTOES
            if (not s.exige or s.exige & ferramentas) and not s.antes_de & ferramentas
        ]
    else:
        candidatas = list(_candidatas(etapa, recomendado))
    escolhidas: list[str] = []
    for s in candidatas:
        if (
            s.ferramenta not in ferramentas
            and _normalizar(s.texto) not in ja_ditos
            and s.texto not in escolhidas
        ):
            escolhidas.append(s.texto)
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


def _jornada(callback_context: Any) -> tuple[str | None, str | None]:
    """``estado_jornada`` e o cenário recomendado dos ``cenarios`` do state, se houver."""
    state = getattr(callback_context, "state", None)
    if state is None:
        return None, None
    estado = state.get(CHAVE_ESTADO_JORNADA)
    return (estado if isinstance(estado, str) else None), recommended_scenario(
        state.get(CHAVE_CENARIOS)
    )


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
    estado, recomendado = _jornada(callback_context)
    sugestoes = sugerir(ferramentas, ditos, estado, recomendado)
    if sugestoes:
        bussola["respostas_rapidas"] = sugestoes
        metadados["bussola"] = bussola
        llm_response.custom_metadata = metadados
    return None
