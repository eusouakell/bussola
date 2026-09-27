"""Constrói as tabelas de ``bussola_dados`` a partir do extrato sintético (ciclo 001, F1).

Fluxo (contratos §3; ciclo 001 §3.1–§3.2):

1. garante o DDL de ``contracts/bigquery/bussola_dados.sql`` no dataset de destino
   (``CREATE ... IF NOT EXISTS``, reaproveitando ``aplicar_ddl.py``) e confere o schema;
2. executa os SQL de ``data/sql/`` na ordem de :data:`STEPS`. Cada arquivo é um script
   ``BEGIN TRANSACTION; TRUNCATE TABLE ...; INSERT ...; COMMIT TRANSACTION;``: rodar de
   novo produz o mesmo conteúdo, e o schema ``NOT NULL`` do contrato é preservado
   (``CREATE OR REPLACE TABLE ... AS SELECT`` perderia o modo ``REQUIRED``; plan.md D-01);
3. carrega ``users`` a partir de ``contracts/fixtures/bussola_dados/users.json``: cada
   linha é validada (regras de ``web/bff/domain/userAccount.ts``) e cada ``id_usuario``
   precisa existir no extrato. As linhas entram só como parâmetro ``@usuarios``;
4. roda as validações pós-build (1.000 usuários × 12 meses, período, somas por categoria
   contra ``perfil_mensal``, UUID v4, cobertura do catálogo) e imprime a contagem de
   linhas de cada tabela.

Com ``--fixtures SAIDA`` o script só lê: gera as fixtures v1 de contratos §8 (plan.md
D-07). As linhas de âncora e controle vêm do ``RepositorioBigQuery`` (modo ``query``), e
os goldens saem de ``metricas.*`` sobre um ``RepositorioFake`` dessas mesmas linhas.
``bussola_dados/users.json`` e ``rag/`` não são tocados.

O único texto trocado nos ``.sql`` é o marcador ``{{dataset}}``, e só depois de validar o
nome (``bussola_dados`` ou ``bussola_dados_<sufixo>``). A origem
``hackathon_dados.extrato_sintetico`` é somente leitura; nenhum valor de usuário entra no
SQL por formatação de string.

Uso, com ADC (``gcloud auth application-default login``)::

    uv run --project mcp_server python data/scripts/build_dados.py --dry-run
    uv run --project mcp_server python data/scripts/build_dados.py
    uv run --project mcp_server python data/scripts/build_dados.py --etapas users
    uv run --project mcp_server python data/scripts/build_dados.py --somente-validar
    uv run --project mcp_server python data/scripts/build_dados.py --fixtures contracts/fixtures

Códigos de saída: 0 (ok), 2 (argumento, configuração ou entrada inválida), 3 (validação
pós-build ou schema divergente).
"""

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from pydantic import ValidationError

