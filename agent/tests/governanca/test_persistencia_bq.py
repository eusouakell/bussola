"""``RegistroBigQuery`` with a fake client (port): no network, no GCP."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from governance_support import ANCHOR

from bussola_agent import persistencia_bq
from bussola_agent.persistencia import (
    Acompanhamento,
    Consentimento,
    EventoAuditoria,
    Plano,
    RegistroEmMemoria,
)
from bussola_agent.persistencia_bq import (
    PLAN_COLUMNS,
    PLAN_INSERT,
    PLAN_PARAM_TYPES,
    PLAN_QUERY,
    RegistroBigQuery,
    RegistryWriteError,
    build_registry,
    fakes_enabled,
)

TS = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
PROJECT = "projeto-teste"


class FakeClient:
    def __init__(self, errors: list | None = None, rows: list | None = None) -> None:
        self.inserts: list[tuple[str, list[dict], list[str]]] = []
        self.queries: list[tuple[str, Any]] = []
        self.errors = errors or []
        self.rows = rows or []
        self.fail = False

    def insert_rows_json(self, table: str, json_rows: list, **kwargs: Any) -> list:
        if self.fail:
            raise ConnectionError(f"sem rede para {json_rows}")
        self.inserts.append((table, list(json_rows), list(kwargs.get("row_ids") or [])))
        return self.errors

    def query(self, query: str, job_config: Any = None, **kwargs: Any) -> Any:
        if self.fail:
            raise ConnectionError(f"sem rede para {job_config}")
        self.queries.append((query, job_config))
        rows = self.rows

        class Job:
            def result(self) -> list:
                return rows

        return Job()


def _registry(client: FakeClient, dataset: str = "bussola_app_dev") -> RegistroBigQuery:
    return RegistroBigQuery(
        client=client,
        project=PROJECT,
        dataset=dataset,
        query_config_factory=lambda project, ds, plano_id: {
            "default_dataset": f"{project}.{ds}",
            "plano_id": plano_id,
        },
        insert_config_factory=lambda project, ds, plano: {
            "default_dataset": f"{project}.{ds}",
            "plano": plano.model_dump(mode="json"),
        },
    )


def _plan() -> Plano:
    return Plano(
        session_id="s-1",
        id_usuario=ANCHOR,
        objetivo="Reserva",
        valor_alvo=30000.0,
        prazo_meses=24,
        cenario="equilibrado",
        aporte_mensal=1250.0,
        ate_anomes=202506,
        criado_em=TS,
    )


def _consent() -> Consentimento:
    return Consentimento(
        session_id="s-1", acao="criar_plano", decisao="aceito", texto_apresentado="t", ts=TS
    )


def test_plan_columns_match_the_model() -> None:
    assert PLAN_COLUMNS == tuple(Plano.model_fields)
    for column in PLAN_COLUMNS:
        assert column in PLAN_QUERY
        assert column in PLAN_INSERT
        assert f"@{column}" in PLAN_INSERT
    assert "@plano_id" in PLAN_QUERY
    assert len(PLAN_PARAM_TYPES) == len(PLAN_COLUMNS)


def test_insert_plan_runs_the_constant_insert() -> None:
    client = FakeClient()
    plan = _plan()
    assert _registry(client).registrar_plano(plan) == plan.plano_id
    # Nada de streaming: o plano e lido de volta num turno seguinte.
    assert client.inserts == []
    [(query, config)] = client.queries
    assert query == PLAN_INSERT
    assert config["default_dataset"] == "projeto-teste.bussola_app_dev"
    assert config["plano"]["id_usuario"] == ANCHOR
    assert config["plano"]["valor_alvo"] == 30000.0
    assert config["plano"]["criado_em"].startswith("2026-09-26T12:00:00")


def test_insert_consent_event_and_follow_up() -> None:
    client = FakeClient()
    registry = _registry(client)
    consent = _consent()
    event = EventoAuditoria(
        session_id="s",
        estado="AGIR",
        tipo_evento="acao_executada",
        resumo={"acao": "ativar_lembretes", "valor": 1.5},
        ts=TS,
    )
    follow = Acompanhamento(
        plano_id="p", anomes=202507, planejado=100.0, realizado=90.0, desvio=-10.0, ts=TS
    )
    registry.registrar_consentimento(consent)
    registry.registrar_evento(event)
    registry.registrar_acompanhamento(follow)

    tables = [t.rsplit(".", 1)[1] for t, _, _ in client.inserts]
    assert tables == ["consentimentos", "auditoria", "acompanhamento"]
    assert client.inserts[0][2] == [consent.consent_id]
    assert client.inserts[1][2] == [event.evento_id]
    assert json.loads(client.inserts[1][1][0]["resumo"]) == {
        "acao": "ativar_lembretes",
        "valor": 1.5,
    }


def test_errors_never_echo_values() -> None:
    client = FakeClient(errors=[{"index": 0, "errors": [{"message": f"bad {ANCHOR}"}]}])
    with pytest.raises(RegistryWriteError) as rejected:
        _registry(client).registrar_consentimento(_consent())
    assert ANCHOR not in str(rejected.value)

    broken = FakeClient()
    broken.fail = True
    with pytest.raises(RegistryWriteError) as failed:
        _registry(broken).registrar_plano(_plan())
    assert ANCHOR not in str(failed.value)
    assert "planos" in str(failed.value)


def test_wrong_row_type_is_refused() -> None:
    with pytest.raises(TypeError):
        _registry(FakeClient()).registrar_plano({"plano_id": "x"})  # type: ignore[arg-type]


def test_get_plan_from_the_local_cache_without_a_select() -> None:
    client = FakeClient()
    registry = _registry(client)
    plan = _plan()
    registry.registrar_plano(plan)
    assert registry.obter_plano(plan.plano_id) == plan
    # So o INSERT: o cache poupou o SELECT, que teria sido a segunda query.
    assert [query for query, _ in client.queries] == [PLAN_INSERT]


def test_get_plan_uses_the_constant_query_with_a_parameter() -> None:
    plan = _plan()
    client = FakeClient(rows=[plan.model_dump()])
    found = _registry(client).obter_plano(plan.plano_id)
    assert found == plan
    query, config = client.queries[0]
    assert query == PLAN_QUERY
    assert config == {"default_dataset": "projeto-teste.bussola_app_dev", "plano_id": plan.plano_id}


def test_get_plan_missing_or_invalid() -> None:
    client = FakeClient(rows=[])
    registry = _registry(client)
    assert registry.obter_plano("nao-existe") is None
    assert registry.obter_plano("") is None
    assert len(client.queries) == 1


def test_real_insert_config_is_parameterized() -> None:
    plan = _plan().model_copy(update={"objetivo": "x'; DROP TABLE planos; --"})
    config = persistencia_bq._plan_insert_config(PROJECT, "bussola_app_dev", plan)
    assert config.default_dataset.dataset_id == "bussola_app_dev"
    por_nome = {p.name: p for p in config.query_parameters}
    assert set(por_nome) == set(PLAN_COLUMNS)
    assert por_nome["objetivo"].value == "x'; DROP TABLE planos; --"
    assert por_nome["objetivo"].type_ == "STRING"
    assert (por_nome["valor_alvo"].type_, por_nome["valor_alvo"].value) == ("FLOAT64", 30000.0)
    assert (por_nome["prazo_meses"].type_, por_nome["prazo_meses"].value) == ("INT64", 24)
    assert por_nome["criado_em"].type_ == "TIMESTAMP"


def test_real_query_config_is_parameterized() -> None:
    config = persistencia_bq._plan_query_config(PROJECT, "bussola_app_dev", "x'; DROP TABLE y")
    assert config.default_dataset.dataset_id == "bussola_app_dev"
    [param] = config.query_parameters
    assert (param.name, param.type_, param.value) == ("plano_id", "STRING", "x'; DROP TABLE y")


@pytest.mark.parametrize(
    ("project", "dataset"),
    [("", "bussola_app"), ("P", "bussola_app"), (PROJECT, "bussola-app"), (PROJECT, "a.b")],
)
def test_invalid_project_or_dataset(
    project: str, dataset: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    with pytest.raises(ValueError):
        RegistroBigQuery(client=FakeClient(), project=project, dataset=dataset)


def test_client_is_created_lazily() -> None:
    created: list[str] = []

    def factory(project: str) -> FakeClient:
        created.append(project)
        return FakeClient()

    registry = RegistroBigQuery(project=PROJECT, dataset="bussola_app_dev", client_factory=factory)
    assert created == []
    registry.registrar_plano(_plan())
    registry.registrar_plano(_plan())
    assert created == [PROJECT]


def test_dataset_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", PROJECT)
    monkeypatch.delenv("BQ_DATASET_APP", raising=False)
    assert RegistroBigQuery(client=FakeClient()).dataset == "bussola_app"
    monkeypatch.setenv("BQ_DATASET_APP", "bussola_app_dev")
    assert RegistroBigQuery(client=FakeClient()).dataset == "bussola_app_dev"


@pytest.mark.parametrize(
    ("value", "enabled"),
    [
        ("TRUE", True),
        ("true", True),
        ("", True),
        ("qualquer", True),
        ("FALSE", False),
        ("0", False),
    ],
)
def test_fakes_enabled(value: str, enabled: bool) -> None:
    assert fakes_enabled({"BUSSOLA_FAKES": value}) is enabled


def test_fakes_enabled_by_default() -> None:
    assert fakes_enabled({}) is True


def test_build_registry() -> None:
    assert isinstance(build_registry({"BUSSOLA_FAKES": "TRUE"}), RegistroEmMemoria)
    real = build_registry(
        {"BUSSOLA_FAKES": "FALSE", "GOOGLE_CLOUD_PROJECT": PROJECT, "BQ_DATASET_APP": "x_dev"}
    )
    assert isinstance(real, RegistroBigQuery) and real.dataset == "x_dev"


def test_default_registry_is_shared() -> None:
    persistencia_bq.set_default_registry(None)
    first = persistencia_bq.default_registry()
    assert isinstance(first, RegistroEmMemoria)
    assert persistencia_bq.default_registry() is first
