"""Extensão do ciclo 009: marcos financeiros intermediários.

Carregada por ``extensoes.carregar_extensoes()``, sem editar o ``agent.py`` do
004. Registra:

- a instrução de prompt na ordem 90 (contratos §6, ordens 90–99 do 009);
- o callback ``after_tool`` na ordem 30, que grava ``marcos`` no
  ``session.state``.

A ferramenta em si é a ``planejar_marcos`` do MCP, já exposta ao modelo pelo
``McpToolset``.
"""

from bussola_agent import callbacks, extensoes
from bussola_agent.marcos.instrucao import INSTRUCAO
from bussola_agent.marcos.instrucao import ORDEM as ORDEM_INSTRUCAO
from bussola_agent.marcos.registro import ORDEM as ORDEM_CALLBACK
from bussola_agent.marcos.registro import gravar_marcos

extensoes.registrar_instrucao(ORDEM_INSTRUCAO, INSTRUCAO)
callbacks.registrar("after_tool", gravar_marcos, ORDEM_CALLBACK)

__all__ = ["INSTRUCAO", "ORDEM_CALLBACK", "ORDEM_INSTRUCAO", "gravar_marcos"]
