"""Pipelines do GitHub Actions (Q-18 do 000; constituição VII e X).

CI com ``make lint`` e ``make test`` em modo fake. CD só por Workload Identity
Federation, sem chave de SA, sem mover tráfego, sem mexer em IAM e sem
interpolar entrada do disparo direto no shell.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
WORKFLOWS = RAIZ / ".github" / "workflows"
CI = WORKFLOWS / "ci.yml"
DEPLOY = WORKFLOWS / "deploy.yml"

_EXPRESSAO_DE_ENTRADA = re.compile(r"\$\{\{\s*(inputs|github\.event\.inputs)\.")
# Entrada só pode aparecer em atribuição de env/with ou em "if:" (nunca em "run:").
_USO_SEGURO = re.compile(
    r"^\s*(if: .*|[A-Za-z_][A-Za-z0-9_-]*: \$\{\{\s*inputs\.[a-z_]+\s*\}\})\s*$"
)


def _workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def test_existem_ci_e_deploy():
    assert CI.is_file()
    assert DEPLOY.is_file()


def test_ci_roda_make_lint_e_make_test_em_modo_fake():
    texto = _texto(CI)
    assert re.search(r"^\s*run: make lint\s*$", texto, re.MULTILINE)
    assert re.search(r"^\s*run: make test\s*$", texto, re.MULTILINE)
    assert re.search(r'BUSSOLA_FAKES: "TRUE"', texto)
    assert "id-token" not in texto  # o CI não fala com o GCP
    assert "workflow_call" in texto  # o deploy reaproveita o CI


def test_deploy_so_por_disparo_manual_e_depois_do_ci():
    texto = _texto(DEPLOY)
    gatilhos = texto.split("\non:", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  ([a-z_]+):", gatilhos, re.MULTILINE) == ["workflow_dispatch"]
    assert "uses: ./.github/workflows/ci.yml" in texto
    assert re.search(r"^\s*needs: ci\s*$", texto, re.MULTILINE)


def test_deploy_usa_wif_e_os_scripts_de_deploy():
    texto = _texto(DEPLOY)
    assert "google-github-actions/auth@" in texto
    assert "workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}" in texto
    assert "id-token: write" in texto
    assert "deploy/build_push.sh" in texto
    assert re.search(r'deploy/deploy\.sh \w+ --tag "\$TAG_REVISAO"', texto)


@pytest.mark.parametrize("caminho", _workflows(), ids=lambda p: p.name)
def test_workflow_nao_usa_chave_de_sa_nem_segredo(caminho):
    texto = _texto(caminho)
    assert "credentials_json" not in texto
    assert not re.search(r"secrets\.(?!GITHUB_TOKEN\b)", texto)


# Só os workflows do 000: a promoção de tráfego do 007 terá workflow próprio.
@pytest.mark.parametrize("caminho", [CI, DEPLOY], ids=lambda p: p.name)
def test_ci_e_deploy_nao_movem_trafego_nem_mexem_em_iam(caminho):
    proibido = re.compile(
        r"update-traffic|--to-latest|--to-revisions|iam-policy|(?<!no-)--allow-unauthenticated"
    )
    assert not proibido.search(_texto(caminho))


@pytest.mark.parametrize("caminho", _workflows(), ids=lambda p: p.name)
def test_workflow_declara_permissoes_minimas(caminho):
    texto = _texto(caminho)
    assert re.search(r"^permissions:\n  contents: read\n", texto, re.MULTILINE)
    assert "write-all" not in texto


@pytest.mark.parametrize("caminho", _workflows(), ids=lambda p: p.name)
def test_entrada_do_disparo_nao_vai_direto_para_o_shell(caminho):
    inseguras = [
        f"{caminho.name}:{n}"
        for n, linha in enumerate(_texto(caminho).splitlines(), start=1)
        if _EXPRESSAO_DE_ENTRADA.search(linha) and not _USO_SEGURO.match(linha)
    ]
    assert inseguras == []


@pytest.mark.parametrize(
    "linha, segura",
    [
        ("      TAG_REVISAO: ${{ inputs.tag }}", True),
        ("        if: inputs.servico != 'agent'", True),
        ('        run: deploy/deploy.sh mcp --tag "${{ inputs.tag }}"', False),
        ("          echo ${{ github.event.inputs.tag }}", False),
    ],
)
def test_detector_de_entrada_no_shell(linha, segura):
    insegura = bool(_EXPRESSAO_DE_ENTRADA.search(linha)) and not _USO_SEGURO.match(linha)
    assert insegura is not segura
