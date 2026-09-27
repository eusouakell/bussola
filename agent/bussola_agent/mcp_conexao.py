"""Conexão do agente com o servidor ``bussola-mcp`` (contratos §6; research R-13).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``.

- :func:`criar_toolset` monta o ``McpToolset`` do ADK em streamable HTTP.
- :func:`aplicar_escopo` força ``id_usuario`` e ``ate_anomes`` a partir do
  ``session.state``; valores enviados pelo modelo são ignorados.
- :func:`chamar_ferramenta` chama uma ferramenta MCP diretamente, sem LLM
  (usada pelo 006). Nunca levanta exceção para quem chama: uma falha de
  transporte vira o envelope ``INDISPONIVEL``.

Com ``MCP_USE_OIDC=TRUE`` (Cloud Run), cada sessão MCP leva o header
``Authorization: Bearer <ID token>``, com ``audience`` = URL base do
``bussola-mcp`` (``esquema://host[:porta]``). O token fica em cache por cerca
de 45 minutos (um ID token do Google vale 1 hora).

Importar este módulo não acessa a rede.
"""

import asyncio
import json
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.types import CallToolResult, TextContent

from bussola_agent import config
from bussola_agent.estado import (
    CHAVE_ATE_ANOMES,
    CHAVE_ID_USUARIO,
    obter_ate_anomes,
    obter_id_usuario,
)
from bussola_agent.logging_json import obter_logger

URL_PADRAO = config.MCP_URL_PADRAO

# Ferramentas servidas pelo mock do 000 (7 P0 + ``resumo_mes``), contratos §5.
FERRAMENTAS_MCP: tuple[str, ...] = (
    "perfil_financeiro",
    "capacidade_poupanca",
    "oportunidades_corte",
    "dividas_e_parcelas",
    "simular_objetivo",
    "comparar_cenarios",
    "buscar_contexto_financeiro",
    "resumo_mes",
    # Acréscimo do 009: marcos intermediários quando o objetivo não cabe.
    "planejar_marcos",
)

# Mesmos códigos de ``bussola_mcp.contratos`` (o agente não depende do MCP).
ERRO_ENTRADA_INVALIDA = "ENTRADA_INVALIDA"
ERRO_INDISPONIVEL = "INDISPONIVEL"
MSG_INDISPONIVEL = "Serviço temporariamente indisponível."
MSG_ESCOPO_INVALIDO = "Entrada inválida: id_usuario, ate_anomes."

# Validade do ID token em cache e tempo máximo de uma chamada: de
# :mod:`bussola_agent.config`, a fonte única (os nomes ficam por compatibilidade).
TTL_TOKEN_S = config.TTL_TOKEN_OIDC_S
TIMEOUT_CHAMADA_S = config.TIMEOUT_MCP_S

_log = obter_logger(__name__)


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------


def _resolver_url(url: str | None) -> str:
    return config.mcp_url(url)


def _resolver_oidc(usar_oidc: bool | None) -> bool:
    return config.mcp_use_oidc(usar_oidc)


def audience_de(url: str) -> str:
    """URL base (``esquema://host[:porta]``) usada como ``audience`` do ID token.

    Levanta ``ValueError`` se a URL não tiver esquema http(s) e host.
    """
    partes = urlsplit(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        raise ValueError("MCP_URL inválida: use http(s)://host[:porta]/mcp.")
    host = partes.hostname
    if ":" in host:  # IPv6
        host = f"[{host}]"
    porta = f":{partes.port}" if partes.port else ""
    return f"{partes.scheme}://{host}{porta}"


# ---------------------------------------------------------------------------
# OIDC
# ---------------------------------------------------------------------------


class ProvedorIdToken:
    """``header_provider`` do ``McpToolset`` com ID token OIDC em cache.

    O token vem de ``google.oauth2.id_token.fetch_id_token`` (metadata server
    no Cloud Run; credenciais de conta de serviço localmente) e é reaproveitado
    por ``ttl_s`` segundos. O token nunca é logado nem aparece no ``repr``.
    """

    def __init__(
        self,
        audience: str,
        ttl_s: float = TTL_TOKEN_S,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self.audience = audience
        self.ttl_s = ttl_s
        self._relogio = relogio
        self._token: str | None = None
        self._expira_em = 0.0
        self._trava = threading.Lock()

    def token(self) -> str:
        with self._trava:
            agora = self._relogio()
            if self._token is None or agora >= self._expira_em:
                self._token = id_token.fetch_id_token(Request(), self.audience)
                self._expira_em = agora + self.ttl_s
            return self._token

    def __call__(self, readonly_context: Any = None) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}"}

    def __repr__(self) -> str:
        return f"ProvedorIdToken(audience={self.audience!r})"


_provedores: dict[str, ProvedorIdToken] = {}
_trava_provedores = threading.Lock()


def _provedor_para(audience: str) -> ProvedorIdToken:
    """Um provedor por ``audience``, compartilhado entre chamadas (reaproveita o cache)."""
    with _trava_provedores:
        provedor = _provedores.get(audience)
        if provedor is None:
            provedor = _provedores[audience] = ProvedorIdToken(audience)
        return provedor


# ---------------------------------------------------------------------------
# Toolset e escopo
# ---------------------------------------------------------------------------


def criar_toolset(
    url: str | None = None,
    usar_oidc: bool | None = None,
    tool_filter: list[str] | None = None,
) -> McpToolset:
    """``McpToolset`` em streamable HTTP para ``url`` (padrão ``MCP_URL``).

    - ``usar_oidc`` (padrão ``MCP_USE_OIDC == "TRUE"``) liga o header com ID token.
    - ``tool_filter`` restringe as ferramentas expostas; ``None`` expõe todas.

    Não abre conexão: a sessão MCP só é criada no primeiro ``get_tools``.
    """
    url_final = _resolver_url(url)
    provedor = _provedor_para(audience_de(url_final)) if _resolver_oidc(usar_oidc) else None
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=url_final, timeout=TIMEOUT_CHAMADA_S),
        tool_filter=list(tool_filter) if tool_filter is not None else None,
        header_provider=provedor,
    )


