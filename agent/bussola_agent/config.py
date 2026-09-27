"""Fonte única da configuração de ambiente e de deploy do agente.

O que mora aqui é **configuração**: o que varia por ambiente ou por deploy —
URL do MCP, projeto do GCP, nome do modelo e a cadeia de fallback, dataset de
aplicação, flags (``BUSSOLA_FAKES``), template do Model Armor, timeouts,
limites de retentativa, ``LOG_LEVEL`` e o escopo âncora da PoC.

O que **não** mora aqui, por decisão de contrato (contratos §5, §6 e §9):
chaves de ``session.state`` (:mod:`bussola_agent.estado`), ``FERRAMENTAS_MCP``,
códigos de erro, ordens reservadas de callback, faixas de validação (UUID v4,
202501–202512), textos ao cliente e regras de guardrail.

Regras deste módulo:

- **só stdlib**: nada de ADK, genai, BigQuery ou httpx, para que a
  configuração não arraste framework nenhum (a construção dos objetos de
  framework fica em quem os usa);
- **leitura no momento do uso**: cada valor é uma função que lê o ambiente na
  chamada, nunca no import. Assim ``monkeypatch.setenv`` nos testes e uma
  variável definida depois do import continuam valendo;
- **``env`` injetável**: toda função aceita um ``Mapping`` no lugar de
  ``os.environ``, para teste e para composição explícita;
- **default explícito**: o par nome/default de cada variável está na tabela
  abaixo e casa com ``contracts/env.example``;
- **nenhum segredo**: ``GOOGLE_API_KEY`` (``gemini-api-key``) e qualquer outro
  segredo não são lidos, nem expostos, nem logados aqui (constituição VII).
  Quem lê a chave do Gemini é o SDK do ``google-genai``, direto do ambiente.

Variáveis lidas por este módulo:

======================  ==================================  ==================
variável                acessor                             default
======================  ==================================  ==================
``MCP_URL``             :func:`mcp_url`                     ``MCP_URL_PADRAO``
``MCP_USE_OIDC``        :func:`mcp_use_oidc`                ``FALSE``
``BUSSOLA_MODEL``       :func:`modelo_principal`            ``MODELO_PADRAO``
``GOOGLE_CLOUD_PROJECT``:func:`projeto_gcp`                 ``""``
``BQ_DATASET_APP``      :func:`dataset_app`                 ``DATASET_APP_PADRAO``
``BUSSOLA_FAKES``       :func:`fakes_habilitados`           ``TRUE``
``MODEL_ARMOR_TEMPLATE``:func:`template_model_armor`        ``""``
``ANCHOR_USER_ID``      :func:`anchor_user_id`              ``ANCHOR_USER_ID_PADRAO``
``REPLAY_START_ANOMES`` :func:`replay_start_anomes`         ``REPLAY_START_PADRAO``
``LOG_LEVEL``           :func:`nivel_de_log`                ``INFO``
======================  ==================================  ==================

``GOOGLE_CLOUD_LOCATION`` e ``GOOGLE_GENAI_USE_VERTEXAI`` aparecem em
``contracts/env.example`` e no chart, mas nenhum código do agente os lê: quem
os consome é o SDK do ``google-genai``. Por isso não têm acessor aqui.
"""

import os
from collections.abc import Mapping

# ---------------------------------------------------------------------------
# Defaults de ambiente
# ---------------------------------------------------------------------------

MCP_URL_PADRAO = "http://localhost:8080/mcp"
"""MCP local do ``make mcp`` (mock do 000)."""

MODELO_PADRAO = "gemini-3.8-flash"
"""Flash validado por ``deploy/smoke_modelos.py`` (``BUSSOLA_MODEL``)."""

MODELOS_FLASH: tuple[str, ...] = ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash")
"""Cadeia Flash que respondeu no smoke (specs/000-fundacao-contratos/modelos.md)."""

DATASET_APP_PADRAO = "bussola_app"
"""Dataset de escrita do agente. Os testes gravam em ``bussola_app_dev``."""

ANCHOR_USER_ID_PADRAO = "36a21505-d6d4-42d3-b319-d51a133c7269"
"""Cliente âncora sintético da PoC (``ANCHOR_USER_ID``)."""

REPLAY_START_PADRAO = 202506
"""Mês inicial do replay temporal (``REPLAY_START_ANOMES``)."""

NIVEL_DE_LOG_PADRAO = "INFO"

FAKES_DESLIGADO = frozenset({"FALSE", "0", "NO", "NAO", "NÃO", "OFF"})
"""Valores de ``BUSSOLA_FAKES`` que desligam os fakes. Qualquer outro os mantém."""

