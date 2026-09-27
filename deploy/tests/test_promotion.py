"""Modo promoção do chart (``templates/promotion.yaml``) e ``promote.jq``.

A promoção muda só o tráfego: o ``spec.template`` vivo vai sem mudança, para
o ``gcloud run services replace`` não criar revisão. Sem rede e sem GCP.
"""

import copy
import re

import pytest
import yaml
from helm_render import (
    ROOT,
    RenderError,
    helm_template,
    needs_helm,
    needs_jq,
    run_jq,
)

PROMOTE_FILTER = ROOT / "deploy" / "helm" / "promote.jq"

C000 = "bussola-agent-00001-mix"
MAIN = "bussola-agent-main-eee18b6-chips-local"
C007 = "bussola-agent-c007-aaaaaaa-1"


def described(
    traffic: list[dict],
    name: str = "bussola-agent",
    public: bool = False,
    ingress: str = "all",
) -> dict:
    """``gcloud run services describe --format=json`` fictício."""
    annotations = {
        "run.googleapis.com/ingress": ingress,
        "run.googleapis.com/ingress-status": ingress,
        "serving.knative.dev/creator": "alguem@example.com",
    }
    if public:
        annotations["run.googleapis.com/invoker-iam-disabled"] = "true"
    return {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {"name": name, "annotations": annotations, "generation": 7},
        "spec": {
            "template": {
                "metadata": {
                    "name": f"{name}-c007-aaaaaaa-1",
                    "labels": {"release-tag": "c007", "run.googleapis.com/startupProbeType": "x"},
                    "annotations": {"autoscaling.knative.dev/maxScale": "1"},
                },
                "spec": {
                    "containerConcurrency": 80,
                    "timeoutSeconds": 300,
                    "serviceAccountName": "sa@example.com",
                    "containers": [
                        {
                            "image": f"repo/{name}@sha256:{'b' * 64}",
                            "env": [
                                {"name": "REPLAY_START_ANOMES", "value": "202506"},
                                {"name": "MCP_USE_OIDC", "value": "TRUE"},
                                {
                                    "name": "GOOGLE_API_KEY",
                                    "valueFrom": {
                                        "secretKeyRef": {"name": "gemini-api-key", "key": "latest"}
                                    },
                                },
                            ],
                            "startupProbe": {"tcpSocket": {"port": 8080}, "periodSeconds": 240},
                        }
                    ],
                },
            },
            "traffic": [],
        },
        "status": {"traffic": traffic, "latestCreatedRevisionName": f"{name}-c007-aaaaaaa-1"},
    }


LIVE_TRAFFIC = [
    {"revisionName": C000, "percent": 100, "tag": "c000", "url": "https://c000---agent"},
    {"revisionName": MAIN, "tag": "main", "url": "https://main---agent"},
    {"revisionName": C007, "tag": "c007", "url": "https://c007---agent"},
]


def promotion_values(service: dict, key: str = "agent", target: str = "main") -> dict:
    return run_jq(PROMOTE_FILTER, service, key=key, target=target)


def render_promotion(tmp_path, values: dict) -> dict:
    return yaml.safe_load(helm_template("promotion.yaml", tmp_path, values))


def promote(tmp_path, service: dict, key: str = "agent", target: str = "main") -> dict:
    return render_promotion(tmp_path, promotion_values(service, key, target))


def applied(service: dict, manifest: dict) -> dict:
    """Estado vivo depois do ``replace``: o status reflete o tráfego pedido."""
    after = copy.deepcopy(service)
    after["status"]["traffic"] = manifest["spec"]["traffic"]
    return after


@needs_jq
def test_promote_filter_copies_live_state_without_deciding():
    service = described(LIVE_TRAFFIC, public=True)

    values = promotion_values(service, target="previous")["promotion"]

    assert values["service"] == "agent"
    assert values["target"] == "previous"
    assert values["live"]["name"] == "bussola-agent"
    assert values["live"]["public"] is True
    assert values["live"]["ingress"] == "all"
    assert values["live"]["template"] == service["spec"]["template"]
    assert values["live"]["traffic"] == [
        {"revisionName": C000, "percent": 100, "tag": "c000"},
        {"revisionName": MAIN, "percent": 0, "tag": "main"},
        {"revisionName": C007, "percent": 0, "tag": "c007"},
    ]


@needs_jq
def test_promote_filter_defaults_missing_annotations():
    service = described([{"revisionName": C000, "percent": 100}])
    del service["metadata"]["annotations"]

    live = promotion_values(service)["promotion"]["live"]

    assert live["public"] is False
    assert live["ingress"] == "all"
    assert live["traffic"] == [{"revisionName": C000, "percent": 100}]


@needs_jq
@needs_helm
def test_promotion_moves_all_traffic_and_marks_previous(tmp_path):
    manifest = promote(tmp_path, described(LIVE_TRAFFIC))

    assert manifest["spec"]["traffic"] == [
        {"revisionName": MAIN, "percent": 100},
        {"revisionName": C000, "percent": 0, "tag": "c000"},
        {"revisionName": MAIN, "percent": 0, "tag": "main"},
        {"revisionName": C007, "percent": 0, "tag": "c007"},
        {"revisionName": C000, "percent": 0, "tag": "previous"},
    ]


