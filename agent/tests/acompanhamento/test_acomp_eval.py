"""Eval offline do 006 (``eval/acompanhamento/rodar_eval.py``) dentro do ``make test``."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from bussola_agent import callbacks, extensoes, mcp_conexao

EVAL_SCRIPT = Path(__file__).resolve().parents[3] / "eval" / "acompanhamento" / "rodar_eval.py"


@pytest.fixture(scope="module")
def eval_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rodar_eval_acompanhamento", EVAL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_every_eval_check_passes(eval_module: ModuleType) -> None:
    report = await eval_module.run_eval()
    failed = [(c.name, c.expected, c.obtained) for c in report.checks if not c.ok]
    assert failed == []
    assert [row.anomes for row in report.months][:3] == [202507, 202508, 202509]
    assert [row.status for row in report.months][:3] == ["desvio", "folga", "folga"]
    assert report.cited_numbers > 0


async def test_the_eval_restores_the_transport_and_the_registries(
    eval_module: ModuleType,
) -> None:
    transport = mcp_conexao._chamar_mcp
    await eval_module.run_eval()
    assert mcp_conexao._chamar_mcp is transport
    assert extensoes.ferramentas() == []
    assert callbacks.registrados("before_tool") == []


def test_main_writes_both_reports(eval_module: ModuleType, tmp_path: Path) -> None:
    assert eval_module.main(["--saida", str(tmp_path)]) == 0
    result = (tmp_path / "resultado.md").read_text(encoding="utf-8")
    summary = (tmp_path / "RESULTADOS.md").read_text(encoding="utf-8")
    assert "verificações ok** (aprovado)" in result
    assert "| 202507 | R$ 2.500,00 | R$ 884,53 |" in result
    assert "[resultado.md](resultado.md)" in summary
