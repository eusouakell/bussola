"""``RepositorioBigQuery``: implementação real de ``RepositorioFinanceiro`` (contratos §4).

Lê as tabelas de ``bussola_dados`` (contratos §3) em dois modos, com resultados
idênticos (ciclo 001 §3.3):

- ``query``: um job parametrizado por leitura (``@id_usuario``, ``@ate_anomes``,
  ``@desde_anomes``, ``@faixa_renda``, ``@macro``). O único texto interpolado no SQL é
  o nome do dataset, validado contra ``bussola_dados`` ou ``bussola_dados_<sufixo>``;
- ``memoria``: ``list_rows`` de todas as tabelas no construtor, indexadas por cliente,
  com o mesmo filtro e a mesma ordem aplicados em Python.

Garantias (constituição III e IV):

- ``id_usuario`` (UUID v4), ``ate_anomes``/``desde_anomes`` (202501–202512) e
  ``faixa_renda`` (:class:`FaixaRenda`) são validados **antes** de qualquer chamada ao
  cliente. Violações levantam ``ValueError`` sem ecoar o valor.
- A ordem das linhas é a mesma nos dois modos (ver :data:`SORT_KEYS`).
- ``recorrentes`` reaplica o critério de ≥ 3 meses distintos só sobre as linhas até o
  corte (plan.md D-05), para o futuro não vazar para o corte.
- Falhas do BigQuery viram
  :class:`~bussola_mcp.dominio.interfaces.RepositoryUnavailableError` (falha da porta,
  definida em ``interfaces.py`` e reexportada aqui), com mensagem genérica — sem SQL,
  projeto ou credencial.
"""

import re
import sys
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from bussola_mcp import config
from bussola_mcp.contratos import (
    ANOMES_MAX,
    ANOMES_MIN,
    MODELOS_TABELA,
    Categoria,
    EntradaCategoria,
    FaixaRenda,
    GastoCategoria,
    Parcela,
    PerfilMes,
    Recorrente,
    RefCoorte,
    anomes_valido,
    normalizar_id_usuario,
)
from bussola_mcp.dominio.interfaces import RepositoryUnavailableError

READ_MODES: tuple[str, ...] = ("query", "memoria")
MIN_RECURRENCE_MONTHS = 3

# Modo, dataset, região e projeto são configuração: os nomes das variáveis e os
# padrões vivem em :mod:`bussola_mcp.config`. Os aliases abaixo ficam para quem
# já importava estes nomes daqui.
DEFAULT_MODE = config.MODO_LEITURA_BQ_PADRAO
DEFAULT_DATASET = config.DATASET_DADOS_PADRAO
LOCATION = config.LOCAL_GCP_PADRAO
"""Região padrão. O valor efetivo vem de :func:`bussola_mcp.config.local_gcp`."""

ENV_MODE = config.VAR_MODO_LEITURA_BQ
ENV_DATASET = config.VAR_DATASET_DADOS
ENV_PROJECT = config.VAR_PROJETO_GCP

_DATASET_RE = re.compile(r"bussola_dados(?:_[a-z0-9_]{1,64})?")

# Tabela (sem dataset) → modelo de linha, a partir do contrato.
TABLE_MODELS: dict[str, type[BaseModel]] = {
    nome.split(".", 1)[1]: modelo for nome, modelo in MODELOS_TABELA.items()
}
CLIENT_TABLES: tuple[str, ...] = (
    "perfil_mensal",
    "gastos_categoria",
    "entradas_categoria",
    "recorrentes",
    "parcelas",
)

_BAND_ORDER = {faixa.value: indice for indice, faixa in enumerate(FaixaRenda)}

