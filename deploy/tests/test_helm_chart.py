"""Testes do chart ``deploy/helm/bussola``: renderiza com ``helm template``.

Também cobrem o filtro de tráfego (``deploy/helm/traffic.jq``) e a coerência
do workflow de deploy com o chart. Não acessam rede nem GCP. Sem ``helm`` (ou
``jq``) no PATH, os testes que dependem deles são pulados. Rodar com
``make test-helm``.
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
TRAFFIC_FILTER = ROOT / "deploy" / "helm" / "traffic.jq"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy.yml"
RELEASE = {"release": {"tag": "c007", "revisionSuffix": "c007-01"}}

needs_helm = pytest.mark.skipif(shutil.which("helm") is None, reason="helm não instalado")
needs_jq = pytest.mark.skipif(shutil.which("jq") is None, reason="jq não instalado")


class RenderError(Exception):
    """``helm template`` falhou; a mensagem traz o stderr."""


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def render(service: str, tmp_path: Path, overrides: dict[str, Any] | None = None) -> dict:
    values = tmp_path / "values-test.yaml"
    values.write_text(yaml.safe_dump(_merge(RELEASE, overrides or {})))
    result = subprocess.run(
        [
            "helm",
            "template",
            "bussola",
            str(CHART),
            "-f",
            str(values),
            "--show-only",
            f"templates/{service}-service.yaml",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RenderError(result.stderr)
    return yaml.safe_load(result.stdout)


def env_of(manifest: dict) -> dict[str, dict]:
    container = manifest["spec"]["template"]["spec"]["containers"][0]
    return {item["name"]: item for item in container["env"]}


@needs_helm
@pytest.mark.parametrize("service", ["agent", "mcp", "bff"])
def test_new_revision_gets_zero_traffic_and_release_tag(service, tmp_path):
    manifest = render(service, tmp_path)
    name = manifest["metadata"]["name"]
    revision = manifest["spec"]["template"]["metadata"]["name"]

    assert revision == f"{name}-c007-01"
    new_entry = manifest["spec"]["traffic"][-1]
    assert new_entry == {"revisionName": revision, "percent": 0, "tag": "c007"}


@needs_helm
@pytest.mark.parametrize("service", ["agent", "mcp"])
def test_kept_traffic_stays_at_100_percent(service, tmp_path):
    traffic = render(service, tmp_path)["spec"]["traffic"]

    assert sum(entry["percent"] for entry in traffic) == 100
    assert traffic[0]["percent"] == 100
    assert traffic[0]["tag"] == "c000"


@needs_helm
@pytest.mark.parametrize("service", ["agent", "mcp", "bff"])
def test_manifest_targets_cloud_run_project(service, tmp_path):
    manifest = render(service, tmp_path)

    assert manifest["apiVersion"] == "serving.knative.dev/v1"
    assert manifest["kind"] == "Service"
    assert manifest["metadata"]["namespace"] == "1061873050224"
    assert manifest["metadata"]["labels"]["cloud.googleapis.com/location"] == "us-central1"
    spec = manifest["spec"]["template"]["spec"]
    assert spec["serviceAccountName"] == "1061873050224-compute@developer.gserviceaccount.com"


@needs_helm
def test_agent_uses_gemini_api_key_from_secret_manager(tmp_path):
    env = env_of(render("agent", tmp_path))

    assert env["GOOGLE_GENAI_USE_VERTEXAI"]["value"] == "FALSE"
    assert "value" not in env["GOOGLE_API_KEY"]
    assert env["GOOGLE_API_KEY"]["valueFrom"]["secretKeyRef"] == {
        "name": "gemini-api-key",
        "key": "latest",
    }


@needs_helm
def test_bff_calls_agent_main_tag_with_service_audience(tmp_path):
    env = env_of(render("bff", tmp_path))

    assert env["AGENT_URL"]["value"] == "https://main---bussola-agent-wimifi56uq-uc.a.run.app"
    assert env["AGENT_AUDIENCE"]["value"] == "https://bussola-agent-wimifi56uq-uc.a.run.app"
    assert env["AGENT_USE_OIDC"]["value"] == "TRUE"
    assert "value" not in env["AUTH_PASSWORD_HASH"]
    assert env["AUTH_PASSWORD_HASH"]["valueFrom"]["secretKeyRef"] == {
        "name": "bussola-auth-password-hash",
        "key": "latest",
    }


@needs_helm
@pytest.mark.parametrize(("service", "public"), [("agent", False), ("mcp", False), ("bff", True)])
def test_only_bff_disables_invoker_check(service, public, tmp_path):
    annotations = render(service, tmp_path)["metadata"]["annotations"]

    assert annotations["run.googleapis.com/ingress"] == "all"
    assert ("run.googleapis.com/invoker-iam-disabled" in annotations) is public
    if public:
        assert annotations["run.googleapis.com/invoker-iam-disabled"] == "true"


@needs_helm
def test_create_gives_first_revision_all_traffic(tmp_path):
    release = {"release": {"tag": "main", "revisionSuffix": "main-aaaaaaa-local"}}
    overrides = _merge(release, {"services": {"bff": {"create": True, "traffic": None}}})

    traffic = render("bff", tmp_path, overrides)["spec"]["traffic"]

    assert traffic == [
        {"revisionName": "bussola-bff-main-aaaaaaa-local", "percent": 100, "tag": "main"}
    ]


@needs_helm
def test_create_is_rejected_when_service_has_traffic(tmp_path):
    with pytest.raises(RenderError, match="create só vale para serviço novo"):
        render("bff", tmp_path, {"services": {"bff": {"create": True}}})


@needs_helm
def test_mcp_reads_bigquery_in_memory_mode(tmp_path):
    env = env_of(render("mcp", tmp_path))

    assert env["BQ_MODO_LEITURA"]["value"] == "memoria"
    assert env["RAG_BACKEND"]["value"] == "lexico"


@needs_helm
def test_image_accepts_tag_and_digest(tmp_path):
    digest = "sha256:" + "a" * 64
    by_tag = render("agent", tmp_path)
    by_digest = render("agent", tmp_path, {"services": {"agent": {"image": digest}}})

    image = by_tag["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image.endswith("/agentes/bussola-agent:09aaeeb")
    image = by_digest["spec"]["template"]["spec"]["containers"][0]["image"]
    assert image.endswith(f"/agentes/bussola-agent@{digest}")


@needs_helm
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"release": {"tag": ""}}, "release.tag é obrigatório"),
        ({"release": {"tag": "v7"}}, "release.tag deve ser main ou cNNN"),
        ({"release": {"tag": "main-2"}}, "release.tag deve ser main ou cNNN"),
        ({"release": {"revisionSuffix": ""}}, "release.revisionSuffix é obrigatório"),
        ({"release": {"revisionSuffix": "C007_01"}}, "release.revisionSuffix aceita só"),
        ({"release": {"revisionSuffix": "x" * 60}}, "mais de 63 caracteres"),
        ({"release": {"tag": "c000"}}, "a tag c000 já está na revisão"),
    ],
)
def test_invalid_release_is_rejected(overrides, message, tmp_path):
    with pytest.raises(RenderError, match=message):
        render("agent", tmp_path, overrides)


@needs_helm
def test_kept_traffic_must_sum_100(tmp_path):
    traffic = [{"revisionName": "bussola-agent-00001-mix", "percent": 90, "tag": "c000"}]

    with pytest.raises(RenderError, match="deve somar 100%"):
        render("agent", tmp_path, {"services": {"agent": {"traffic": traffic}}})


@needs_helm
def test_missing_traffic_without_create_is_rejected(tmp_path):
    with pytest.raises(RenderError, match="soma 0%"):
        render("bff", tmp_path, {"services": {"bff": {"traffic": None}}})


@needs_helm
@pytest.mark.parametrize("name", ["GOOGLE_API_KEY", "SESSION_TOKEN", "DB_PASSWORD", "MY_SECRET"])
def test_secret_like_plain_env_is_rejected(name, tmp_path):
    overrides = {"services": {"agent": {"env": {name: "x"}, "secretEnv": {}}}}

    with pytest.raises(RenderError, match=f"{name} parece segredo"):
        render("agent", tmp_path, overrides)


@needs_helm
def test_rendered_chart_has_no_literal_secret_values(tmp_path):
    for service in ("agent", "mcp", "bff"):
        for item in env_of(render(service, tmp_path)).values():
            if "valueFrom" in item:
                assert set(item) == {"name", "valueFrom"}


def live_traffic(entries: list[dict], key: str, tag: str) -> dict[str, Any]:
    """Roda ``traffic.jq`` como o workflow, sobre um ``services describe`` fictício."""
    described = json.dumps({"status": {"traffic": entries}})
    result = subprocess.run(
        ["jq", "--arg", "key", key, "--arg", "tag", tag, "-f", str(TRAFFIC_FILTER)],
        input=described,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


SERVING = {"revisionName": "bussola-agent-00001-mix", "percent": 100}
C000 = {"revisionName": "bussola-agent-00001-mix", "tag": "c000", "url": "https://c000---agent"}
MAIN_BEFORE = {
    "revisionName": "bussola-agent-main-aaaaaaa-1",
    "tag": "main",
    "url": "https://main---agent",
}
MAIN_RELEASE = {"release": {"tag": "main", "revisionSuffix": "main-bbbbbbb-1"}}


@needs_jq
def test_live_traffic_keeps_percentages_and_frees_the_new_tag():
    traffic = live_traffic([SERVING, C000, MAIN_BEFORE], "agent", "main")

    assert traffic == {
        "services": {
            "agent": {
                "traffic": [
                    {"revisionName": "bussola-agent-00001-mix", "percent": 100},
                    {"revisionName": "bussola-agent-00001-mix", "percent": 0, "tag": "c000"},
                ]
            }
        }
    }


@needs_jq
def test_live_traffic_moves_main_tag_off_a_serving_revision():
    promoted = {"revisionName": "bussola-agent-main-aaaaaaa-1", "percent": 100, "tag": "main"}

    traffic = live_traffic([promoted], "agent", "main")["services"]["agent"]["traffic"]

    assert traffic == [{"revisionName": "bussola-agent-main-aaaaaaa-1", "percent": 100}]


@needs_jq
def test_live_traffic_drops_untagged_idle_entries():
    idle = {"revisionName": "bussola-agent-00002-old", "percent": 0}

    traffic = live_traffic([SERVING, idle], "agent", "main")["services"]["agent"]["traffic"]

    assert traffic == [{"revisionName": "bussola-agent-00001-mix", "percent": 100}]


@needs_jq
@needs_helm
def test_main_deploy_renders_new_revision_without_moving_traffic(tmp_path):
    overrides = _merge(MAIN_RELEASE, live_traffic([SERVING, C000, MAIN_BEFORE], "agent", "main"))

    traffic = render("agent", tmp_path, overrides)["spec"]["traffic"]

    assert traffic == [
        {"revisionName": "bussola-agent-00001-mix", "percent": 100},
        {"revisionName": "bussola-agent-00001-mix", "percent": 0, "tag": "c000"},
        {"revisionName": "bussola-agent-main-bbbbbbb-1", "percent": 0, "tag": "main"},
    ]


@needs_jq
@needs_helm
def test_cycle_tag_serving_traffic_cannot_be_reused(tmp_path):
    serving_c000 = {"revisionName": "bussola-agent-00001-mix", "percent": 100, "tag": "c000"}
    release = {"release": {"tag": "c000", "revisionSuffix": "c000-bbbbbbb-1"}}
    overrides = _merge(release, live_traffic([serving_c000], "agent", "c000"))

    with pytest.raises(RenderError, match="a tag c000 já está na revisão"):
        render("agent", tmp_path, overrides)


def test_deploy_workflow_matches_chart_values():
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    env = yaml.safe_load(DEPLOY_WORKFLOW.read_text())["env"]
    services = json.loads(env["SERVICES"])

    assert env["GCP_PROJECT"] == values["project"]["id"]
    assert env["GCP_REGION"] == values["project"]["region"]
    assert env["IMAGE_REPOSITORY"] == values["imageRepository"]
    assert Path(ROOT / env["CHART"]) == CHART
    assert {item["key"]: item["name"] for item in services} == {
        key: service["name"] for key, service in values["services"].items()
    }
    for item in services:
        assert (ROOT / item["dockerfile"]).is_file()
        assert (CHART / "templates" / f"{item['key']}-service.yaml").is_file()
