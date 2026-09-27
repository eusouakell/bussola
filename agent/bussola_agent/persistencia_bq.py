"""``RegistroBigQuery``: :class:`RegistroApp` over BigQuery streaming insert (005).

- Rows come from ``model.model_dump(mode="json")`` and go to
  ``{GOOGLE_CLOUD_PROJECT}.{BQ_DATASET_APP}.{tabela}`` through
  ``insert_rows_json``. No SQL is built from text: the only query
  (:data:`PLAN_QUERY`, in :meth:`RegistroBigQuery.obter_plano`) is a constant
  that takes ``@plano_id`` as a parameter and reads the dataset from the job's
  ``default_dataset``. Project and dataset names are validated first.
- The BigQuery client is a port (:class:`BigQueryClient`, the subset of
  ``google.cloud.bigquery.Client`` used here). It is created on first use,
  so importing or building the registry never opens the network.
- Failures raise :class:`RegistryWriteError` with a message that never echoes
  row values.
- :func:`build_registry` picks the fake (``RegistroEmMemoria``) or BigQuery
  from ``BUSSOLA_FAKES``. :func:`default_registry` is the process-wide
  instance shared by governance (005) and follow-up (006).
"""

import json
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel

from bussola_agent.config import (
    DATASET_APP_PADRAO,
    dataset_app,
    fakes_habilitados,
    projeto_gcp,
)
from bussola_agent.logging_json import obter_logger
from bussola_agent.persistencia import (
    Acompanhamento,
    Consentimento,
    EventoAuditoria,
    Plano,
    RegistroApp,
    RegistroEmMemoria,
)

DEFAULT_DATASET = DATASET_APP_PADRAO
# Values of ``BUSSOLA_FAKES`` that turn the fakes off. Anything else (including
# unset) keeps the fake, so a misconfigured process never writes by accident.

