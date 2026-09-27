"""Eval do agente no modo offline (FR-017, AC-08), dentro do ``make test``.

Roda ``eval/agente/rodar_eval.py`` com o roteiro de cada caso no lugar do
modelo, contra o mock do 000 em subprocesso (só loopback): todo número das
respostas precisa ter fonte e todas as expectativas precisam ser cumpridas.
O modo ao vivo fica fora do ``make test`` (``make eval-agente-ao-vivo``).
"""

import importlib.util
import shutil
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

import bussola_agent
from bussola_agent.extensoes import PACOTES_EXTENSAO
from bussola_agent.logging_json import configurar_logging

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "eval" / "agente" / "rodar_eval.py"
ENV_KEYS = (
    "ADK_DISABLE_LOAD_DOTENV",
    "BUSSOLA_FAKES",
    "GOOGLE_API_USE_CLIENT_CERTIFICATE",
    "MCP_URL",
    "MCP_USE_OIDC",
    "ANCHOR_USER_ID",
    "REPLAY_START_ANOMES",
)


@pytest.fixture
def rodar_eval(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    if shutil.which("uv") is None or not SCRIPT.is_file():
        pytest.skip("eval precisa do uv e de eval/agente/rodar_eval.py")
    # O eval ajusta o ambiente e reimporta o agente: tudo volta ao fim do teste.
    for key in ENV_KEYS:
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)
    # Extension packages are imported again so they register in the clean registries.
    for name in ("bussola_agent.agent", *PACOTES_EXTENSAO):
        monkeypatch.delitem(sys.modules, name, raising=False)
        monkeypatch.delattr(bussola_agent, name.rsplit(".", 1)[1], raising=False)
    spec = importlib.util.spec_from_file_location("rodar_eval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "rodar_eval", module)
    spec.loader.exec_module(module)
    yield module
    configurar_logging()


async def test_every_number_has_a_source_offline(rodar_eval: ModuleType, tmp_path: Path) -> None:
    output = tmp_path / "RESULTADOS.md"
    summary, results = await rodar_eval.run_eval(rodar_eval.MODE_OFFLINE, output=output)

    assert summary.unsupported == 0, [
        (r.case.id, t.unsupported) for r in results for t in r.turns if t.unsupported
    ]
    missed = [
        (r.case.id, name) for r in results for t in r.turns for name, ok in t.expectations if not ok
    ]
    assert not missed
    assert summary.checked > 40 and summary.unavailable == 0
    ids = {r.case.id for r in results}
    assert {"jornada-demo", "escopo-controle", "recusa-credito"} <= ids
    assert {f"q{n}" for n in range(1, 8)} == {i.split("-")[0] for i in ids if i.startswith("q")}

    report = output.read_text("utf-8")
    assert "<!-- eval:offline:inicio -->" in report and "**sem fonte: 0**" in report
    # Sem texto das respostas no arquivo: só contagens e nomes.
    assert "6.691,39" not in report and "Sua renda" not in report


def test_section_is_replaced_in_place(rodar_eval: ModuleType, tmp_path: Path) -> None:
    output = tmp_path / "RESULTADOS.md"
    rodar_eval.write_section(output, "offline", "## Modo offline\n\nprimeira\n")
    rodar_eval.write_section(output, "ao-vivo", "## Modo ao-vivo\n\nviva\n")
    rodar_eval.write_section(output, "offline", "## Modo offline\n\nsegunda\n")

    report = output.read_text("utf-8")
    assert report.startswith("# Resultados do eval do agente")
    assert "primeira" not in report and report.count("segunda") == 1
    assert report.index("segunda") < report.index("viva")


@pytest.mark.parametrize(
    ("stage", "expected", "live", "ok"),
    [
        ("ORIENTAR", "ANTECIPAR", True, True),
        ("ORIENTAR", "ANTECIPAR", False, False),
        ("ENTENDER", "ANTECIPAR", True, False),
    ],
)
def test_live_mode_accepts_a_later_stage(
    rodar_eval: ModuleType, stage: str, expected: str, live: bool, ok: bool
) -> None:
    result = rodar_eval.TurnResult(client="", stage=stage)
    [(_, passed)] = rodar_eval.check_expectations({"estado_jornada": expected}, result, set(), live)
    assert passed is ok


def test_live_without_answers_is_inconclusive(rodar_eval: ModuleType) -> None:
    case = rodar_eval.Case(id="q2", title="", live=True, state={}, turns=[])
    turn = rodar_eval.TurnResult(client="", unavailable=True)
    result = rodar_eval.CaseResult(case=case, turns=[turn])

    section = rodar_eval.render_section(rodar_eval.MODE_LIVE, [result], set(), "mock")
    assert "nenhum Gemini respondeu" in section
    assert "nenhum número nas respostas" in section and "100%" not in section
    summary = rodar_eval.summarize([result])
    assert rodar_eval.verdict(rodar_eval.MODE_LIVE, summary) == rodar_eval.VERDICT_INCONCLUSIVE