def aplicar_escopo(args: Mapping[str, Any] | None, state: Mapping[str, Any]) -> dict[str, Any]:
    """Cópia de ``args`` com ``id_usuario`` e ``ate_anomes`` tirados do ``state``.

    Os valores do ``state`` sempre prevalecem sobre os enviados pelo modelo.
    Levanta ``ValueError`` se o ``state`` não tiver escopo válido; nesse caso
    **não** usa os valores de ``args``.
    """
    escopo = {
        CHAVE_ID_USUARIO: obter_id_usuario(state),
        CHAVE_ATE_ANOMES: obter_ate_anomes(state),
    }
    return {**dict(args or {}), **escopo}


# ---------------------------------------------------------------------------
# Chamada direta (sem LLM)
# ---------------------------------------------------------------------------


def _envelope_erro(codigo: str, mensagem: str) -> dict[str, Any]:
    return {"erro": {"codigo": codigo, "mensagem": mensagem}}


async def _chamar_mcp(
    url: str, cabecalhos: dict[str, str], nome: str, argumentos: dict[str, Any]
) -> CallToolResult:
    """Abre uma sessão MCP, chama ``nome`` e fecha a sessão."""
    timeout = httpx.Timeout(TIMEOUT_CHAMADA_S)
    async with create_mcp_http_client(headers=cabecalhos or None, timeout=timeout) as cliente:
        async with streamable_http_client(url, http_client=cliente) as (leitura, escrita, _):
            async with ClientSession(leitura, escrita) as sessao:
                await sessao.initialize()
                return await sessao.call_tool(nome, argumentos)


def _eh_envelope(valor: object) -> bool:
    return isinstance(valor, dict) and ("dados" in valor or "erro" in valor)


def _extrair_envelope(resultado: CallToolResult) -> dict[str, Any] | None:
    """Envelope §5 do resultado MCP, ou ``None`` se o resultado estiver fora do contrato."""
    if resultado.isError:
        return None
    estruturado = resultado.structuredContent
    if _eh_envelope(estruturado):
        return estruturado  # type: ignore[return-value]
    if isinstance(estruturado, dict) and _eh_envelope(estruturado.get("result")):
        return estruturado["result"]
    for parte in resultado.content:
        if isinstance(parte, TextContent):
            try:
                valor = json.loads(parte.text)
            except ValueError:
                continue
            if _eh_envelope(valor):
                return valor
    return None


def _latencia_ms(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)


async def chamar_ferramenta(
    nome: str,
    args: dict[str, Any],
    state: Mapping[str, Any],
    url: str | None = None,
    usar_oidc: bool | None = None,
) -> dict[str, Any]:
    """Chama a ferramenta MCP ``nome`` com o escopo do ``state`` e devolve o envelope §5.

    - Escopo ausente ou inválido no ``state``: envelope ``ENTRADA_INVALIDA``.
    - Falha de transporte, timeout, erro de protocolo ou resposta fora do
      contrato: envelope ``INDISPONIVEL``.
    - Envelopes de erro de negócio do MCP são devolvidos como vieram.
    """
    inicio = time.perf_counter()
    extra: dict[str, Any] = {"evento": "mcp_chamada", "ferramenta": nome}
    try:
        argumentos = aplicar_escopo(args, state)
    except ValueError:
        _log.warning(
            "Chamada MCP sem escopo válido no state.",
            extra={**extra, "erro_codigo": ERRO_ENTRADA_INVALIDA},
        )
        return _envelope_erro(ERRO_ENTRADA_INVALIDA, MSG_ESCOPO_INVALIDO)
    extra["ate_anomes"] = argumentos[CHAVE_ATE_ANOMES]

    try:
        url_final = _resolver_url(url)
        cabecalhos: dict[str, str] = {}
        if _resolver_oidc(usar_oidc):
            cabecalhos = _provedor_para(audience_de(url_final))()
        resultado = await asyncio.wait_for(
            _chamar_mcp(url_final, cabecalhos, nome, argumentos), timeout=TIMEOUT_CHAMADA_S
        )
    except Exception:
        _log.warning(
            "Falha de transporte na chamada MCP.",
            exc_info=True,
            extra={**extra, "erro_codigo": ERRO_INDISPONIVEL, "latencia_ms": _latencia_ms(inicio)},
        )
        return _envelope_erro(ERRO_INDISPONIVEL, MSG_INDISPONIVEL)

    envelope = _extrair_envelope(resultado)
    if envelope is None:
        _log.warning(
            "Resposta MCP fora do contrato.",
            extra={**extra, "erro_codigo": ERRO_INDISPONIVEL, "latencia_ms": _latencia_ms(inicio)},
        )
        return _envelope_erro(ERRO_INDISPONIVEL, MSG_INDISPONIVEL)

    extra["latencia_ms"] = _latencia_ms(inicio)
    erro = envelope.get("erro")
    if isinstance(erro, dict) and erro.get("codigo"):
        extra["erro_codigo"] = erro["codigo"]
    _log.info("Chamada MCP concluída.", extra=extra)
    return envelope