from bussola_mcp import config
from bussola_mcp.contratos import (
    ANOMES_MAX,
    ANOMES_MIN,
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    UUID_V4_RE,
    FaixaRenda,
    UserPersona,
    arquivo_golden,
    arquivo_resumo_mes,
)
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.dominio.interfaces import RepositorioFinanceiro
from bussola_mcp.dominio.repositorio_bq import (
    SORT_KEYS,
    RepositorioBigQuery,
    RepositoryUnavailableError,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
# A raiz do repositório e os defaults de ambiente têm um dono só:
# ``bussola_mcp.config`` (contratos §7). Aqui só se lê de lá.
REPO_ROOT = config.RAIZ_REPOSITORIO
SQL_DIR = REPO_ROOT / "data" / "sql"
DDL_FILE = REPO_ROOT / "contracts" / "bigquery" / "bussola_dados.sql"
PERSONAS_FILE = REPO_ROOT / "contracts" / "fixtures" / "bussola_dados" / "users.json"

LOCATION = config.LOCAL_GCP_PADRAO
"""Região padrão dos jobs. O valor efetivo vem de :func:`config.local_gcp`."""

DEFAULT_DATASET = config.DATASET_DADOS_PADRAO
"""Dataset canônico de destino (contratos §3); o efetivo vem de
:func:`config.dataset_dados` ou de ``--dataset``."""

SOURCE_TABLE = "hackathon_dados.extrato_sintetico"
DATASET_PLACEHOLDER = "{{dataset}}"

# Etapa (arquivo em data/sql/ sem .sql) → tabela gravada. A ordem importa:
# referencia_coorte lê perfil_mensal e gastos_categoria já reconstruídas.
STEPS: dict[str, str] = {
    "perfil_mensal": "perfil_mensal",
    "gastos_categoria": "gastos_categoria",
    "entradas_categoria": "entradas_categoria",
    "recorrentes": "recorrentes",
    "parcelas": "parcelas",
    "seed_categorias": "categorias",
    "referencia_coorte": "referencia_coorte",
    "users": "users",
}
# Marco "tabelas v1" (ciclo 001 §3.2): as seis tabelas que desbloqueiam o 003.
MILESTONE_TABLES: tuple[str, ...] = (
    "perfil_mensal",
    "gastos_categoria",
    "entradas_categoria",
    "recorrentes",
    "parcelas",
    "categorias",
)

EXPECTED_USERS = 1000
EXPECTED_MONTHS = ANOMES_MAX - ANOMES_MIN + 1
EXPECTED_CATEGORY_PAIRS = 98
SUM_TOLERANCE = 0.005

_DATASET_RE = re.compile(r"bussola_dados(?:_[a-z0-9_]{1,64})?")
# Regras de linha de web/bff/domain/userAccount.ts (o teste de contrato confere as duas).
LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,31}$")
MAX_ID_LENGTH = 36
MAX_DISPLAY_NAME = 80
MAX_SUMMARY = 280


class BuildError(Exception):
    """Configuração ou dado inválido. A mensagem nunca ecoa valores de linhas."""


class FixtureValidationError(Exception):
    """Fixtures v1 fora dos modelos de contratos §8 (código de saída 3)."""


# ---------------------------------------------------------------------------
# Funções puras: dataset, SQL e personas
# ---------------------------------------------------------------------------


def validate_dataset(name: str) -> str:
    """Aceita só ``bussola_dados`` ou ``bussola_dados_<sufixo>`` (nunca a origem)."""
    if not isinstance(name, str) or not _DATASET_RE.fullmatch(name):
        raise BuildError("dataset inválido: use bussola_dados ou bussola_dados_<sufixo>")
    return name


def render_sql(template: str, dataset: str) -> str:
    """Troca ``{{dataset}}`` pelo dataset validado; qualquer outro marcador aborta."""
    sql = template.replace(DATASET_PLACEHOLDER, validate_dataset(dataset))
    if "{{" in sql or "}}" in sql:
        raise BuildError("marcador desconhecido no SQL")
    return sql


def load_step_sql(step: str, dataset: str, sql_dir: Path = SQL_DIR) -> str:
    if step not in STEPS:
        raise BuildError(f"etapa desconhecida: use uma de {', '.join(STEPS)}")
    return render_sql((sql_dir / f"{step}.sql").read_text(encoding="utf-8"), dataset)


def parse_steps(text: str | None) -> list[str]:
    """Etapas pedidas em ``--etapas`` (separadas por vírgula), na ordem de :data:`STEPS`."""
    if not text:
        return list(STEPS)
    asked = {item.strip() for item in text.split(",") if item.strip()}
    unknown = asked - set(STEPS)
    if unknown or not asked:
        raise BuildError(f"etapa desconhecida: use uma de {', '.join(STEPS)}")
    return [step for step in STEPS if step in asked]


def validate_personas(rows: Any) -> list[UserPersona]:
    """Valida as linhas de ``users.json`` sem ecoar valores (só índice e campo)."""
    if not isinstance(rows, list) or not rows:
        raise BuildError("users.json deve ser uma lista não vazia de linhas")
    personas: list[UserPersona] = []
    for index, row in enumerate(rows):
        try:
            persona = UserPersona.model_validate(row)
        except ValidationError as exc:
            fields = sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]})
            raise BuildError(f"users.json linha {index}: campos inválidos {fields}") from None
        problems = _persona_problems(persona)
        if problems:
            raise BuildError(f"users.json linha {index}: campos inválidos {problems}")
        personas.append(persona)
    for field in ("login", "id_usuario"):
        values = [getattr(p, field) for p in personas]
        if len(set(values)) != len(values):
            raise BuildError(f"users.json: {field} repetido")
    return personas


