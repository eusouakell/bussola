"""Fixtures v1 (plan.md D-07, FR-016): ``build_dados.py --fixtures`` e consistência.

Tudo offline. O BigQuery é emulado por um cliente que responde às leituras de
``RepositorioBigQuery.build_queries`` a partir das tabelas de ``contracts/fixtures``:
exportar de novo precisa reproduzir byte a byte os arquivos versionados.
"""

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from google.cloud.bigquery.table import Row

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    arquivo_golden,
    arquivo_resumo_mes,
)
from bussola_mcp.dominio import metricas
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.dominio.repositorio_bq import TABLE_MODELS, RepositorioBigQuery, build_queries

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMITTED = REPO_ROOT / "contracts" / "fixtures"
_TABLE_RE = re.compile(r"FROM `([a-z0-9_]+)\.([a-z_]+)`")


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / "data" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"bussola_scripts_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build = _load_script("build_dados")
gerar = _load_script("gerar_fixtures")


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tables(base: Path) -> dict[str, list[dict[str, Any]]]:
    return {nome: _read(base / "bussola_dados" / f"{nome}.json") for nome in TABLE_MODELS}


class _Job:
    def __init__(self, rows: list[Row]) -> None:
        self._rows = rows

    def result(self) -> list[Row]:
        return self._rows