_PROJECT_RE = re.compile(r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
_DATASET_RE = re.compile(r"^[A-Za-z0-9_]{1,1024}$")

# Columns of ``planos`` (same order as the DDL). A test keeps them equal to ``Plano``.
PLAN_COLUMNS: tuple[str, ...] = (
    "plano_id",
    "session_id",
    "id_usuario",
    "objetivo",
    "valor_alvo",
    "prazo_meses",
    "cenario",
    "aporte_mensal",
    "ate_anomes",
    "criado_em",
)
# The only query. ``planos`` resolves against the job's ``default_dataset``.
PLAN_QUERY = (
    "SELECT plano_id, session_id, id_usuario, objetivo, valor_alvo, prazo_meses, cenario, "
    "aporte_mensal, ate_anomes, criado_em FROM planos "
    "WHERE plano_id = @plano_id ORDER BY criado_em DESC LIMIT 1"
)

_log = obter_logger(__name__)


class RegistryWriteError(RuntimeError):
    """BigQuery rejected or failed a write. The message never carries row values."""


class BigQueryClient(Protocol):
    """Port: the subset of ``google.cloud.bigquery.Client`` used by the registry."""

    def insert_rows_json(
        self, table: str, json_rows: Sequence[Mapping[str, Any]], **kwargs: Any
    ) -> Sequence[Mapping[str, Any]]: ...

    def query(self, query: str, job_config: Any = None, **kwargs: Any) -> Any: ...


def fakes_enabled(env: Mapping[str, str] | None = None) -> bool:
    """``True`` unless ``BUSSOLA_FAKES`` explicitly turns the fakes off."""
    return fakes_habilitados(env)


def _default_client_factory(project: str) -> BigQueryClient:
    from google.cloud import bigquery

    return bigquery.Client(project=project)


def _plan_query_config(project: str, dataset: str, plano_id: str) -> Any:
    from google.cloud import bigquery

    return bigquery.QueryJobConfig(
        default_dataset=bigquery.DatasetReference(project, dataset),
        query_parameters=[bigquery.ScalarQueryParameter("plano_id", "STRING", plano_id)],
    )


class RegistroBigQuery:
    """:class:`RegistroApp` that writes to ``BQ_DATASET_APP`` via streaming insert."""

    def __init__(
        self,
        client: BigQueryClient | None = None,
        project: str | None = None,
        dataset: str | None = None,
        client_factory: Callable[[str], BigQueryClient] = _default_client_factory,
        query_config_factory: Callable[[str, str, str], Any] = _plan_query_config,
    ) -> None:
        project = project or projeto_gcp()
        dataset = dataset or dataset_app()
        if not _PROJECT_RE.fullmatch(project):
            raise ValueError("GOOGLE_CLOUD_PROJECT ausente ou inválido.")
        if not _DATASET_RE.fullmatch(dataset):
            raise ValueError("BQ_DATASET_APP inválido.")
        self.project = project
        self.dataset = dataset
        self._client = client
        self._client_factory = client_factory
        self._query_config_factory = query_config_factory
        self._lock = threading.Lock()
        # Plans written by this process: ``obter_plano`` works without
        # ``bigquery.jobUser`` (Plano B) and right after the insert.
        self._plans: dict[str, Plano] = {}

    # -- infrastructure ---------------------------------------------------

    def table_id(self, tabela: str) -> str:
        return f"{self.project}.{self.dataset}.{tabela}"

    def _get_client(self) -> BigQueryClient:
        with self._lock:
            if self._client is None:
                self._client = self._client_factory(self.project)
            return self._client

    def _insert(self, tabela: str, row: BaseModel, row_id: str) -> None:
        data = row.model_dump(mode="json")
        if "resumo" in data:
            # JSON columns go through the streaming API as serialized text.
            data["resumo"] = json.dumps(data["resumo"], ensure_ascii=False)
        try:
            errors = self._get_client().insert_rows_json(
                self.table_id(tabela), [data], row_ids=[row_id]
            )
        except Exception as exc:
            raise RegistryWriteError(f"Falha ao gravar em {tabela}.") from exc
        if errors:
            raise RegistryWriteError(f"O BigQuery recusou a linha de {tabela}.")

    # -- RegistroApp ------------------------------------------------------

    def registrar_plano(self, plano: Plano) -> str:
        _require(plano, Plano)
        # A plan may get new versions (006 adjusts it): the insert id is per version.
        self._insert("planos", plano, f"{plano.plano_id}:{plano.criado_em.isoformat()}")
        self._plans[plano.plano_id] = plano.model_copy(deep=True)
        return plano.plano_id

    def registrar_consentimento(self, c: Consentimento) -> str:
        _require(c, Consentimento)
        self._insert("consentimentos", c, c.consent_id)
        return c.consent_id

    def registrar_evento(self, e: EventoAuditoria) -> str:
        _require(e, EventoAuditoria)
        self._insert("auditoria", e, e.evento_id)
        return e.evento_id

    def registrar_acompanhamento(self, a: Acompanhamento) -> None:
        _require(a, Acompanhamento)
        self._insert("acompanhamento", a, f"{a.plano_id}:{a.anomes}:{a.ts.isoformat()}")

    def obter_plano(self, plano_id: str) -> Plano | None:
        """Latest version of the plan: local cache first, then a parameterized query."""
        if not isinstance(plano_id, str) or not plano_id:
            return None
        cached = self._plans.get(plano_id)
        if cached is not None:
            return cached.model_copy(deep=True)
        config = self._query_config_factory(self.project, self.dataset, plano_id)
        try:
            job = self._get_client().query(PLAN_QUERY, job_config=config)
            rows = list(job.result())
        except Exception as exc:
            raise RegistryWriteError("Falha ao ler o plano.") from exc
        if not rows:
            return None
        return Plano.model_validate({col: rows[0][col] for col in PLAN_COLUMNS})


def _require(value: object, kind: type[BaseModel]) -> None:
    if not isinstance(value, kind):
        raise TypeError(f"Esperado um {kind.__name__}.")


def build_registry(env: Mapping[str, str] | None = None) -> RegistroApp:
    """``RegistroEmMemoria`` with the fakes on; ``RegistroBigQuery`` otherwise."""
    if fakes_enabled(env):
        return RegistroEmMemoria()
    return RegistroBigQuery(project=projeto_gcp(env), dataset=dataset_app(env))


_default: RegistroApp | None = None
_default_lock = threading.Lock()


def default_registry() -> RegistroApp:
    """Process-wide registry, built on first use by :func:`build_registry`."""
    global _default
    with _default_lock:
        if _default is None:
            _default = build_registry()
            _log.info(
                "Registro da aplicação criado.",
                extra={"evento": f"registro_{type(_default).__name__}"},
            )
        return _default


def set_default_registry(registry: RegistroApp | None) -> None:
    """Replaces (or with ``None``, resets) the process-wide registry. For tests."""
    global _default
    with _default_lock:
        _default = registry
