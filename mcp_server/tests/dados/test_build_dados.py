"""Testes offline de ``data/scripts/build_dados.py`` (ciclo 001, F1).

Troca de ``{{dataset}}``, validação do dataset e das personas, avaliação das verificações
pós-build e uma execução completa com cliente BigQuery falso (sem rede).
"""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from google.cloud.bigquery import SchemaField

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / "data" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"bussola_scripts_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load_script("build_dados")
ddl = _load_script("aplicar_ddl")

PERSONAS = json.loads(build.PERSONAS_FILE.read_text(encoding="utf-8"))
OK_CHECKS = {
    name: (expected if expected is not None else 0)
    for name, (expected, _) in build.EXPECTED_CHECKS.items()
}


# ---------------------------------------------------------------------------
# Dataset e SQL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["bussola_dados", "bussola_dados_teste", "bussola_dados_c001"])
def test_accepts_bussola_dados_datasets(name: str) -> None:
    assert build.validate_dataset(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "hackathon_dados",
        "bussola_app",
        "bussola_app_dev",
        "bussola_dados.perfil_mensal",
        "bussola_dados; DROP SCHEMA x",
        "bussola_dados_",
        "Bussola_dados",
        "",
    ],
)
def test_rejects_other_datasets(name: str) -> None:
    with pytest.raises(build.BuildError):
        build.validate_dataset(name)


def test_every_step_has_sql_with_placeholder_and_transaction() -> None:
    assert list(build.STEPS)[-2:] == ["referencia_coorte", "users"]
    assert set(build.MILESTONE_TABLES) < set(build.STEPS.values())
    for step, table in build.STEPS.items():
        template = (build.SQL_DIR / f"{step}.sql").read_text(encoding="utf-8")
        assert f"TRUNCATE TABLE {{{{dataset}}}}.{table};" in template
        assert "BEGIN TRANSACTION;" in template and "COMMIT TRANSACTION;" in template
        sql = build.load_step_sql(step, "bussola_dados_teste")
        assert "{{" not in sql and "bussola_dados_teste." in sql
        assert "CREATE OR REPLACE" not in sql.upper()
        assert "DROP " not in sql.upper()


def test_sql_writes_only_to_target_dataset() -> None:
    for step in build.STEPS:
        sql = build.load_step_sql(step, "bussola_dados_teste").upper()
        for verb in ("TRUNCATE TABLE ", "INSERT INTO "):
            for chunk in sql.split(verb)[1:]:
                assert chunk.startswith("BUSSOLA_DADOS_TESTE.")


def test_source_is_only_read() -> None:
    for step in build.STEPS:
        sql = build.load_step_sql(step, "bussola_dados")
        assert "INSERT INTO `hackathon_dados" not in sql
        assert "INSERT INTO hackathon_dados" not in sql


def test_render_rejects_unknown_placeholder() -> None:
    with pytest.raises(build.BuildError):
        build.render_sql("SELECT * FROM {{dataset}}.x WHERE a = '{{outro}}'", "bussola_dados")


def test_users_sql_takes_rows_only_as_parameter() -> None:
    sql = build.load_step_sql("users", "bussola_dados")
    assert "UNNEST(@usuarios)" in sql
    for persona in PERSONAS:
        assert persona["login"] not in sql and persona["id_usuario"] not in sql


SEED_ROW = re.compile(r"^\s*\('([^']+)', '([^']+)', (TRUE|FALSE), (0\.[0-9])\)[,;]$", re.M)


def test_seed_has_98_unique_pairs_with_valid_cut() -> None:
    rows = SEED_ROW.findall(build.load_step_sql("seed_categorias", "bussola_dados"))
    assert len(rows) == build.EXPECTED_CATEGORY_PAIRS
    assert len({(macro, micro) for macro, micro, _, _ in rows}) == len(rows)
    for _, _, discretionary, pct in rows:
        if discretionary == "TRUE":
            assert 0.2 <= float(pct) <= 0.5
        else:
            assert float(pct) == 0.0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, list(build.STEPS)),
        ("users", ["users"]),
        ("users, perfil_mensal", ["perfil_mensal", "users"]),
    ],
)
def test_parse_steps_keeps_canonical_order(text: str | None, expected: list[str]) -> None:
    assert build.parse_steps(text) == expected


@pytest.mark.parametrize("text", ["usuarios", ",", "perfil_mensal,drop"])
def test_parse_steps_rejects_unknown(text: str) -> None:
    with pytest.raises(build.BuildError):
        build.parse_steps(text)


