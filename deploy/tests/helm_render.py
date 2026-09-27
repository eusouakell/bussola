"""Apoio aos testes do chart: ``helm template`` e ``jq`` como no workflow.

Sem rede e sem GCP. Sem ``helm`` (ou ``jq``) no PATH, os testes marcados com
``needs_helm`` (``needs_jq``) são pulados.
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "deploy" / "helm" / "bussola"
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE = {"release": {"tag": "c007", "revisionSuffix": "c007-01"}}

needs_helm = pytest.mark.skipif(shutil.which("helm") is None, reason="helm não instalado")
needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq não instalado")


class RenderError(Exception):
    """``helm template`` falhou; a mensagem traz o stderr."""


def merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def helm_template(
    template: str,
    tmp_path: Path,
    values: dict[str, Any],
    values_files: tuple[Path, ...] = (),
) -> str:
    """Renderiza ``templates/<template>`` com os overlays e depois ``values``."""
    values_path = tmp_path / "values-test.yaml"
    values_path.write_text(yaml.safe_dump(values))
    command = ["helm", "template", "bussola", str(CHART)]
    for path in (*values_files, values_path):
        command += ["-f", str(path)]
    command += ["--show-only", f"templates/{template}"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RenderError(result.stderr)
    return result.stdout


def render(
    service: str,
    tmp_path: Path,
    overrides: dict[str, Any] | None = None,
    values_files: tuple[Path, ...] = (),
) -> dict:
    """Manifesto do modo deploy (``templates/<service>-service.yaml``)."""
    values = merge(RELEASE, overrides or {})
    return yaml.safe_load(helm_template(f"{service}-service.yaml", tmp_path, values, values_files))


def env_of(manifest: dict) -> dict[str, dict]:
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    return {item["name"]: item for item in container["env"]}


def run_jq(filter_path: Path, document: dict, **args: str) -> dict:
    command = ["jq"]
    for name, value in args.items():
        command += ["--arg", name, value]
    command += ["-f", str(filter_path)]
    result = subprocess.run(
        command, input=json.dumps(document), capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)
