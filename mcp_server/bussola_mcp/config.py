"""Fonte única de configuração do MCP server (contratos §7, constituição VII).

Tudo que varia por **ambiente** ou por **deploy** é lido aqui, e só aqui: projeto
e região do GCP, dataset e modo de leitura do BigQuery, modo fake, porta HTTP,
nível de log, modelo de embedding, backend do RAG e os caminhos das fixtures e do
índice do RAG. Nenhum outro módulo de ``bussola_mcp`` chama ``os.environ``.

O que **não** é configuração continua fora daqui, de propósito:

- constantes de **contrato** (``FERRAMENTAS``, ``TABELAS_FERRAMENTA``,
  ``CORTES_GOLDEN``, ``ID_ANCORA``/``ID_CONTROLE``,
  ``ENTRADA_CANONICA_SIMULACAO``, faixas de ``anomes``) ficam em
  :mod:`bussola_mcp.contratos` e mudam só por PR ``contracts:``;
- **limiares de negócio** (``MAX_TERM_MONTHS``, ``MAX_OPPORTUNITIES``,
  ``INCOME_BAND_LIMITS``, ``RegrasMarco``, ``RegrasCenario``) ficam no domínio;
- a **calibração** do RAG (BM25 ``k1``/``b``, coberturas mínimas, ``min_score``)
  fica nos adaptadores de :mod:`bussola_mcp.rag`, medida em
  ``eval/rag/RESULTADOS.md``: é parâmetro de algoritmo, não de ambiente.

Regras deste módulo:

- **Nenhum segredo.** Só nomes de variável e defaults não secretos. A chave do
  Gemini (``GOOGLE_API_KEY``) é lida pelo ``genai.Client()`` direto do ambiente,
  nunca por este módulo, e nunca é registrada nem impressa (constituição VII).
- **Leitura tardia.** Cada valor é uma função que lê ``os.environ`` na chamada,
  não no import: os testes trocam o ambiente com ``monkeypatch``.
- **Default explícito.** Todo valor tem default não secreto, e o conjunto dos
  defaults sobe o serviço em modo fake sem nenhuma variável definida.

Os nomes das variáveis são exatamente os de ``contracts/env.example`` e os
injetados por ``deploy/helm/bussola/values.yaml`` no serviço ``mcp``.
"""

import os
from pathlib import Path

__all__ = [
    "BACKEND_RAG_PADRAO",
    "DATASET_DADOS_PADRAO",
    "DIMENSAO_EMBEDDING_PADRAO",
    "DIR_INDICE_RAG",
    "LOCAL_GCP_PADRAO",
    "MODELO_EMBEDDING_PADRAO",
    "MODO_LEITURA_BQ_PADRAO",
    "NIVEL_LOG_PADRAO",
    "PORTA_PADRAO",
    "RAIZ_REPOSITORIO",
    "VALORES_VERDADEIROS",
    "VAR_BACKEND_RAG",
    "VAR_DATASET_DADOS",
    "VAR_FAKES",
    "VAR_LOCAL_GCP",
    "VAR_MODELO_EMBEDDING",
    "VAR_MODO_LEITURA_BQ",
    "VAR_NIVEL_LOG",
    "VAR_PORTA",
    "VAR_PROJETO_GCP",
    "backend_rag",
    "dataset_dados",
    "dir_fixtures_padrao",
    "fakes_ligados",
    "local_gcp",
    "modelo_embedding",
    "modo_leitura_bq",
    "nivel_log",
    "porta_http",
    "projeto_gcp",
]

# ---------------------------------------------------------------------------
# Nomes das variáveis de ambiente (contracts/env.example)
# ---------------------------------------------------------------------------

VAR_PROJETO_GCP = "GOOGLE_CLOUD_PROJECT"
"""Projeto do GCP onde está ``bussola_dados``. Injetado pelo deploy; vazio em teste."""

VAR_LOCAL_GCP = "GOOGLE_CLOUD_LOCATION"
"""Região dos jobs e das tabelas do BigQuery."""

VAR_DATASET_DADOS = "BQ_DATASET_DADOS"
"""Dataset lido pelo ``RepositorioBigQuery`` (contratos §3)."""

VAR_MODO_LEITURA_BQ = "BQ_MODO_LEITURA"
"""``query`` (job parametrizado) ou ``memoria`` (``list_rows``, Plano B)."""

VAR_FAKES = "BUSSOLA_FAKES"
"""``TRUE``/``1`` liga fakes e fixtures, sem nenhuma chamada ao GCP."""

VAR_PORTA = "PORT"
"""Porta HTTP do servidor MCP. O Cloud Run define esta variável."""

VAR_NIVEL_LOG = "LOG_LEVEL"
"""Nível do logger raiz (``DEBUG``, ``INFO``, ``WARNING``...)."""

VAR_MODELO_EMBEDDING = "EMBEDDING_MODEL"
"""Modelo de embedding do RAG, validado por ``deploy/smoke_modelos.py``."""

VAR_BACKEND_RAG = "RAG_BACKEND"
"""Busca do RAG: ``lexico`` (sem GCP) ou ``numpy`` (embeddings, Plano A)."""

# ---------------------------------------------------------------------------
# Defaults (não secretos; sobem o serviço em modo fake sem nenhuma variável)
# ---------------------------------------------------------------------------

LOCAL_GCP_PADRAO = "us-central1"
"""Região da PoC (constituição, Restrições de plataforma)."""

DATASET_DADOS_PADRAO = "bussola_dados"
"""Dataset canônico de leitura (contratos §3)."""