# Chave de ordem por tabela: as colunas do plano e, para desempate, a linha inteira.
SORT_KEYS: dict[str, Callable[[Any], tuple[Any, ...]]] = {
    "perfil_mensal": lambda r: (r.anomes,),
    "gastos_categoria": lambda r: (r.anomes, r.macro, r.micro, r.total, r.qtd),
    "entradas_categoria": lambda r: (r.anomes, r.macro, r.micro, r.total, r.qtd),
    "recorrentes": lambda r: (r.anomes, r.descr_norm, r.macro, r.micro, r.valor),
    "parcelas": lambda r: (r.anomes, r.descr, r.parcela_atual, r.parcela_total, r.vlr, r.macro),
    "categorias": lambda r: (r.macro, r.micro),
    "referencia_coorte": lambda r: (_BAND_ORDER.get(r.faixa_renda, len(_BAND_ORDER)), r.macro),
}


# ---------------------------------------------------------------------------
# Validação (sempre antes do cliente)
# ---------------------------------------------------------------------------


def validate_dataset(name: object) -> str:
    """Aceita só ``bussola_dados`` ou ``bussola_dados_<sufixo>``."""
    if not isinstance(name, str) or not _DATASET_RE.fullmatch(name):
        raise ValueError("dataset inválido: use bussola_dados ou bussola_dados_<sufixo>")
    return name


def validate_mode(mode: object) -> str:
    if mode not in READ_MODES:
        raise ValueError("modo de leitura inválido: use query ou memoria")
    return str(mode)


def _anomes(name: str, value: object) -> int:
    if not anomes_valido(value):
        raise ValueError(f"{name} deve estar entre {ANOMES_MIN} e {ANOMES_MAX}")
    return value  # type: ignore[return-value]