def test_ddl_plan_targets_only_the_dataset() -> None:
    for dataset in ("bussola_dados", "bussola_dados_teste"):
        plan = build.ddl_plan(dataset)
        assert {i.dataset for i in plan} == {dataset}
        tables = {i.tabela for i in plan if i.tipo == "tabela"}
        assert set(build.STEPS.values()) <= tables


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------


def test_personas_fixture_is_valid() -> None:
    personas = build.load_personas()
    assert {p.id_usuario for p in personas} >= {ID_ANCORA, ID_CONTROLE}


def _mutated(index: int, **changes: Any) -> list[dict[str, Any]]:
    rows = copy.deepcopy(PERSONAS)
    rows[index].update(changes)
    return rows


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"login": "Fernando"}, "login"),
        ({"login": "x"}, "login"),
        ({"login": "fernando' OR 1=1 --"}, "login"),
        ({"id_usuario": ID_ANCORA.upper()}, "id_usuario"),
        ({"id_usuario": "36a21505-d6d4-42d3-b319-d51a133c7269' OR '1'='1"}, "id_usuario"),
        ({"id_usuario": "00000000-0000-1000-8000-000000000000"}, "id_usuario"),
        ({"display_name": " Fernando"}, "display_name"),
        ({"display_name": ""}, "display_name"),
        ({"display_name": "x" * 81}, "display_name"),
        ({"summary": "x" * 281}, "summary"),
        ({"featured": "sim"}, "featured"),
        ({"senha": "segredo123"}, "senha"),
    ],
)
def test_invalid_persona_is_rejected_without_echo(changes: dict[str, Any], field: str) -> None:
    with pytest.raises(build.BuildError) as error:
        build.validate_personas(_mutated(0, **changes))
    message = str(error.value)
    assert "linha 0" in message and field in message
    for value in changes.values():
        if isinstance(value, str) and len(value) > 4:
            assert value not in message


def test_duplicate_persona_is_rejected() -> None:
    rows = _mutated(1, id_usuario=PERSONAS[0]["id_usuario"])
    with pytest.raises(build.BuildError, match="id_usuario repetido"):
        build.validate_personas(rows)
    with pytest.raises(build.BuildError, match="não vazia"):
        build.validate_personas([])


# ---------------------------------------------------------------------------
# Verificações pós-build
# ---------------------------------------------------------------------------


def test_checks_all_green() -> None:
    assert build.evaluate_checks(OK_CHECKS) == []


def test_checks_report_each_failure() -> None:
    values = {**OK_CHECKS, "usuarios": 999, "gasto_divergente": 3}
    values.pop("coorte_pequena")
    failures = build.evaluate_checks(values)
    assert len(failures) == 3
    assert any("1000 usuários (obtido 999)" in f for f in failures)
    assert any("gastos_categoria" in f and "obtido 3" in f for f in failures)
    assert any(f.startswith("coorte_pequena: verificação ausente") for f in failures)


def test_checks_sql_covers_every_expected_check() -> None:
    sql = build.render_sql(build.CHECKS_SQL, "bussola_dados")
    for name in build.EXPECTED_CHECKS:
        assert f"AS {name}" in sql
    assert "{{" not in build.render_sql(build.COUNTS_SQL, "bussola_dados")


# ---------------------------------------------------------------------------
# Execução com cliente falso
# ---------------------------------------------------------------------------


def _schema(instrucao: Any) -> list[SchemaField]:
    return [SchemaField(c.nome, *ddl.campo_esperado(c)) for c in instrucao.colunas]


class _Job:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def result(self) -> list[Any]:
        return self.rows