# ---------------------------------------------------------------------------
# Timeouts e limites de retentativa (variam por deploy, não por requisição)
# ---------------------------------------------------------------------------

TIMEOUT_MCP_S = 30.0
"""Tempo máximo de uma chamada MCP (inclui partida a frio do Cloud Run)."""

TTL_TOKEN_OIDC_S = 45 * 60
"""Validade do ID token em cache (o token do Google expira em 1 hora)."""

TIMEOUT_MODEL_ARMOR_S = 3.0
"""Tempo máximo de uma checagem no Model Armor; estourar cai nas regras."""

RETENTATIVA_TENTATIVAS = 2
"""Uma retentativa no mesmo modelo (408, 429 e 5xx) antes de passar ao próximo."""

RETENTATIVA_ESPERA_INICIAL_S = 1.0
RETENTATIVA_ESPERA_MAXIMA_S = 4.0


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------


def _ambiente(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _texto(nome: str, padrao: str, env: Mapping[str, str] | None) -> str:
    return (_ambiente(env).get(nome) or padrao).strip()


def mcp_url(url: str | None = None, env: Mapping[str, str] | None = None) -> str:
    """URL do MCP: o argumento, senão ``MCP_URL``, senão :data:`MCP_URL_PADRAO`."""
    return (url or _ambiente(env).get("MCP_URL") or MCP_URL_PADRAO).strip()


def mcp_use_oidc(usar_oidc: bool | None = None, env: Mapping[str, str] | None = None) -> bool:
    """``True`` só com ``MCP_USE_OIDC=TRUE`` (default ``FALSE``); o argumento tem prioridade."""
    if usar_oidc is not None:
        return bool(usar_oidc)
    return _texto("MCP_USE_OIDC", "FALSE", env).upper() == "TRUE"


def modelo_principal(env: Mapping[str, str] | None = None) -> str:
    """Primeiro modelo da cadeia (``BUSSOLA_MODEL``, default :data:`MODELO_PADRAO`)."""
    return _texto("BUSSOLA_MODEL", MODELO_PADRAO, env)


def cadeia_de_modelos(
    principal: str | None = None, env: Mapping[str, str] | None = None
) -> tuple[str, ...]:
    """``principal`` (ou ``BUSSOLA_MODEL``) seguido dos outros Flash, sem repetir."""
    primeiro = principal or modelo_principal(env)
    return (primeiro, *(m for m in MODELOS_FLASH if m != primeiro))


def projeto_gcp(env: Mapping[str, str] | None = None) -> str:
    """``GOOGLE_CLOUD_PROJECT``, ou ``""`` quando ausente (quem exige valida)."""
    return _texto("GOOGLE_CLOUD_PROJECT", "", env)


def dataset_app(env: Mapping[str, str] | None = None) -> str:
    """``BQ_DATASET_APP``, default :data:`DATASET_APP_PADRAO`."""
    return _texto("BQ_DATASET_APP", DATASET_APP_PADRAO, env)


def fakes_habilitados(env: Mapping[str, str] | None = None) -> bool:
    """``True`` a menos que ``BUSSOLA_FAKES`` esteja em :data:`FAKES_DESLIGADO`."""
    valor = _ambiente(env).get("BUSSOLA_FAKES", "TRUE")
    return valor.strip().upper() not in FAKES_DESLIGADO


def template_model_armor(env: Mapping[str, str] | None = None) -> str:
    """``MODEL_ARMOR_TEMPLATE``; vazio significa guardrail só por regras."""
    return _texto("MODEL_ARMOR_TEMPLATE", "", env)


def anchor_user_id(env: Mapping[str, str] | None = None) -> str:
    """``ANCHOR_USER_ID``, default :data:`ANCHOR_USER_ID_PADRAO`. Quem usa valida o UUID."""
    return _texto("ANCHOR_USER_ID", ANCHOR_USER_ID_PADRAO, env)


def replay_start_anomes(env: Mapping[str, str] | None = None) -> int:
    """``REPLAY_START_ANOMES`` como ``int``, default :data:`REPLAY_START_PADRAO`.

    Levanta ``ValueError`` se o valor não for inteiro; quem chama valida a
    faixa 202501–202512 (contratos §2, regra de domínio).
    """
    return int(_texto("REPLAY_START_ANOMES", str(REPLAY_START_PADRAO), env))


def nivel_de_log(env: Mapping[str, str] | None = None) -> str:
    """``LOG_LEVEL`` em maiúsculas, default ``INFO``."""
    return _texto("LOG_LEVEL", NIVEL_DE_LOG_PADRAO, env).upper()