MODO_LEITURA_BQ_PADRAO = "query"
"""Modo canônico: um job parametrizado por leitura."""

PORTA_PADRAO = 8080
"""Porta do MCP quando ``PORT`` não vem do ambiente."""

NIVEL_LOG_PADRAO = "INFO"
"""Nível de log padrão (contratos §9)."""

MODELO_EMBEDDING_PADRAO = "gemini-embedding-001"
"""Modelo de embedding validado no ciclo 000."""

DIMENSAO_EMBEDDING_PADRAO = 768
"""Dimensão de saída pedida ao modelo de embedding. Sem variável de ambiente: o
índice versionado grava modelo e dimensão no ``manifesto.json``, e o
``BuscadorNumpy`` recusa subir se divergirem."""

BACKEND_RAG_PADRAO = "lexico"
"""Backend de busca padrão: BM25 puro Python, sem GCP (Q-17 do 000)."""

VALORES_VERDADEIROS = frozenset({"TRUE", "1"})
"""Valores que ligam uma bandeira de ambiente, sem diferenciar maiúsculas."""

# ---------------------------------------------------------------------------
# Leitura tipada
# ---------------------------------------------------------------------------


def _texto(variavel: str, padrao: str) -> str:
    """Texto do ambiente sem espaços nas pontas; vazio ou ausente cai no padrão."""
    return os.environ.get(variavel, "").strip() or padrao


def _texto_opcional(variavel: str) -> str | None:
    """Texto do ambiente, ou ``None`` quando ausente ou vazio (sem padrão)."""
    return os.environ.get(variavel, "").strip() or None


def _inteiro(variavel: str, padrao: int) -> int:
    """Inteiro do ambiente; vazio ou ausente cai no padrão.

    Um valor não numérico levanta ``ValueError``: é erro de deploy, e falhar no
    startup é melhor que subir numa porta que ninguém pediu.
    """
    bruto = os.environ.get(variavel, "").strip()
    return int(bruto) if bruto else padrao


def _bandeira(variavel: str) -> bool:
    """``True`` só para :data:`VALORES_VERDADEIROS`, sem diferenciar maiúsculas."""
    return os.environ.get(variavel, "").strip().upper() in VALORES_VERDADEIROS


# ---------------------------------------------------------------------------
# Valores
# ---------------------------------------------------------------------------


def projeto_gcp() -> str | None:
    """``GOOGLE_CLOUD_PROJECT``, ou ``None`` para o cliente inferir do ambiente (ADC)."""
    return _texto_opcional(VAR_PROJETO_GCP)


def local_gcp() -> str:
    """``GOOGLE_CLOUD_LOCATION``, padrão :data:`LOCAL_GCP_PADRAO`."""
    return _texto(VAR_LOCAL_GCP, LOCAL_GCP_PADRAO)


def dataset_dados() -> str:
    """``BQ_DATASET_DADOS``, padrão :data:`DATASET_DADOS_PADRAO`.

    O formato é validado por ``repositorio_bq.validate_dataset`` antes de entrar
    no SQL: este módulo só lê o valor, nunca o interpola.
    """
    return _texto(VAR_DATASET_DADOS, DATASET_DADOS_PADRAO)


def modo_leitura_bq() -> str:
    """``BQ_MODO_LEITURA``, padrão :data:`MODO_LEITURA_BQ_PADRAO`.

    O valor é validado por ``repositorio_bq.validate_mode``.
    """
    return _texto(VAR_MODO_LEITURA_BQ, MODO_LEITURA_BQ_PADRAO)


def fakes_ligados() -> bool:
    """``BUSSOLA_FAKES`` ligado (``TRUE`` ou ``1``, sem diferenciar maiúsculas)."""
    return _bandeira(VAR_FAKES)


def porta_http() -> int:
    """``PORT``, padrão :data:`PORTA_PADRAO`."""
    return _inteiro(VAR_PORTA, PORTA_PADRAO)


def nivel_log() -> str:
    """``LOG_LEVEL`` em maiúsculas, padrão :data:`NIVEL_LOG_PADRAO`.

    Só o texto: quem instala o logger confere se é um nível conhecido
    (:func:`bussola_mcp.logging_json.configurar_logging`).
    """
    return _texto(VAR_NIVEL_LOG, NIVEL_LOG_PADRAO).upper()


def modelo_embedding() -> str | None:
    """``EMBEDDING_MODEL``, ou ``None`` quando não configurado.

    Sem valor, quem decide é o consumidor: o ``BuscadorNumpy`` usa o modelo do
    manifesto do índice e o indexador usa :data:`MODELO_EMBEDDING_PADRAO`.
    """
    return _texto_opcional(VAR_MODELO_EMBEDDING)


def backend_rag() -> str:
    """``RAG_BACKEND``, padrão :data:`BACKEND_RAG_PADRAO`."""
    return _texto(VAR_BACKEND_RAG, BACKEND_RAG_PADRAO)


# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------

RAIZ_REPOSITORIO = Path(__file__).resolve().parents[2]
"""``config.py`` → ``bussola_mcp`` → ``mcp_server`` → raiz do repositório."""

DIR_INDICE_RAG = Path(__file__).resolve().parent / "rag" / "indice"
"""Índice versionado do RAG (``trechos.jsonl``, ``embeddings.npy``,
``manifesto.json``). Fica no repositório, não em dataset (Q-17 do 000)."""


def dir_fixtures_padrao() -> Path:
    """``<raiz do repositório>/contracts/fixtures`` (contratos §8)."""
    return RAIZ_REPOSITORIO / "contracts" / "fixtures"