class FakeClient:
    """Registra as queries e responde às consultas de verificação do build."""

    def __init__(self, dataset: str = "bussola_dados", checks: dict[str, int] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.plan = {i.alvo: i for i in build.ddl_plan(dataset)}
        self.checks = OK_CHECKS if checks is None else checks
        self.known_ids = {p["id_usuario"] for p in PERSONAS}

    def query(self, sql: str, job_config: Any = None, location: str | None = None) -> _Job:
        params = list(job_config.query_parameters) if job_config is not None else []
        self.calls.append({"sql": sql, "params": params, "location": location})
        if "IN UNNEST(@ids_usuario)" in sql:
            ids = params[0].values
            return _Job([{"id_usuario": i} for i in ids if i in self.known_ids])
        if "AS linhas FROM" in sql:
            return _Job([{"tabela": t, "linhas": 1} for t in build.STEPS.values()])
        if "AS users_sem_extrato" in sql:
            return _Job([dict(self.checks)])
        return _Job([])

    def get_dataset(self, alvo: str) -> Any:
        return SimpleNamespace(location="us-central1")

    def get_table(self, alvo: str) -> Any:
        return SimpleNamespace(schema=_schema(self.plan[alvo.split(".", 1)[1]]))


def _forbidden_factory(project: str) -> Any:
    raise AssertionError("não devia criar cliente BigQuery")


def test_dry_run_prints_sql_without_client(capsys: pytest.CaptureFixture[str]) -> None:
    assert build.main(["--dry-run", "--etapas", "users"], create_client=_forbidden_factory) == 0
    out = capsys.readouterr().out
    assert "TRUNCATE TABLE bussola_dados.users;" in out
    assert PERSONAS[0]["id_usuario"] not in out


def test_invalid_dataset_exits_2_before_client(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["--dataset", "hackathon_dados", "--projeto", "p"]
    assert build.main(argv, create_client=_forbidden_factory) == 2
    assert "dataset inválido" in capsys.readouterr().err


def test_missing_project_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert build.main([], create_client=_forbidden_factory) == 2
    assert "GOOGLE_CLOUD_PROJECT" in capsys.readouterr().err


def test_full_build_with_fake_client(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    assert build.main(["--projeto", "p"], create_client=lambda project: client) == 0
    sqls = [call["sql"] for call in client.calls]
    assert all(call["location"] == "us-central1" for call in client.calls)
    ddl_calls = [s for s in sqls if "IF NOT EXISTS" in s]
    assert ddl_calls and sqls.index(ddl_calls[-1]) < next(
        i for i, s in enumerate(sqls) if "TRUNCATE" in s
    )
    truncated = [s.split("TRUNCATE TABLE ")[1].split(";")[0] for s in sqls if "TRUNCATE" in s]
    assert truncated == [f"bussola_dados.{t}" for t in build.STEPS.values()]
    users_call = next(c for c in client.calls if "UNNEST(@usuarios)" in c["sql"])
    (param,) = users_call["params"]
    assert param.name == "usuarios" and len(param.values) == len(PERSONAS)
    out = capsys.readouterr().out
    assert "Validação pós-build: ok." in out
    assert "bussola_dados.users: 1 linhas" in out


def test_single_step_skips_others(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    argv = ["--projeto", "p", "--etapas", "users"]
    assert build.main(argv, create_client=lambda project: client) == 0
    truncated = [c["sql"] for c in client.calls if "TRUNCATE" in c["sql"]]
    assert len(truncated) == 1 and "bussola_dados.users;" in truncated[0]


def test_persona_missing_from_source_aborts_before_insert(
    capsys: pytest.CaptureFixture[str],
) -> None:
    client = FakeClient()
    client.known_ids = {ID_ANCORA}
    argv = ["--projeto", "p", "--etapas", "users"]
    assert build.main(argv, create_client=lambda project: client) == 2
    assert not [c for c in client.calls if "TRUNCATE" in c["sql"]]
    err = capsys.readouterr().err
    assert "ausente no extrato" in err and ID_CONTROLE not in err


def test_failed_checks_exit_3(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient(checks={**OK_CHECKS, "fora_periodo": 7})
    argv = ["--projeto", "p", "--somente-validar"]
    assert build.main(argv, create_client=lambda project: client) == 3
    assert not [c for c in client.calls if "TRUNCATE" in c["sql"] or "IF NOT EXISTS" in c["sql"]]
    assert "obtido 7" in capsys.readouterr().err


def test_schema_divergence_exits_3_before_writing(capsys: pytest.CaptureFixture[str]) -> None:
    client = FakeClient()
    original = client.get_table

    def drifted(alvo: str) -> Any:
        table = original(alvo)
        if alvo.endswith(".perfil_mensal"):
            table.schema = [f for f in table.schema if f.name != "juros"]
        return table

    client.get_table = drifted  # type: ignore[method-assign]
    assert build.main(["--projeto", "p"], create_client=lambda project: client) == 3
    assert not [c for c in client.calls if "TRUNCATE" in c["sql"]]
    assert "perfil_mensal" in capsys.readouterr().err