def _client_id(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("id_usuario deve ser um UUID v4")
    return normalizar_id_usuario(value)


def _band(value: object) -> str:
    if value not in _BAND_ORDER:
        raise ValueError("faixa_renda inválida")
    return str(value)


def _macro(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("macro inválida")
    return value


# ---------------------------------------------------------------------------
# SQL (constante, com o dataset validado como único texto variável)
# ---------------------------------------------------------------------------

DATASET_PLACEHOLDER = "{{dataset}}"
"""Marcador do dataset nos modelos de SQL (o mesmo de ``data/scripts/build_dados.py``)."""


def _columns(table: str) -> str:
    return ", ".join(TABLE_MODELS[table].model_fields)


# Colunas de cada tabela, na ordem dos campos do contrato.
PERFIL_COLUMNS = _columns("perfil_mensal")
GASTOS_COLUMNS = _columns("gastos_categoria")
ENTRADAS_COLUMNS = _columns("entradas_categoria")
RECORRENTES_COLUMNS = _columns("recorrentes")
PARCELAS_COLUMNS = _columns("parcelas")
CATEGORIAS_COLUMNS = _columns("categorias")
COORTE_COLUMNS = _columns("referencia_coorte")
BY_CLIENT = "WHERE id_usuario = @id_usuario AND anomes <= @ate_anomes"
DS = DATASET_PLACEHOLDER

QUERY_TEMPLATES: dict[str, str] = {
    "usuario_existe": (
        f"SELECT 1 AS existe FROM `{DS}.perfil_mensal` WHERE id_usuario = @id_usuario LIMIT 1"
    ),
    "perfil_mensal": (
        f"SELECT {PERFIL_COLUMNS} FROM `{DS}.perfil_mensal` {BY_CLIENT} ORDER BY anomes"
    ),
    "gastos_categoria": (
        f"SELECT {GASTOS_COLUMNS} FROM `{DS}.gastos_categoria` {BY_CLIENT} "
        "AND (@desde_anomes IS NULL OR anomes >= @desde_anomes) ORDER BY anomes, macro, micro"
    ),
    "entradas_categoria": (
        f"SELECT {ENTRADAS_COLUMNS} FROM `{DS}.entradas_categoria` {BY_CLIENT} "
        "ORDER BY anomes, macro, micro"
    ),
    "recorrentes": (
        f"SELECT {RECORRENTES_COLUMNS} FROM `{DS}.recorrentes` {BY_CLIENT} "
        "ORDER BY anomes, descr_norm, macro, micro"
    ),
    "parcelas": (
        f"SELECT {PARCELAS_COLUMNS} FROM `{DS}.parcelas` {BY_CLIENT} "
        "ORDER BY anomes, descr, parcela_atual, parcela_total, vlr"
    ),
    "categorias": f"SELECT {CATEGORIAS_COLUMNS} FROM `{DS}.categorias` ORDER BY macro, micro",
    "referencia_coorte": (
        f"SELECT {COORTE_COLUMNS} FROM `{DS}.referencia_coorte` "
        "WHERE faixa_renda = @faixa_renda AND (@macro IS NULL OR macro = @macro) ORDER BY macro"
    ),
}
"""SQL de cada leitura. Todo valor de entrada vai como parâmetro nomeado."""


def build_queries(dataset: str) -> dict[str, str]:
    """``QUERY_TEMPLATES`` com o marcador trocado pelo dataset validado."""
    ds = validate_dataset(dataset)
    return {nome: sql.replace(DATASET_PLACEHOLDER, ds) for nome, sql in QUERY_TEMPLATES.items()}


def _row_dict(row: Any) -> dict[str, Any]:
    """``google.cloud.bigquery.Row`` (ou mapeamento) → ``dict``."""
    return dict(row.items()) if hasattr(row, "items") else dict(row)


def _create_client(projeto: str | None) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=projeto, location=config.local_gcp())


def _as_tuple(row: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[Any, ...]:
    """Linha como tupla na ordem dos campos, com textos repetidos internados (memória)."""
    return tuple(sys.intern(v) if isinstance(v, str) else v for v in (row[f] for f in fields))


class RepositorioBigQuery:
    """``RepositorioFinanceiro`` sobre ``bussola_dados``, nos modos ``query`` e ``memoria``."""

    def __init__(
        self,
        modo: str | None = None,
        *,
        client: Any = None,
        dataset: str | None = None,
        projeto: str | None = None,
    ) -> None:
        self.modo = validate_mode(modo or config.modo_leitura_bq())
        self.dataset = validate_dataset(dataset or config.dataset_dados())
        self.local = config.local_gcp()
        self._queries = build_queries(self.dataset)
        self._categories: list[Categoria] | None = None
        # memoria: tabela → id_usuario → linhas como tuplas (ordem dos campos do modelo).
        self._by_client: dict[str, dict[str, list[tuple[Any, ...]]]] = {}
        self._shared: dict[str, list[tuple[Any, ...]]] = {}
        try:
            self._client = (
                client if client is not None else _create_client(projeto or config.projeto_gcp())
            )
            if self.modo == "memoria":
                self._load_memory()
        except RepositoryUnavailableError:
            raise
        except Exception as exc:
            raise RepositoryUnavailableError() from exc

    # -- acesso ao BigQuery --------------------------------------------------

    def _run_query(self, name: str, **params: tuple[str, Any]) -> list[dict[str, Any]]:
        from google.cloud import bigquery

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter(chave, tipo, valor)
                for chave, (tipo, valor) in params.items()
            ]
        )
        try:
            job = self._client.query(
                self._queries[name], job_config=job_config, location=self.local
            )
            return [_row_dict(row) for row in job.result()]
        except Exception as exc:
            raise RepositoryUnavailableError() from exc

    def _load_memory(self) -> None:
        for table, model in TABLE_MODELS.items():
            fields = tuple(model.model_fields)
            rows = self._client.list_rows(f"{self.dataset}.{table}")
            tuples = (_as_tuple(_row_dict(row), fields) for row in rows)
            if table in CLIENT_TABLES:
                index: dict[str, list[tuple[Any, ...]]] = defaultdict(list)
                id_pos = fields.index("id_usuario")
                for values in tuples:
                    index[str(values[id_pos]).lower()].append(values)
                self._by_client[table] = dict(index)
            else:
                self._shared[table] = list(tuples)

    # -- conversão, filtro e ordem (iguais nos dois modos) -------------------

    @staticmethod
    def _models[M: BaseModel](
        table: str, model: type[M], rows: Iterable[Mapping[str, Any]]
    ) -> list[M]:
        try:
            linhas = [model.model_validate(row) for row in rows]
        except Exception as exc:
            raise RepositoryUnavailableError() from exc
        return sorted(linhas, key=SORT_KEYS[table])

    def _memory_rows(self, table: str, id_usuario: str | None = None) -> list[dict[str, Any]]:
        """Linhas carregadas no modo ``memoria``: as do cliente ou as da tabela comum."""
        fields = tuple(TABLE_MODELS[table].model_fields)
        if id_usuario is None:
            stored = self._shared[table]
        else:
            stored = self._by_client[table].get(id_usuario, [])
        return [dict(zip(fields, values, strict=True)) for values in stored]

    def _client_rows[M: BaseModel](
        self,
        table: str,
        model: type[M],
        id_usuario: object,
        ate_anomes: object,
        desde_anomes: object = None,
    ) -> list[M]:
        uid = _client_id(id_usuario)
        ate = _anomes("ate_anomes", ate_anomes)
        desde = None if desde_anomes is None else _anomes("desde_anomes", desde_anomes)
        if self.modo == "query":
            params: dict[str, tuple[str, Any]] = {
                "id_usuario": ("STRING", uid),
                "ate_anomes": ("INT64", ate),
            }
            if table == "gastos_categoria":
                params["desde_anomes"] = ("INT64", desde)
            rows = self._run_query(table, **params)
        else:
            rows = self._memory_rows(table, uid)
        linhas = self._models(table, model, rows)
        return [
            linha
            for linha in linhas
            if linha.id_usuario.lower() == uid
            and linha.anomes <= ate
            and (desde is None or linha.anomes >= desde)
        ]

    # -- RepositorioFinanceiro -----------------------------------------------

    def usuario_existe(self, id_usuario: str) -> bool:
        uid = _client_id(id_usuario)
        if self.modo == "query":
            return bool(self._run_query("usuario_existe", id_usuario=("STRING", uid)))
        return bool(self._by_client["perfil_mensal"].get(uid))

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        return self._client_rows("perfil_mensal", PerfilMes, id_usuario, ate_anomes)

    def gastos_categoria(
        self, id_usuario: str, ate_anomes: int, desde_anomes: int | None = None
    ) -> list[GastoCategoria]:
        return self._client_rows(
            "gastos_categoria", GastoCategoria, id_usuario, ate_anomes, desde_anomes
        )

    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]:
        return self._client_rows("entradas_categoria", EntradaCategoria, id_usuario, ate_anomes)

    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]:
        linhas = self._client_rows("recorrentes", Recorrente, id_usuario, ate_anomes)
        meses: dict[str, set[int]] = defaultdict(set)
        for linha in linhas:
            meses[linha.descr_norm].add(linha.anomes)
        return [linha for linha in linhas if len(meses[linha.descr_norm]) >= MIN_RECURRENCE_MONTHS]

    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]:
        return self._client_rows("parcelas", Parcela, id_usuario, ate_anomes)

    def categorias(self) -> list[Categoria]:
        """Seed estático: lido uma vez por instância (plan.md D-08)."""
        if self._categories is None:
            if self.modo == "query":
                rows = self._run_query("categorias")
            else:
                rows = self._memory_rows("categorias")
            self._categories = self._models("categorias", Categoria, rows)
        return list(self._categories)

    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]:
        faixa = _band(faixa_renda)
        alvo = _macro(macro)
        if self.modo == "query":
            rows = self._run_query(
                "referencia_coorte",
                faixa_renda=("STRING", faixa),
                macro=("STRING", alvo),
            )
        else:
            rows = self._memory_rows("referencia_coorte")
        linhas = self._models("referencia_coorte", RefCoorte, rows)
        return [
            linha
            for linha in linhas
            if linha.faixa_renda == faixa and (alvo is None or linha.macro == alvo)
        ]
