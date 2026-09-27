"""Agente da jornada do 004 (spec FR-001–FR-003): ``root_agent`` para ``adk web`` e Cloud Run.

- Extensões: ``carregar_extensoes()`` roda antes de montar o ``root_agent``,
  para que ferramentas, trechos de instrução e callbacks de 005 e 006 entrem.
- Ferramentas: o ``McpToolset`` do ``bussola-mcp``, as ferramentas locais da
  jornada (``registrar_objetivo`` e ``escolher_cenario``) e as das extensões.
- Instrução: o prompt base em pt-BR de :mod:`bussola_agent.prompts` (persona,
  etapa atual, regras de número e fonte, blocos, catálogo curado e limites)
  seguido de ``extensoes.instrucoes()``. Os placeholders ``{...?}`` são
  preenchidos pelo ADK a partir do ``session.state`` a cada chamada.
- Callbacks: os 4 agregados de :mod:`bussola_agent.callbacks`, o
  ``before_agent_callback`` de :func:`bussola_agent.escopo.initialize_session`
  e o ``on_model_error_callback`` de alta demanda. As cadeias do 004 são:

  ================  =====  ==============================================
  fase              ordem  função
  ================  =====  ==============================================
  ``before_model``  30     ferramenta obrigatória após o "sim" do cliente
  ``before_tool``   10     escopo da sessão (``enforce_scope``)
  ``after_tool``    10     jornada e fontes (``record_tool_result``)
  ``after_model``   50     verificação de números (``check_numbers``)
  ``after_model``   60     ação afirmada sem ferramenta no turno
  ``after_model``   90     ``tag``/``recomendado``, depois respostas rápidas
  ================  =====  ==============================================

- Modelo: ``BUSSOLA_MODEL`` seguido dos outros Flash verificados pelo smoke,
  com uma retentativa por modelo, cada um chamado sem streaming
  (:mod:`bussola_agent.resilient_model`). Um 429 ou 5xx passa para o próximo
  da cadeia; com a cadeia esgotada, o cliente recebe a mensagem de alta
  demanda em pt-BR.
- Safety settings do Gemini em ``BLOCK_MEDIUM_AND_ABOVE`` nas categorias
  padrão (fallback de guardrail do mestre §10 F5).

Importar este módulo não acessa a rede nem chama modelos.
"""

from google.adk.agents import Agent
from google.adk.models import FallbackModel, Gemini
from google.genai import types

from bussola_agent import callbacks, config, escopo, prompts
from bussola_agent.extensoes import carregar_extensoes, ferramentas, instrucoes
from bussola_agent.jornada import (
    action_claims,
    annotations,
    number_check,
    respostas_rapidas,
    tool_forcing,
)
from bussola_agent.jornada.tools import escolher_cenario, registrar_objetivo
from bussola_agent.logging_json import configurar_logging
from bussola_agent.mcp_conexao import criar_toolset
from bussola_agent.resilient_model import build_fallback_chain, capacity_error_response

NOME_AGENTE = "bussola"
# Modelo, cadeia de fallback e limites de retentativa: de
# :mod:`bussola_agent.config`, a fonte única (os nomes ficam por compatibilidade).
MODELO_PADRAO = config.MODELO_PADRAO
MODELOS_FLASH = config.MODELOS_FLASH
RETENTATIVA = types.HttpRetryOptions(
    attempts=config.RETENTATIVA_TENTATIVAS,
    initial_delay=config.RETENTATIVA_ESPERA_INICIAL_S,
    max_delay=config.RETENTATIVA_ESPERA_MAXIMA_S,
)
ANCHOR_PADRAO = escopo.DEFAULT_ANCHOR_USER_ID
REPLAY_START_PADRAO = escopo.DEFAULT_REPLAY_START
CATEGORIAS_SEGURANCA = (
    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
)

configurar_logging()

# Nome usado na documentação dos ciclos para o ``before_agent_callback``.
inicializar_sessao = escopo.initialize_session


def criar_modelo(principal: str) -> FallbackModel:
    """``principal`` e os demais Flash, nessa ordem, cada um com ``RETENTATIVA``.

    O ``FallbackModel`` só troca de modelo antes da primeira resposta do turno.
    Por isso cada Gemini é chamado sem streaming (``NonStreamingModel``): um
    erro de capacidade no meio da geração acontece antes de qualquer resposta
    e ainda cai para o próximo modelo. Construir não acessa a rede: o cliente
    do genai nasce na primeira chamada.
    """
    nomes = config.cadeia_de_modelos(principal)
    return build_fallback_chain([Gemini(model=n, retry_options=RETENTATIVA) for n in nomes])


def configuracao_geracao() -> types.GenerateContentConfig:
    """Safety settings ``BLOCK_MEDIUM_AND_ABOVE`` nas categorias padrão."""
    return types.GenerateContentConfig(
        safety_settings=[
            types.SafetySetting(
                category=categoria,
                threshold=types.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            )
            for categoria in CATEGORIAS_SEGURANCA
        ]
    )


def registrar_callbacks() -> None:
    """Cadeias do 004 no registro de :mod:`bussola_agent.callbacks`."""
    callbacks.registrar("before_model", tool_forcing.force_authorized_action, tool_forcing.ORDER)
    callbacks.registrar("before_tool", escopo.enforce_scope, escopo.ORDER)
    callbacks.registrar("after_tool", escopo.record_tool_result, escopo.ORDER)
    callbacks.registrar("after_model", number_check.check_numbers, number_check.ORDER)
    callbacks.registrar("after_model", action_claims.check_action_claims, action_claims.ORDER)
    # Mesma ordem: as anotações rodam antes das respostas rápidas.
    callbacks.registrar("after_model", annotations.annotate, annotations.ORDER)
    callbacks.registrar("after_model", respostas_rapidas.anexar, respostas_rapidas.ORDEM)


carregar_extensoes()
registrar_callbacks()

root_agent = Agent(
    name=NOME_AGENTE,
    model=criar_modelo(config.modelo_principal()),
    description=(
        "Bússola, do app do banco: ajuda o cliente a transformar um objetivo financeiro "
        "em plano, com números das ferramentas MCP."
    ),
    instruction=prompts.build_instruction(instrucoes()),
    generate_content_config=configuracao_geracao(),
    tools=[criar_toolset(), registrar_objetivo, escolher_cenario, *ferramentas()],
    before_agent_callback=inicializar_sessao,
    on_model_error_callback=capacity_error_response,
    before_model_callback=callbacks.before_model,
    after_model_callback=callbacks.after_model,
    before_tool_callback=callbacks.before_tool,
    after_tool_callback=callbacks.after_tool,
)
