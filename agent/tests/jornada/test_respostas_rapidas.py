"""Respostas rápidas do agente hello: regras (unidade) e evento do ADK (integração).

A integração roda um ``Runner`` em memória com modelo falso e ferramentas
locais que devolvem o mesmo formato do ``McpTool``, sem rede nem MCP.
"""

import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any

import pytest
from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.models import BaseLlm, LlmRequest, LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types

from bussola_agent import callbacks
from bussola_agent.jornada import respostas_rapidas
from bussola_agent.jornada.respostas_rapidas import MAX_SUGESTOES, anexar, sugerir

INICIO = ["Quero comprar meu primeiro apartamento"]


# --- regras -----------------------------------------------------------------


def test_antes_de_simular_sugere_valor_de_exemplo_e_exploracao() -> None:
    assert sugerir(set(), INICIO) == [
        "Quero juntar R$ 30 mil em 2 anos",
        "Quanto consigo guardar por mês?",
        "Onde posso economizar?",
    ]


def test_depois_de_simular_o_proximo_passo_sao_os_caminhos() -> None:
    assert sugerir({"simular_objetivo"}, INICIO) == [
        "Me mostra os caminhos",
        "Quanto consigo guardar por mês?",
        "Onde posso economizar?",
    ]


def test_depois_dos_cenarios_e_dos_cortes_sugere_escolher_o_caminho() -> None:
    """O caso da tela: cenários e cortes já mostrados, e os chips não acompanhavam."""
    usadas = {"simular_objetivo", "comparar_cenarios", "oportunidades_corte"}
    assert sugerir(usadas, INICIO) == [
        "Quero o caminho acelerado",
        "Quero o caminho equilibrado",
        "Quanto consigo guardar por mês?",
    ]


def test_o_que_o_cliente_ja_escreveu_nao_volta() -> None:
    usadas = {"comparar_cenarios", "oportunidades_corte", "capacidade_poupanca"}
    ditos = [*INICIO, "  quero o CAMINHO acelerado!  "]
    assert sugerir(usadas, ditos) == [
        "Quero o caminho equilibrado",
        "Tenho parcelas em aberto?",
        "Como foi meu último mês?",
    ]


def test_nunca_passa_do_maximo_e_pode_acabar() -> None:
    todas = {s.ferramenta for s in respostas_rapidas.SUGESTOES if s.ferramenta}
    todas |= {"simular_objetivo"}
    ditos = ["Quero o caminho acelerado", "quero o caminho equilibrado"]
    assert sugerir(todas, ditos) == []
    assert all(len(sugerir(u, [])) <= MAX_SUGESTOES for u in (set(), todas))


def test_sugestoes_nao_trazem_numero_alem_do_exemplo() -> None:
    """Só o valor de exemplo tem número, e ele é fixo: nada vem do modelo."""
    com_numero = [s.texto for s in respostas_rapidas.SUGESTOES if any(c.isdigit() for c in s.texto)]
    assert com_numero == ["Quero juntar R$ 30 mil em 2 anos"]


# --- callback sobre eventos -------------------------------------------------


def _mcp(envelope: dict[str, Any], *, erro_mcp: bool = False) -> dict[str, Any]:
    """Resultado como o ``McpTool`` do ADK entrega ao modelo."""
    return {
        "content": [{"type": "text", "text": json.dumps(envelope)}],
        "structuredContent": envelope,
        "isError": erro_mcp,
    }


def _resposta(nome: str, conteudo: dict[str, Any]) -> Event:
    parte = types.Part(function_response=types.FunctionResponse(name=nome, response=conteudo))
    return Event(author="bussola_hello", content=types.Content(role="user", parts=[parte]))


def _cliente(texto: str) -> Event:
    return Event(author="user", content=types.Content(role="user", parts=[types.Part(text=texto)]))


def _texto(texto: str, **extras: Any) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part(text=texto)]), **extras
    )


def _contexto(*eventos: Event) -> SimpleNamespace:
    return SimpleNamespace(session=SimpleNamespace(events=list(eventos)))


OK = {"dados": {}, "fonte": {"ferramenta": "x"}, "avisos": []}
ERRO = {"erro": {"codigo": "PRAZO_IMPLAUSIVEL", "mensagem": "..."}}


