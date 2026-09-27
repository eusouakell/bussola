"""Workflow ``promote.yml``: coerente com o chart e com as regras de tráfego.

Só ele move tráfego, com environment protegido e confirmação digitada. O
``ci.yml`` e o ``deploy.yml`` seguem sem promoção. Sem rede e sem GCP.
"""

import re

import pytest
import yaml
from helm_render import CHART, ROOT, WORKFLOWS

PROMOTE_WORKFLOW = WORKFLOWS / "promote.yml"
DEPLOY_WORKFLOW = WORKFLOWS / "deploy.yml"
CI_WORKFLOW = WORKFLOWS / "ci.yml"


def _workflow(path) -> dict:
    return yaml.safe_load(path.read_text())


def _triggers(workflow: dict) -> dict:
    # PyYAML lê a chave "on" como True (YAML 1.1).
    return workflow.get("on") or workflow[True]


def _steps_text(workflow: dict) -> str:
    return "\n".join(
        str(step.get("run", "")) for job in workflow["jobs"].values() for step in job["steps"]
    )


def test_promote_workflow_is_manual_with_service_target_and_confirmation():
    workflow = _workflow(PROMOTE_WORKFLOW)
    values = yaml.safe_load((CHART / "values.yaml").read_text())

    triggers = _triggers(workflow)
    assert list(triggers) == ["workflow_dispatch"]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"service", "target", "confirm"}
    assert inputs["service"]["type"] == "choice"
    assert set(inputs["service"]["options"]) == set(values["services"])
    assert inputs["target"]["default"] == "main"
    assert all(item["required"] for item in inputs.values())


def test_promote_workflow_needs_protected_environment_and_wif():
    workflow = _workflow(PROMOTE_WORKFLOW)
    text = PROMOTE_WORKFLOW.read_text()

    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"].values()
    gcp_jobs = [job for job in jobs if "id-token" in job.get("permissions", {})]
    assert len(gcp_jobs) == 1
    assert gcp_jobs[0]["environment"] == "production"
    assert gcp_jobs[0]["permissions"] == {"contents": "read", "id-token": "write"}
    assert "workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}" in text
    assert "credentials_json" not in text


def test_promote_workflow_renders_through_the_chart_and_dry_runs_first():
    run = _steps_text(_workflow(PROMOTE_WORKFLOW))

    assert "-f deploy/helm/promote.jq" in run
    assert "--show-only templates/promotion.yaml" in run
    dry_run = run.index("gcloud run services replace")
    assert "--dry-run" in run[dry_run : run.index("\n", run.index("--region", dry_run))]
    assert run.count("gcloud run services replace") == 2
    assert run.index("--dry-run") < run.rindex("gcloud run services replace")


def test_promote_workflow_verifies_result_and_no_new_revision():
    run = _steps_text(_workflow(PROMOTE_WORKFLOW))

    assert "latestCreatedRevisionName" in run
    assert "previous" in run  # resumo com o comando de rollback


def test_promote_workflow_never_touches_iam_or_prints_tokens():
    text = PROMOTE_WORKFLOW.read_text()

    forbidden = re.compile(
        r"update-traffic|iam-policy|--allow-unauthenticated|gcloud run deploy|"
        r"print-identity-token|print-access-token|deploy/\w+\.sh"
    )
    assert not forbidden.search(text)


def test_promote_workflow_shares_deploy_concurrency_and_settings():
    promote_workflow = _workflow(PROMOTE_WORKFLOW)
    deploy_workflow = _workflow(DEPLOY_WORKFLOW)
    values = yaml.safe_load((CHART / "values.yaml").read_text())

    assert promote_workflow["concurrency"]["group"] == deploy_workflow["concurrency"]["group"]
    assert promote_workflow["concurrency"]["cancel-in-progress"] is False
    env = promote_workflow["env"]
    assert env["GCP_PROJECT"] == values["project"]["id"]
    assert env["GCP_REGION"] == values["project"]["region"]
    assert (ROOT / env["CHART"]) == CHART


@pytest.mark.parametrize("path", [CI_WORKFLOW, DEPLOY_WORKFLOW], ids=lambda p: p.name)
def test_ci_and_deploy_do_not_promote(path):
    text = path.read_text()

    assert "promotion.yaml" not in text
    assert "promote.jq" not in text
