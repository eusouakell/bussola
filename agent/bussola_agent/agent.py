"""Agente hello do 000 (FR-019): ``root_agent`` para ``adk web`` e Cloud Run.

- Ferramentas: o ``McpToolset`` do ``bussola-mcp`` mais as ferramentas
  registradas pelas extensões.
- Instrução: um texto base mínimo em pt-BR, mais os trechos das extensões.
- Callbacks: os 4 agregados de :mod:`bussola_agent.callbacks` e um
  ``before_agent_callback`` que preenche o escopo da sessão com
  ``ANCHOR_USER_ID`` e ``REPLAY_START_ANOMES`` quando ausente. A única cadeia
  preenchida aqui é ``after_model``, com as respostas rápidas de
  :mod:`bussola_agent.jornada.respostas_rapidas`.
- Modelo: ``BUSSOLA_MODEL`` seguido dos outros Flash verificados pelo smoke,
  com uma retentativa por modelo, cada um chamado sem streaming
  (:mod:`bussola_agent.resilient_model`). Um 429 ou 5xx, antes ou durante a
  geração, passa para o próximo da cadeia em vez de derrubar o turno. Com a
  cadeia esgotada, o ``on_model_error_callback`` responde com uma mensagem de
  alta demanda em pt-BR.

O 004 substitui este arquivo pelo agente da jornada, mantendo o mesmo
esqueleto (``carregar_extensoes()`` antes de montar o ``root_agent``).
Importar este módulo não acessa a rede nem chama modelos.
"""

import os
from typing import Any

from google.adk.agents import Agent
from google.adk.models import FallbackModel, Gemini
from google.genai import types

from bussola_agent import callbacks
from bussola_agent.estado import CHAVE_ATE_ANOMES, CHAVE_ID_USUARIO, estado_inicial
from bussola_agent.extensoes import carregar_extensoes, ferramentas, instrucoes
from bussola_agent.jornada import respostas_rapidas
from bussola_agent.logging_json import configurar_logging, obter_logger
from bussola_agent.mcp_conexao import criar_toolset
from bussola_agent.resilient_model import build_fallback_chain, capacity_error_response

NOME_AGENTE = "bussola_hello"
MODELO_PADRAO = "gemini-3.8-flash"
# Cadeia Flash que respondeu no smoke (specs/000-fundacao-contratos/modelos.md).
MODELOS_FLASH = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash")
# Uma retentativa no mesmo modelo (408, 429 e 5xx) antes de passar ao próximo.
RETENTATIVA = types.HttpRetryOptions(attempts=2, initial_delay=1.0, max_delay=4.0)
ANCHOR_PADRAO = "36a21505-d6d4-42d3-b319-d51a133c7269"
REPLAY_START_PADRAO = 202506
_CHAVES_ESCOPO = (CHAVE_ID_USUARIO, CHAVE_ATE_ANOMES)

INSTRUCAO_BASE = """\
Você é o Bússola, um assistente de finanças pessoais que responde em português do Brasil.

Contexto da sessão:
- cliente: {id_usuario?}
- dados disponíveis até o mês (AAAAMM): {ate_anomes?}

Regras:
- Use as ferramentas para obter qualquer número sobre o cliente. Nunca invente valores.
- Em toda chamada de ferramenta, passe id_usuario e ate_anomes exatamente como acima.
- Se uma ferramenta devolver "erro", explique o problema em linguagem simples, sem jargão.
- Responda de forma curta e cite a fonte (ferramenta e período) dos números usados.
"""

configurar_logging()
_log = obter_logger(__name__)


async def inicializar_sessao(callback_context: Any) -> None:
    """Preenche as chaves de §6 ausentes no ``session.state`` (``before_agent_callback``).

    ``id_usuario`` vem de ``ANCHOR_USER_ID`` e ``ate_anomes`` de
    ``REPLAY_START_ANOMES``. Chaves já presentes não são alteradas. Com
    configuração inválida, registra o erro e segue sem escopo (as ferramentas
    devolvem ``ENTRADA_INVALIDA``).
    """
    state = callback_context.state
    try:
        inicial = estado_inicial(
            os.getenv("ANCHOR_USER_ID") or ANCHOR_PADRAO,
            int(os.getenv("REPLAY_START_ANOMES") or REPLAY_START_PADRAO),
        )
    except ValueError:
        _log.error(
            "ANCHOR_USER_ID ou REPLAY_START_ANOMES inválido.",
            extra={"evento": "sessao_sem_escopo", "erro_codigo": "CONFIGURACAO_INVALIDA"},
        )
        return None
    novas = [
        chave
        for chave in inicial
        if chave not in state or (chave in _CHAVES_ESCOPO and state.get(chave) is None)
    ]
    for chave in novas:
        state[chave] = inicial[chave]
    if novas:
        _log.info(
            "Estado da sessão inicializado.",
            extra={
                "evento": "sessao_iniciada",
                "session_id": getattr(getattr(callback_context, "session", None), "id", None),
                "ate_anomes": state.get(CHAVE_ATE_ANOMES),
            },
        )
    return None


def criar_modelo(principal: str) -> FallbackModel:
    """``principal`` e os demais Flash, nessa ordem, cada um com ``RETENTATIVA``.

    O ``FallbackModel`` só troca de modelo antes da primeira resposta do turno.
    Por isso cada Gemini é chamado sem streaming (``NonStreamingModel``): um
    erro de capacidade no meio da geração acontece antes de qualquer resposta
    e ainda cai para o próximo modelo. Construir não acessa a rede: o cliente
    do genai nasce na primeira chamada.
    """
    nomes = [principal, *(m for m in MODELOS_FLASH if m != principal)]
    return build_fallback_chain([Gemini(model=n, retry_options=RETENTATIVA) for n in nomes])


def _instrucao() -> str:
    extras = instrucoes()
    return f"{INSTRUCAO_BASE}\n{extras}\n" if extras else INSTRUCAO_BASE


carregar_extensoes()
callbacks.registrar("after_model", respostas_rapidas.anexar, respostas_rapidas.ORDEM)

root_agent = Agent(
    name=NOME_AGENTE,
    model=criar_modelo(os.getenv("BUSSOLA_MODEL") or MODELO_PADRAO),
    description="Agente hello do Bússola: conversa em pt-BR usando as ferramentas MCP.",
    instruction=_instrucao(),
    tools=[criar_toolset(), *ferramentas()],
    before_agent_callback=inicializar_sessao,
    on_model_error_callback=capacity_error_response,
    before_model_callback=callbacks.before_model,
    after_model_callback=callbacks.after_model,
    before_tool_callback=callbacks.before_tool,
    after_tool_callback=callbacks.after_tool,
)