def _persona_problems(persona: UserPersona) -> list[str]:
    problems: list[str] = []
    if not LOGIN_RE.fullmatch(persona.login):
        problems.append("login")
    id_usuario = persona.id_usuario
    if (
        len(id_usuario) > MAX_ID_LENGTH
        or id_usuario != id_usuario.lower()
        or not UUID_V4_RE.fullmatch(id_usuario)
    ):
        problems.append("id_usuario")
    name = persona.display_name
    if name != name.strip() or not 0 < len(name) <= MAX_DISPLAY_NAME:
        problems.append("display_name")
    if len(persona.summary) > MAX_SUMMARY:
        problems.append("summary")
    return problems


def load_personas(path: Path = PERSONAS_FILE) -> list[UserPersona]:
    return validate_personas(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Validações pós-build
# ---------------------------------------------------------------------------

_UUID_SQL = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"

CHECKS_SQL = f"""
WITH gastos AS (
  SELECT id_usuario, anomes, SUM(total) AS total
  FROM {{{{dataset}}}}.gastos_categoria GROUP BY id_usuario, anomes
),
entradas AS (
  SELECT id_usuario, anomes, SUM(total) AS total
  FROM {{{{dataset}}}}.entradas_categoria GROUP BY id_usuario, anomes
),
pares AS (
  SELECT DISTINCT nom_cate_macro AS macro, nom_cate_micro AS micro
  FROM `{SOURCE_TABLE}`
  WHERE anomes BETWEEN {ANOMES_MIN} AND {ANOMES_MAX}
)
SELECT
  (SELECT COUNT(DISTINCT id_usuario) FROM {{{{dataset}}}}.perfil_mensal) AS usuarios,
  (SELECT COUNT(*) FROM {{{{dataset}}}}.perfil_mensal) AS linhas_perfil,
  (SELECT COUNT(*) FROM (
     SELECT id_usuario, anomes FROM {{{{dataset}}}}.perfil_mensal
     GROUP BY id_usuario, anomes HAVING COUNT(*) > 1)) AS perfil_duplicado,
  (SELECT COUNTIF(anomes NOT BETWEEN {ANOMES_MIN} AND {ANOMES_MAX}) FROM (
     SELECT anomes FROM {{{{dataset}}}}.perfil_mensal
     UNION ALL SELECT anomes FROM {{{{dataset}}}}.gastos_categoria
     UNION ALL SELECT anomes FROM {{{{dataset}}}}.entradas_categoria
     UNION ALL SELECT anomes FROM {{{{dataset}}}}.recorrentes
     UNION ALL SELECT anomes FROM {{{{dataset}}}}.parcelas)) AS fora_periodo,
  (SELECT COUNTIF(NOT REGEXP_CONTAINS(id_usuario, r'{_UUID_SQL}')) FROM (
     SELECT id_usuario FROM {{{{dataset}}}}.perfil_mensal
     UNION ALL SELECT id_usuario FROM {{{{dataset}}}}.gastos_categoria
     UNION ALL SELECT id_usuario FROM {{{{dataset}}}}.entradas_categoria
     UNION ALL SELECT id_usuario FROM {{{{dataset}}}}.recorrentes
     UNION ALL SELECT id_usuario FROM {{{{dataset}}}}.parcelas)) AS ids_invalidos,
  (SELECT COUNTIF(ABS(p.gasto - IFNULL(g.total, 0)) > {SUM_TOLERANCE})
     FROM {{{{dataset}}}}.perfil_mensal AS p
     LEFT JOIN gastos AS g USING (id_usuario, anomes)) AS gasto_divergente,
  (SELECT COUNTIF(ABS(p.renda - IFNULL(e.total, 0)) > {SUM_TOLERANCE})
     FROM {{{{dataset}}}}.perfil_mensal AS p
     LEFT JOIN entradas AS e USING (id_usuario, anomes)) AS renda_divergente,
  (SELECT COUNT(*) FROM gastos AS g
     LEFT JOIN {{{{dataset}}}}.perfil_mensal AS p USING (id_usuario, anomes)
     WHERE p.id_usuario IS NULL) AS gastos_sem_perfil,
  (SELECT COUNT(*) FROM {{{{dataset}}}}.categorias) AS categorias,
  (SELECT COUNT(*) FROM pares
     LEFT JOIN {{{{dataset}}}}.categorias AS c USING (macro, micro)
     WHERE c.macro IS NULL) AS pares_sem_categoria,
  (SELECT COUNTIF(
       (discricionaria AND (corte_max_pct < 0.2 OR corte_max_pct > 0.5))
       OR (NOT discricionaria AND corte_max_pct != 0))
     FROM {{{{dataset}}}}.categorias) AS categorias_invalidas,
  (SELECT COUNTIF(qtd_usuarios < 5) FROM {{{{dataset}}}}.referencia_coorte) AS coorte_pequena,
  (SELECT COUNT(*) FROM {{{{dataset}}}}.users AS u
     LEFT JOIN (SELECT DISTINCT id_usuario FROM {{{{dataset}}}}.perfil_mensal) AS p
     USING (id_usuario)
     WHERE p.id_usuario IS NULL) AS users_sem_extrato
"""

# Linhas por tabela de ``STEPS`` (texto fixo; um teste confere que cobre todas as etapas).
COUNTS_SQL = """
SELECT 'perfil_mensal' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.perfil_mensal
UNION ALL
SELECT 'gastos_categoria' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.gastos_categoria
UNION ALL
SELECT 'entradas_categoria' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.entradas_categoria
UNION ALL
SELECT 'recorrentes' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.recorrentes
UNION ALL
SELECT 'parcelas' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.parcelas
UNION ALL
SELECT 'categorias' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.categorias
UNION ALL
SELECT 'referencia_coorte' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.referencia_coorte
UNION ALL
SELECT 'users' AS tabela, COUNT(*) AS linhas FROM {{dataset}}.users
"""

# Verificação → (valor esperado, mensagem). ``None`` = só informativo.
EXPECTED_CHECKS: dict[str, tuple[int | None, str]] = {
    "usuarios": (EXPECTED_USERS, f"perfil_mensal deve ter {EXPECTED_USERS} usuários"),
    "linhas_perfil": (
        EXPECTED_USERS * EXPECTED_MONTHS,
        f"perfil_mensal deve ter {EXPECTED_USERS} × {EXPECTED_MONTHS} linhas",
    ),
    "perfil_duplicado": (0, "perfil_mensal com usuário/mês repetido"),
    "fora_periodo": (0, f"linhas com anomes fora de {ANOMES_MIN}–{ANOMES_MAX}"),
    "ids_invalidos": (0, "id_usuario fora do formato UUID v4 em minúsculas"),
    "gasto_divergente": (0, "soma de gastos_categoria diverge de perfil_mensal.gasto"),
    "renda_divergente": (0, "soma de entradas_categoria diverge de perfil_mensal.renda"),
    "gastos_sem_perfil": (0, "gastos_categoria com usuário/mês sem perfil_mensal"),
    "categorias": (EXPECTED_CATEGORY_PAIRS, f"categorias deve ter {EXPECTED_CATEGORY_PAIRS} pares"),
    "pares_sem_categoria": (0, "par macro/micro do extrato fora de categorias"),
    "categorias_invalidas": (0, "corte_max_pct fora de 0,2–0,5 (ou ≠ 0 se não discricionária)"),
    "coorte_pequena": (0, "referencia_coorte com grupo de menos de 5 usuários"),
    "users_sem_extrato": (0, "users com id_usuario sem perfil_mensal"),
}


def evaluate_checks(values: Mapping[str, Any]) -> list[str]:
    """Falhas das validações pós-build (lista vazia = tudo certo)."""
    failures: list[str] = []
    for name, (expected, message) in EXPECTED_CHECKS.items():
        value = values.get(name)
        if value is None:
            failures.append(f"{name}: verificação ausente")
        elif expected is not None and int(value) != expected:
            failures.append(f"{message} (obtido {int(value)})")
    return failures


# ---------------------------------------------------------------------------
# Execução (única parte com BigQuery)
# ---------------------------------------------------------------------------


def _load_sibling(name: str) -> ModuleType:
    """Carrega outro script de ``data/scripts/`` (não é pacote Python)."""
    module_name = f"bussola_scripts_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise BuildError(f"script {name}.py não encontrado")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def ddl_plan(dataset: str, ddl_file: Path = DDL_FILE) -> list[Any]:
    """Instruções ``IF NOT EXISTS`` de ``bussola_dados.sql`` apontadas para ``dataset``."""
    ddl = _load_sibling("aplicar_ddl")
    text = ddl_file.read_text(encoding="utf-8")
    if validate_dataset(dataset) != DEFAULT_DATASET:
        text = ddl.trocar_dataset(text, dataset, origem=DEFAULT_DATASET)
    plan = ddl.parse_ddl(text)
    outside = [i for i in plan if i.dataset != dataset]
    if outside:
        raise BuildError("DDL com objeto fora do dataset de destino")
    return plan


def ensure_ddl(client: Any, project: str, dataset: str) -> list[str]:
    """Aplica o DDL (idempotente) e devolve as divergências de schema."""
    ddl = _load_sibling("aplicar_ddl")
    plan = ddl_plan(dataset)
    ddl.aplicar(client, plan)
    return ddl.verificar(client, project, plan)


@dataclass(frozen=True)
class QueryRunner:
    """Executa SQL com parâmetros nomeados na região de :func:`config.local_gcp`."""

    client: Any

    def run(self, sql: str, parameters: Sequence[Any] = ()) -> list[Any]:
        from google.cloud import bigquery

        job = bigquery.QueryJobConfig(query_parameters=list(parameters))
        return list(self.client.query(sql, job_config=job, location=config.local_gcp()).result())


def personas_parameter(personas: Iterable[UserPersona]) -> Any:
    """``@usuarios`` como ``ARRAY<STRUCT<login, id_usuario, display_name, summary, featured>>``."""
    from google.cloud import bigquery

    def struct(persona: UserPersona) -> Any:
        return bigquery.StructQueryParameter(
            None,
            bigquery.ScalarQueryParameter("login", "STRING", persona.login),
            bigquery.ScalarQueryParameter("id_usuario", "STRING", persona.id_usuario),
            bigquery.ScalarQueryParameter("display_name", "STRING", persona.display_name),
            bigquery.ScalarQueryParameter("summary", "STRING", persona.summary),
            bigquery.ScalarQueryParameter("featured", "BOOL", persona.featured),
        )

    return bigquery.ArrayQueryParameter("usuarios", "STRUCT", [struct(p) for p in personas])


EXISTING_IDS_SQL = f"""
SELECT DISTINCT id_usuario
FROM `{SOURCE_TABLE}`
WHERE id_usuario IN UNNEST(@ids_usuario)
  AND anomes BETWEEN {ANOMES_MIN} AND {ANOMES_MAX}
"""


def check_personas_exist(runner: QueryRunner, personas: Sequence[UserPersona]) -> None:
    """Todo ``id_usuario`` de ``users.json`` precisa ter lançamentos de 2025 no extrato."""
    from google.cloud import bigquery

    ids = [p.id_usuario for p in personas]
    parameter = bigquery.ArrayQueryParameter("ids_usuario", "STRING", ids)
    rows = runner.run(EXISTING_IDS_SQL, [parameter])
    found = {str(row["id_usuario"]).lower() for row in rows}
    missing = [i for i, id_usuario in enumerate(ids) if id_usuario not in found]
    if missing:
        raise BuildError(f"users.json: linha(s) {missing} com id_usuario ausente no extrato")


def run_step(runner: QueryRunner, step: str, dataset: str) -> None:
    sql = load_step_sql(step, dataset)
    parameters: list[Any] = []
    if step == "users":
        personas = load_personas()
        check_personas_exist(runner, personas)
        parameters = [personas_parameter(personas)]
    runner.run(sql, parameters)
    print(f"etapa concluída: {step} → {dataset}.{STEPS[step]}")


def validate_build(runner: QueryRunner, dataset: str) -> tuple[dict[str, int], list[str]]:
    """Contagem de linhas por tabela e falhas das validações pós-build."""
    counts = {
        str(row["tabela"]): int(row["linhas"])
        for row in runner.run(render_sql(COUNTS_SQL, dataset))
    }
    (checks,) = runner.run(render_sql(CHECKS_SQL, dataset))
    return counts, evaluate_checks(dict(checks.items()))


# ---------------------------------------------------------------------------
# Fixtures v1 (plan.md D-07): só leitura de bussola_dados
# ---------------------------------------------------------------------------

FIXTURE_CUTOFF = ANOMES_MAX
FIXTURE_USERS: tuple[tuple[str, str], ...] = ((ID_ANCORA, "ancora"), (ID_CONTROLE, "controle"))
CLIENT_FIXTURE_TABLES: tuple[str, ...] = (
    "perfil_mensal",
    "gastos_categoria",
    "entradas_categoria",
    "recorrentes",
    "parcelas",
)
# Mesmas entradas dos goldens provisórios (contratos §8).
GOLDEN_ARGUMENTS: dict[str, dict[str, Any]] = {
    "oportunidades_corte": {"top_n": 10},
    "simular_objetivo": dict(ENTRADA_CANONICA_SIMULACAO),
    "comparar_cenarios": dict(ENTRADA_CANONICA_SIMULACAO),
}


def fixture_repository(client: Any, dataset: str) -> RepositorioFinanceiro:
    """Repositório de leitura das fixtures v1: ``RepositorioBigQuery`` em modo ``query``."""
    return RepositorioBigQuery(modo="query", client=client, dataset=dataset)


def _rows_json(table: str, rows: Iterable[Any]) -> list[dict[str, Any]]:
    """Linhas em ordem estável (usuário, depois a ordem do repositório) e prontas para JSON."""
    key = SORT_KEYS[table]
    ordered = sorted(rows, key=lambda row: (getattr(row, "id_usuario", ""), *key(row)))
    return [row.model_dump(mode="json") for row in ordered]


def fixture_tables(repository: RepositorioFinanceiro) -> dict[str, list[dict[str, Any]]]:
    """Linhas de âncora e controle até dezembro, o catálogo e a coorte de todas as faixas."""
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in CLIENT_FIXTURE_TABLES:
        read = getattr(repository, table)
        rows = [row for id_usuario, _ in FIXTURE_USERS for row in read(id_usuario, FIXTURE_CUTOFF)]
        tables[table] = _rows_json(table, rows)
    tables["categorias"] = _rows_json("categorias", repository.categorias())
    cohort = [row for band in FaixaRenda for row in repository.referencia_coorte(band.value)]
    tables["referencia_coorte"] = _rows_json("referencia_coorte", cohort)
    return tables


def fixture_users(perfil: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """``usuarios.json``: faixa de renda pela renda média do ano (igual ao 000)."""
    users = []
    for id_usuario, papel in FIXTURE_USERS:
        rendas = [float(row["renda"]) for row in perfil if row["id_usuario"] == id_usuario]
        if len(rendas) != EXPECTED_MONTHS:
            raise BuildError(f"perfil_mensal do usuário {papel} sem os {EXPECTED_MONTHS} meses")
        faixa = metricas.income_band(sum(rendas) / len(rendas))
        users.append({"faixa_renda": faixa, "id_usuario": id_usuario, "papel": papel})
    return users


def _golden(repository: RepositorioFinanceiro, tool: str, ate: int, **kwargs: Any) -> Any:
    try:
        result = getattr(metricas, tool)(repository, ID_ANCORA, ate, **kwargs)
    except metricas.MetricError as exc:
        raise BuildError(f"golden {tool} até {ate}: {exc.codigo}") from exc
    return metricas.build_envelope(tool, result)


def fixture_goldens(repository: RepositorioFinanceiro) -> dict[str, Any]:
    """Goldens da âncora: as 6 ferramentas nos dois cortes e ``resumo_mes`` de cada mês."""
    goldens: dict[str, Any] = {}
    for cut in CORTES_GOLDEN:
        for tool in FERRAMENTAS_GOLDEN:
            path = f"ferramentas/{arquivo_golden(tool, cut)}"
            goldens[path] = _golden(repository, tool, cut, **GOLDEN_ARGUMENTS.get(tool, {}))
    for anomes in range(ANOMES_MIN, ANOMES_MAX + 1):
        path = f"ferramentas/{arquivo_resumo_mes(anomes)}"
        goldens[path] = _golden(repository, "resumo_mes", anomes, anomes=anomes)
    return goldens


def build_fixture_set(repository: RepositorioFinanceiro) -> dict[str, Any]:
    """Conjunto v1 (caminho relativo → JSON), validado com os modelos de contratos §8.

    As linhas vêm de ``repository``. Os goldens são calculados sobre um
    ``RepositorioFake`` dessas mesmas linhas, o que garante a consistência com as fixtures.
    """
    tables = fixture_tables(repository)
    data: dict[str, Any] = {"usuarios.json": fixture_users(tables["perfil_mensal"])}
    for table, rows in tables.items():
        data[f"bussola_dados/{table}.json"] = rows
    fixtures = _load_sibling("gerar_fixtures")
    with tempfile.TemporaryDirectory(prefix="bussola_fixtures_") as tmp:
        fixtures.gravar(tmp, data)
        data.update(fixture_goldens(RepositorioFake(tmp)))
    try:
        fixtures.validar_conjunto(data)
    except (ValidationError, fixtures.ErroDados) as exc:
        raise FixtureValidationError(f"fixtures v1 fora do contrato: {type(exc).__name__}") from exc
    return dict(sorted(data.items()))


def export_fixtures(repository: RepositorioFinanceiro, output: Path) -> dict[str, Any]:
    """Grava as fixtures v1 em ``output`` sem apagar outros arquivos (users.json, rag/)."""
    data = build_fixture_set(repository)
    _load_sibling("gerar_fixtures").gravar(output, data)
    return data


def _create_client(project: str) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=project, location=config.local_gcp())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_dados.py",
        description=(
            f"Reconstrói as tabelas de bussola_dados a partir de {SOURCE_TABLE} "
            "(TRUNCATE+INSERT em transação) e roda as validações pós-build."
        ),
    )
    parser.add_argument(
        "--dataset",
        default=config.dataset_dados(),
        help="dataset de destino (padrão: BQ_DATASET_DADOS ou bussola_dados)",
    )
    parser.add_argument(
        "--projeto", default=None, help="projeto GCP (padrão: variável GOOGLE_CLOUD_PROJECT)"
    )
    parser.add_argument(
        "--etapas", default=None, help=f"subconjunto de etapas, separadas por vírgula: {STEPS}"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="só mostra os SQL, sem BigQuery")
    mode.add_argument(
        "--somente-validar", action="store_true", help="só roda as validações pós-build"
    )
    mode.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        metavar="SAIDA",
        help="só lê o dataset e grava as fixtures v1 de contratos §8 em SAIDA",
    )
    return parser


