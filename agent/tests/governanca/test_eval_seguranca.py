"""Security eval (``eval/seguranca``) runs inside ``make test``: deterministic (D1)."""

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType

import pytest

from bussola_agent.governanca.guardrails import Finding

EVAL_FILE = Path(__file__).resolve().parents[3] / "eval" / "seguranca" / "rodar_eval.py"


@pytest.fixture(scope="module")
def rodar_eval() -> ModuleType:
    name = "rodar_eval_seguranca"
    spec = importlib.util.spec_from_file_location(name, EVAL_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_cases_cover_the_cycle_list(rodar_eval: ModuleType) -> None:
    cases = rodar_eval.load_cases()
    assert len(cases) >= 8
    assert {c.get("ciclo") for c in cases} >= set(rodar_eval.CYCLE_CASES)
    for case in cases:
        assert case["turnos"] and all("esperado" in t for t in case["turnos"])


async def test_all_cases_behave_as_expected(rodar_eval: ModuleType) -> None:
    results = await rodar_eval.evaluate(rodar_eval.load_cases())
    failures = {
        r.case_id: [f for t in r.turns for f in t.failures] + r.failures
        for r in results
        if not r.passed
    }
    assert failures == {}


class _NoScreener:
    """A guardrail that lets everything through: the eval must notice."""

    async def check_input(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        return None

    async def check_output(self, text: str, known_ids: frozenset[str]) -> Finding | None:
        return None


async def test_eval_catches_a_missing_guardrail(rodar_eval: ModuleType) -> None:
    results = await rodar_eval.evaluate(rodar_eval.load_cases(), screener_factory=_NoScreener)
    by_id = {r.case_id: r for r in results}
    for case_id in ("outro_cliente_uuid", "infra_sql", "vazamento_sql_saida"):
        assert not by_id[case_id].passed
    assert by_id["outro_cliente_uuid"].failures  # invariant: a foreign UUID reached the customer
    # The gate and the consent reader do not depend on the screener.
    assert by_id["recusa_respeitada"].passed
    assert by_id["controle_consentimento_uso_unico"].passed


def test_check_reports_each_mismatch(rodar_eval: ModuleType) -> None:
    seen = {
        "guardrail": None,
        "modelo_chamado": True,
        "ferramentas": {"criar_plano": "ok"},
        "consentimentos": {},
        "planos": 1,
        "decisoes": [],
        "auditoria": ["plano_criado"],
        "respostas_rapidas": None,
        "texto": "SELECT 1",
    }
    failures = rodar_eval.check(
        {
            "guardrail": "infra",
            "ferramentas": {"criar_plano": "CONSENTIMENTO_NECESSARIO"},
            "auditoria_exclui": ["plano_criado"],
            "texto_nao_contem": ["SELECT"],
            "outra": 1,
        },
        seen,
    )
    assert len(failures) == 5


def test_render_lists_every_case(rodar_eval: ModuleType) -> None:
    ok = rodar_eval.CaseResult("a", "Caso A", 1)
    bad = rodar_eval.CaseResult("b", "Caso B", None, failures=["x"])
    text = rodar_eval.render([ok, bad], generated=datetime(2026, 9, 27, tzinfo=UTC))
    assert "Resultado: 1/2 casos ok" in text
    assert "| `a` | 1 | Caso A | ✅ |" in text
    assert "## Falhas" in text and "- `b`: x" in text


def test_invalid_script_step(rodar_eval: ModuleType) -> None:
    with pytest.raises(ValueError):
        rodar_eval.to_response({"outra": "coisa"})