def test_anexa_na_mensagem_final_sem_interromper_a_cadeia() -> None:
    resposta = _texto("Seus caminhos", custom_metadata={"outro": 1})
    contexto = _contexto(_cliente("oi"), _resposta("comparar_cenarios", _mcp(OK)))
    assert anexar(callback_context=contexto, llm_response=resposta) is None
    assert resposta.custom_metadata == {
        "outro": 1,
        "bussola": {
            "respostas_rapidas": [
                "Quero o caminho acelerado",
                "Quero o caminho equilibrado",
                "Quanto consigo guardar por mês?",
            ]
        },
    }


@pytest.mark.parametrize(
    "conteudo",
    [
        _mcp(ERRO),
        _mcp(OK, erro_mcp=True),
        {"content": [{"type": "text", "text": json.dumps(ERRO)}]},
    ],
    ids=["envelope-erro", "isError", "erro-so-no-texto"],
)
def test_ferramenta_com_erro_nao_conta(conteudo: dict[str, Any]) -> None:
    resposta = _texto("Não deu")
    anexar(
        callback_context=_contexto(_resposta("simular_objetivo", conteudo)), llm_response=resposta
    )
    assert resposta.custom_metadata["bussola"]["respostas_rapidas"][0] == (
        "Quero juntar R$ 30 mil em 2 anos"
    )


@pytest.mark.parametrize(
    "resposta",
    [
        _texto("parc", partial=True),
        _texto("", error_code="503"),
        LlmResponse(
            content=types.Content(
                role="model",
                parts=[types.Part(function_call=types.FunctionCall(name="resumo_mes", args={}))],
            )
        ),
        LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text="pensando", thought=True)])
        ),
    ],
    ids=["parcial", "erro", "chamada-de-ferramenta", "so-raciocinio"],
)
def test_so_a_mensagem_final_recebe_sugestoes(resposta: LlmResponse) -> None:
    anexar(callback_context=_contexto(), llm_response=resposta)
    assert resposta.custom_metadata is None


def test_nao_sobrescreve_sugestoes_de_outro_callback() -> None:
    proprias = {"bussola": {"respostas_rapidas": ["Entendi"], "guardrail": "infra"}}
    resposta = _texto("Não posso", custom_metadata=proprias)
    anexar(callback_context=_contexto(), llm_response=resposta)
    assert resposta.custom_metadata == proprias


# --- integração com o Runner do ADK -----------------------------------------


class _ModeloFalso(BaseLlm):
    """Chama ``comparar_cenarios`` e depois responde em texto, com um parcial antes."""

    model: str = "falso"

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        if any(p.function_response for p in llm_request.contents[-1].parts or []):
            if stream:
                yield _texto("Estes são", partial=True)
            yield _texto("Estes são os seus caminhos.")
            return
        chamada = types.FunctionCall(name="comparar_cenarios", args={})
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(function_call=chamada)])
        )


def comparar_cenarios() -> dict[str, Any]:
    """Cenários do cliente (ferramenta local com o formato do MCP)."""
    return _mcp(OK)


async def test_evento_final_do_turno_leva_as_sugestoes_ao_front() -> None:
    callbacks.registrar("after_model", anexar, respostas_rapidas.ORDEM)
    agente = Agent(
        name="bussola_hello",
        model=_ModeloFalso(),
        tools=[comparar_cenarios],
        after_model_callback=callbacks.after_model,
    )
    runner = InMemoryRunner(agent=agente, app_name="bussola_agent")
    sessao = await runner.session_service.create_session(app_name="bussola_agent", user_id="u")
    mensagem = types.Content(role="user", parts=[types.Part(text="Quero os caminhos")])

    eventos = [
        e
        async for e in runner.run_async(
            user_id="u",
            session_id=sessao.id,
            new_message=mensagem,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    ]

    final = eventos[-1]
    assert final.content.parts[0].text == "Estes são os seus caminhos."
    # O front serializa com alias: customMetadata.bussola.respostas_rapidas.
    enviado = json.loads(final.model_dump_json(by_alias=True, exclude_none=True))
    assert enviado["customMetadata"]["bussola"]["respostas_rapidas"] == [
        "Quero o caminho acelerado",
        "Quero o caminho equilibrado",
        "Quanto consigo guardar por mês?",
    ]
    chamada = next(e for e in eventos if e.get_function_calls())
    assert chamada.custom_metadata is None