def _fixtures_command(client: Any, dataset: str, output: Path) -> int:
    try:
        data = export_fixtures(fixture_repository(client, dataset), output)
    except (BuildError, RepositoryUnavailableError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except FixtureValidationError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 3
    for path, rows in data.items():
        if path.startswith("bussola_dados/") or path == "usuarios.json":
            print(f"{path}: {len(rows)} linhas")
    print(
        f"{len(data)} arquivos gravados em {output} (fixtures v1 de {dataset}; "
        "users.json e rag/ preservados)."
    )
    return 0


def main(
    argv: Sequence[str] | None = None,
    create_client: Callable[[str], Any] = _create_client,
) -> int:
    args = _parser().parse_args(argv)
    try:
        dataset = validate_dataset(args.dataset)
        steps = parse_steps(args.etapas)
        if args.dry_run:
            for step in steps:
                print(f"-- etapa {step}\n{load_step_sql(step, dataset)}")
            return 0
        if args.fixtures is None:
            load_personas()  # falha cedo, antes de qualquer escrita
    except (BuildError, OSError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    project = args.projeto or config.projeto_gcp()
    if not project:
        print("Erro: informe --projeto ou defina GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 2
    client = create_client(project)
    if args.fixtures is not None:
        return _fixtures_command(client, dataset, args.fixtures)
    runner = QueryRunner(client)
    try:
        if not args.somente_validar:
            divergences = ensure_ddl(client, project, dataset)
            if divergences:
                print("Schema divergente do DDL (nada foi gravado):", file=sys.stderr)
                for divergence in divergences:
                    print(f"  - {divergence}", file=sys.stderr)
                return 3
            for step in steps:
                run_step(runner, step, dataset)
        counts, failures = validate_build(runner, dataset)
    except BuildError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    for table, rows in counts.items():
        print(f"{dataset}.{table}: {rows} linhas")
    if failures:
        print("Validação pós-build falhou:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 3
    print("Validação pós-build: ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