class ReadOnlyBigQuery:
    """Responde às leituras do ``RepositorioBigQuery`` e registra cada SQL executado."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]], fail: bool = False) -> None:
        self.tables = tables
        self.fail = fail
        self.calls: list[tuple[str, str | None]] = []

    def query(self, sql: str, job_config: Any = None, location: str | None = None) -> _Job:
        self.calls.append((sql, location))
        if self.fail:
            raise RuntimeError("falha interna com detalhe que não pode vazar")
        values = {p.name: p.value for p in job_config.query_parameters}
        match = _TABLE_RE.search(sql)
        assert match is not None
        rows = [r for r in self.tables[match.group(2)] if self._matches(r, values)]
        return _Job([Row(tuple(r.values()), {c: i for i, c in enumerate(r)}) for r in rows])

    @staticmethod
    def _matches(row: dict[str, Any], values: dict[str, Any]) -> bool:
        if "id_usuario" in values and row["id_usuario"] != values["id_usuario"]:
            return False
        if "ate_anomes" in values and row["anomes"] > values["ate_anomes"]:
            return False
        if values.get("desde_anomes") is not None and row["anomes"] < values["desde_anomes"]:
            return False
        if "faixa_renda" in values and row["faixa_renda"] != values["faixa_renda"]:
            return False
        return values.get("macro") is None or row["macro"] == values["macro"]


def _preexisting(output: Path) -> dict[str, str]:
    """Arquivos que o export não pode tocar (personas do 008 e corpus do RAG)."""
    keep = {
        "bussola_dados/users.json": '[{"sentinela": true}]\n',
        "rag/trechos_exemplo.json": '[{"sentinela": "rag"}]\n',
    }
    for relative, text in keep.items():
        (output / relative).parent.mkdir(parents=True, exist_ok=True)
        (output / relative).write_text(text, encoding="utf-8")
    return keep


def _written(output: Path) -> dict[str, str]:
    return {
        str(p.relative_to(output)): p.read_text(encoding="utf-8")
        for p in sorted(output.rglob("*.json"))
    }


# ---------------------------------------------------------------------------
# Consistência das fixtures versionadas (T014, AC-07)
# ---------------------------------------------------------------------------

GOLDEN_CALLS = [
    (arquivo_golden(tool, cut), tool, cut, build.GOLDEN_ARGUMENTS.get(tool, {}))
    for cut in CORTES_GOLDEN
    for tool in FERRAMENTAS_GOLDEN
] + [
    (arquivo_resumo_mes(anomes), "resumo_mes", anomes, {"anomes": anomes})
    for anomes in range(202501, 202513)
]


@pytest.mark.parametrize(("arquivo", "tool", "ate", "kwargs"), GOLDEN_CALLS)
def test_golden_versionado_igual_a_metricas_sobre_as_linhas(arquivo, tool, ate, kwargs):
    repo = RepositorioFake(COMMITTED)
    resultado = getattr(metricas, tool)(repo, ID_ANCORA, ate, **kwargs)
    assert metricas.build_envelope(tool, resultado) == _read(COMMITTED / "ferramentas" / arquivo)


def test_entradas_canonicas_dos_goldens():
    assert build.GOLDEN_ARGUMENTS["simular_objetivo"] == ENTRADA_CANONICA_SIMULACAO
    assert build.GOLDEN_ARGUMENTS["comparar_cenarios"] == ENTRADA_CANONICA_SIMULACAO
    assert build.GOLDEN_ARGUMENTS["oportunidades_corte"] == {"top_n": gerar.TOP_MAX}


def test_resumo_mes_nao_depende_do_corte():
    repo = RepositorioFake(COMMITTED)
    for anomes in (202501, 202506, 202512):
        no_mes = metricas.resumo_mes(repo, ID_ANCORA, anomes, anomes)
        no_fim = metricas.resumo_mes(repo, ID_ANCORA, 202512, anomes)
        assert metricas.build_envelope("resumo_mes", no_mes) == metricas.build_envelope(
            "resumo_mes", no_fim
        )


# ---------------------------------------------------------------------------
# build_dados.py --fixtures (T012)
# ---------------------------------------------------------------------------


def test_export_via_bigquery_reproduz_as_fixtures_versionadas(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = ReadOnlyBigQuery(_tables(COMMITTED))
    keep = _preexisting(tmp_path)
    argv = ["--projeto", "p", "--fixtures", str(tmp_path)]
    assert build.main(argv, create_client=lambda project: client) == 0

    written = _written(tmp_path)
    for relative, text in keep.items():
        assert written.pop(relative) == text
    assert len(written) == 1 + len(TABLE_MODELS) + 2 * len(FERRAMENTAS_GOLDEN) + 12
    for relative, text in written.items():
        assert text == (COMMITTED / relative).read_text(encoding="utf-8"), relative

    out = capsys.readouterr().out
    assert "bussola_dados/perfil_mensal.json: 24 linhas" in out
    assert ID_ANCORA not in out and ID_CONTROLE not in out


def test_export_so_le_e_usa_us_central1(tmp_path: Path) -> None:
    client = ReadOnlyBigQuery(_tables(COMMITTED))
    assert build.main(["--projeto", "p", "--fixtures", str(tmp_path)], lambda p: client) == 0
    allowed = set(build_queries("bussola_dados").values())
    assert client.calls
    for sql, location in client.calls:
        assert sql in allowed
        assert location == "us-central1"
        assert not re.search(r"\b(INSERT|TRUNCATE|CREATE|DELETE|MERGE|UPDATE|DROP)\b", sql)


def test_fixture_repository_le_em_modo_query() -> None:
    repo = build.fixture_repository(object(), "bussola_dados_teste")
    assert isinstance(repo, RepositorioBigQuery)
    assert (repo.modo, repo.dataset) == ("query", "bussola_dados_teste")


def test_conjunto_sintetico_valido(fixtures_sinteticas: Path) -> None:
    data = build.build_fixture_set(RepositorioFake(fixtures_sinteticas))
    gerar.validar_conjunto(data)
    assert "bussola_dados/users.json" not in data
    assert not [k for k in data if k.startswith("rag/")]
    assert [u["papel"] for u in data["usuarios.json"]] == ["ancora", "controle"]
    assert {len(data["bussola_dados/perfil_mensal.json"])} == {24}
    fonte = data[f"ferramentas/{arquivo_golden('perfil_financeiro', 202506)}"]["fonte"]
    assert fonte["periodo"] == {"inicio": 202501, "fim": 202506}


def test_meses_faltando_sai_2_sem_gravar(
    fixtures_sinteticas: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tables = _tables(fixtures_sinteticas)
    tables["perfil_mensal"] = [
        r
        for r in tables["perfil_mensal"]
        if not (r["id_usuario"] == ID_CONTROLE and r["anomes"] == 202503)
    ]
    client = ReadOnlyBigQuery(tables)
    output = tmp_path / "saida"
    assert build.main(["--projeto", "p", "--fixtures", str(output)], lambda p: client) == 2
    assert not output.exists()
    err = capsys.readouterr().err
    assert "controle" in err and ID_CONTROLE not in err


def test_falha_do_bigquery_sai_2_com_mensagem_generica(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    client = ReadOnlyBigQuery(_tables(COMMITTED), fail=True)
    assert build.main(["--projeto", "p", "--fixtures", str(tmp_path)], lambda p: client) == 2
    err = capsys.readouterr().err
    assert "indisponível" in err and "detalhe" not in err
    assert _written(tmp_path) == {}


def test_conjunto_fora_do_contrato_sai_3_sem_gravar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    golden = copy.deepcopy(
        _read(COMMITTED / "ferramentas" / arquivo_golden("perfil_financeiro", 202506))
    )
    golden["fonte"]["ferramenta"] = "capacidade_poupanca"
    path = f"ferramentas/{arquivo_golden('perfil_financeiro', 202506)}"
    monkeypatch.setattr(build, "fixture_goldens", lambda repository: {path: golden})
    client = ReadOnlyBigQuery(_tables(COMMITTED))
    assert build.main(["--projeto", "p", "--fixtures", str(tmp_path)], lambda p: client) == 3
    assert "fora do contrato" in capsys.readouterr().err
    assert _written(tmp_path) == {}


def test_sem_projeto_sai_2_antes_do_cliente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

    def forbidden(project: str) -> Any:
        raise AssertionError("não devia criar cliente BigQuery")

    assert build.main(["--fixtures", str(tmp_path)], create_client=forbidden) == 2


@pytest.mark.parametrize("other", ["--dry-run", "--somente-validar"])
def test_fixtures_exclui_os_outros_modos(other: str, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        build.main([other, "--fixtures", str(tmp_path)])
    assert exc.value.code == 2
