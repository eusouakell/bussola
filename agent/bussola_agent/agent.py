"""Agente hello do 000 (FR-019): ``root_agent`` para ``adk web`` e Cloud Run.

- Ferramentas: o ``McpToolset`` do ``bussola-mcp`` mais as ferramentas
  registradas pelas extensões.
- Instrução: um texto base mínimo em pt-BR, mais os trechos das extensões.
- Callbacks: os 4 agregados de :mod:`bussola_agent.callbacks` (no 000, as
  cadeias estão vazias) e um ``before_agent_callback`` que preenche o escopo
  da sessão com ``ANCHOR_USER_ID`` e ``REPLAY_START_ANOMES`` quando ausente.

O 004 substitui este arquivo pelo agente da jornada, mantendo o mesmo
esqueleto (``carregar_extensoes()`` antes de montar o ``root_agent``).
Importar este módulo não acessa a rede nem chama modelos.
"""

import os
from typing import Any

from google.adk.agents import Agent

from bussola_agent import callbacks
from bussola_agent.estado import CHAVE_ATE_ANOMES, CHAVE_ID_USUARIO, estado_inicial
from bussola_agent.extensoes import carregar_extensoes, ferramentas, instrucoes
from bussola_agent.logging_json import configurar_logging, obter_logger
from bussola_agent.mcp_conexao import criar_toolset

NOME_AGENTE = "bussola_hello"
MODELO_PADRAO = "gemini-3.8-flash"
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


def _instrucao() -> str:
    extras = instrucoes()
    return f"{INSTRUCAO_BASE}\n{extras}\n" if extras else INSTRUCAO_BASE


carregar_extensoes()

root_agent = Agent(
    name=NOME_AGENTE,
    model=os.getenv("BUSSOLA_MODEL") or MODELO_PADRAO,
    description="Agente hello do Bússola: conversa em pt-BR usando as ferramentas MCP.",
    instruction=_instrucao(),
    tools=[criar_toolset(), *ferramentas()],
    before_agent_callback=inicializar_sessao,
    before_model_callback=callbacks.before_model,
    after_model_callback=callbacks.after_model,
    before_tool_callback=callbacks.before_tool,
    after_tool_callback=callbacks.after_tool,
)