@needs_jq
@needs_helm
def test_promotion_keeps_live_template_so_no_revision_is_created(tmp_path):
    service = described(LIVE_TRAFFIC)

    manifest = promote(tmp_path, service)

    assert manifest["spec"]["template"] == service["spec"]["template"]
    env = manifest["spec"]["template"]["spec"]["containers"][0]["env"]
    assert {"name": "REPLAY_START_ANOMES", "value": "202506"} in env
    assert all("value" not in item for item in env if item["name"] == "GOOGLE_API_KEY")


@needs_jq
@needs_helm
def test_promotion_manifest_targets_the_service(tmp_path):
    manifest = promote(tmp_path, described(LIVE_TRAFFIC))

    assert manifest["apiVersion"] == "serving.knative.dev/v1"
    assert manifest["kind"] == "Service"
    assert manifest["metadata"]["name"] == "bussola-agent"
    assert manifest["metadata"]["namespace"] == "1061873050224"
    assert manifest["metadata"]["annotations"] == {"run.googleapis.com/ingress": "all"}


@needs_jq
@needs_helm
def test_rollback_returns_to_previous_revision(tmp_path):
    service = described(LIVE_TRAFFIC)
    promoted = applied(service, promote(tmp_path, service))

    rolled_back = promote(tmp_path, promoted, target="previous")

    traffic = rolled_back["spec"]["traffic"]
    assert traffic[0] == {"revisionName": C000, "percent": 100}
    assert {"revisionName": MAIN, "percent": 0, "tag": "previous"} in traffic
    assert {"revisionName": C000, "percent": 0, "tag": "c000"} in traffic
    assert {"revisionName": MAIN, "percent": 0, "tag": "main"} in traffic
    assert sum(entry["percent"] for entry in traffic) == 100
    assert len([entry for entry in traffic if entry.get("tag") == "previous"]) == 1


@needs_jq
@needs_helm
def test_promotion_accepts_a_revision_name_in_live_traffic(tmp_path):
    manifest = promote(tmp_path, described(LIVE_TRAFFIC), target=C007)

    assert manifest["spec"]["traffic"][0] == {"revisionName": C007, "percent": 100}


@needs_jq
@needs_helm
def test_bff_promotion_keeps_invoker_check_disabled(tmp_path):
    traffic = [
        {"revisionName": "bussola-bff-main-9766008-foco-local", "percent": 100},
        {"revisionName": "bussola-bff-main-1111111-local", "tag": "main"},
    ]
    service = described(traffic, name="bussola-bff", public=True)

    manifest = promote(tmp_path, service, key="bff")

    annotations = manifest["metadata"]["annotations"]
    assert annotations["run.googleapis.com/invoker-iam-disabled"] == "true"
    assert manifest["spec"]["traffic"][0] == {
        "revisionName": "bussola-bff-main-1111111-local",
        "percent": 100,
    }


@needs_jq
@needs_helm
def test_promotion_mode_does_not_need_release_values(tmp_path):
    values = promotion_values(described(LIVE_TRAFFIC))
    values["release"] = {"tag": "", "revisionSuffix": ""}

    assert render_promotion(tmp_path, values)["kind"] == "Service"
    with pytest.raises(RenderError, match="could not find template"):
        helm_template("agent-service.yaml", tmp_path, values)


@needs_jq
@needs_helm
@pytest.mark.parametrize(
    ("service", "key", "target", "message"),
    [
        (described(LIVE_TRAFFIC), "agent", "c999", 'o alvo "c999" não está no tráfego vivo'),
        (described(LIVE_TRAFFIC), "agent", "previous", 'o alvo "previous" não está'),
        (described(LIVE_TRAFFIC), "agent", "c000", "já recebe 100%"),
        (described(LIVE_TRAFFIC), "agent", C000, "já recebe 100%"),
        (described(LIVE_TRAFFIC), "agent", "", "promotion.target é obrigatório"),
        (described(LIVE_TRAFFIC), "web", "main", "promotion.service deve ser agent, bff, mcp"),
        (described(LIVE_TRAFFIC), "mcp", "main", 'o estado vivo é de "bussola-agent"'),
        (described(LIVE_TRAFFIC, public=True), "agent", "main", "Promover não muda IAM"),
        (described(LIVE_TRAFFIC, name="bussola-bff"), "bff", "main", "Promover não muda IAM"),
        (described(LIVE_TRAFFIC, ingress="internal"), "agent", "main", "ingress de bussola"),
        (
            described(
                [
                    {"revisionName": C000, "percent": 90, "tag": "c000"},
                    {"revisionName": MAIN, "percent": 10, "tag": "main"},
                ]
            ),
            "agent",
            "main",
            "não está 100% numa revisão",
        ),
    ],
)
def test_promotion_guards(service, key, target, message, tmp_path):
    with pytest.raises(RenderError, match=re.escape(message)):
        promote(tmp_path, service, key=key, target=target)


@needs_helm
def test_promotion_without_live_state_is_rejected(tmp_path):
    values = {"promotion": {"service": "agent", "target": "main", "live": {}}}

    with pytest.raises(RenderError, match="promotion.live.template é obrigatório"):
        render_promotion(tmp_path, values)
