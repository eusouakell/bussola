"""Scripts de ``deploy/`` com binários falsos (FR-023, FR-024, AC-13, constituição VII e X).

``docker``, ``gcloud`` e ``bq`` falsos registram cada chamada em ``chamadas.log``
e respondem com sucesso. Os testes conferem os argumentos, sem rede e sem GCP:
revisão com ``--tag cNNN``, serviço privado, ``--no-traffic`` em serviço
existente, segredo só por ``--set-secrets`` e IAM só com confirmação humana.

Adaptado da branch ``alt/000-fundacao-contratos-claude`` (João Paulo).
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
DEPLOY = RAIZ / "deploy"
SCRIPTS = ["build_push.sh", "deploy.sh", "iam_datasets.sh"]
AR = "us-central1-docker.pkg.dev/batalha-time-07-lkbv/agentes"
SA_DEFAULT = "1061873050224-compute@developer.gserviceaccount.com"
URL_MCP = "https://bussola-mcp-1061873050224.us-central1.run.app"

# $4 de "gcloud run services describe <serviço>" é o nome do serviço.
GCLOUD_FALSO = """#!/bin/sh
echo "gcloud $*" >> "{log}"
case "$1 $2 $3" in
  "run services describe")
    case " $FAKE_SERVICOS " in
      *" $4 "*) echo "https://$4-1061873050224.us-central1.run.app"; exit 0 ;;
    esac
    echo "ERROR: (gcloud.run.services.describe) Cannot find service [$4]" >&2
    exit 1
    ;;
  "projects describe "*) echo "1061873050224" ;;
esac
exit 0
"""
BINARIO_FALSO = '#!/bin/sh\necho "{nome} $*" >> "{log}"\nexit 0\n'


@pytest.fixture
def binarios(tmp_path):
    """Pasta com docker/gcloud/bq falsos e o caminho do log de chamadas."""
    pasta = tmp_path / "bin"
    pasta.mkdir()
    log = tmp_path / "chamadas.log"
    for nome in ("docker", "gcloud", "bq"):
        modelo = GCLOUD_FALSO if nome == "gcloud" else BINARIO_FALSO
        exe = pasta / nome
        exe.write_text(modelo.format(nome=nome, log=log), encoding="utf-8")
        exe.chmod(0o755)
    return pasta, log


def _rodar(script: str, *args: str, binarios, servicos: str = "", **env_extra: str):
    pasta, _ = binarios
    env = {
        "PATH": f"{pasta}:{os.environ['PATH']}",
        "HOME": str(pasta.parent),
        "FAKE_SERVICOS": servicos,
        **env_extra,
    }
    return subprocess.run(
        ["bash", str(DEPLOY / script), *args],
        cwd=RAIZ,
        env=env,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # sem terminal de controle: /dev/tty indisponível
        timeout=60,
    )


def _chamadas(binarios, prefixo: str = "") -> list[str]:
    _, log = binarios
    if not log.exists():
        return []
    return [
        linha for linha in log.read_text(encoding="utf-8").splitlines() if linha.startswith(prefixo)
    ]


def _deploy(binarios) -> str:
    chamadas = _chamadas(binarios, "gcloud run deploy ")
    assert len(chamadas) == 1, chamadas
    return chamadas[0]


def _envs(comando: str) -> dict[str, str]:
    lista = re.search(r"--set-env-vars (\S+)", comando).group(1)
    return dict(par.split("=", 1) for par in lista.split(","))


@pytest.mark.parametrize("script", SCRIPTS)
def test_sintaxe_bash(script):
    subprocess.run(["bash", "-n", str(DEPLOY / script)], check=True)


# ---------------------------------------------------------------------------
# build_push.sh
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("alvo", "dockerfile", "imagem"),
    [
        ("mcp", "mcp_server/Dockerfile", "bussola-mcp"),
        ("bussola-agent", "agent/Dockerfile", "bussola-agent"),
    ],
)
def test_build_push_amd64_para_o_artifact_registry(alvo, dockerfile, imagem, binarios):
    r = _rodar("build_push.sh", alvo, "c000", binarios=binarios)
    assert r.returncode == 0, r.stderr
    (build,) = _chamadas(binarios, "docker buildx build ")
    assert "--platform linux/amd64" in build
    assert f"--file {RAIZ / dockerfile} " in build
    assert f"--tag {AR}/{imagem}:c000 " in build
    assert build.endswith(f"--push {RAIZ}")


@pytest.mark.parametrize(
    ("args", "codigo"),
    [((), 2), (("outro-servico",), 1), (("mcp", "c000", "extra"), 1), (("mcp", "tag inválida"), 1)],
)
def test_build_push_argumentos_invalidos_nao_chamam_o_docker(args, codigo, binarios):
    assert _rodar("build_push.sh", *args, binarios=binarios).returncode == codigo
    assert _chamadas(binarios, "docker") == []


# ---------------------------------------------------------------------------
# deploy.sh
# ---------------------------------------------------------------------------


def test_deploy_de_servico_novo_cria_privado_com_tag(binarios):
    r = _rodar("deploy.sh", "mcp", "--imagem", "c000", binarios=binarios)
    assert r.returncode == 0, r.stderr
    comando = _deploy(binarios)
    assert comando.startswith("gcloud run deploy bussola-mcp ")
    assert "--project batalha-time-07-lkbv" in comando
    assert "--region us-central1" in comando
    assert f"--image {AR}/bussola-mcp:c000" in comando
    assert f"--service-account {SA_DEFAULT}" in comando
    assert "--max-instances 1" in comando
    assert "--tag c000" in comando
    assert "--no-allow-unauthenticated" in comando
    assert re.search(r"(?<!no-)--allow-unauthenticated", comando) is None
    # O gcloud não aceita --no-traffic na criação.
    assert "--no-traffic" not in comando
    assert _envs(comando)["BUSSOLA_FAKES"] == "TRUE"


def test_deploy_em_servico_existente_sai_sem_trafego_e_sem_mexer_no_iam(binarios):
    r = _rodar(
        "deploy.sh",
        "mcp",
        "--tag",
        "c001",
        "--imagem",
        "c001",
        binarios=binarios,
        servicos="bussola-mcp",
    )
    assert r.returncode == 0, r.stderr
    comando = _deploy(binarios)
    assert "--tag c001" in comando
    assert "--no-traffic" in comando
    assert "--clear-secrets" in comando
    assert "allow-unauthenticated" not in comando


def test_deploy_do_agente_aponta_para_o_mcp_com_oidc(binarios):
    r = _rodar("deploy.sh", "agent", "--imagem", "c000", binarios=binarios, servicos="bussola-mcp")
    assert r.returncode == 0, r.stderr
    envs = _envs(_deploy(binarios))
    assert envs["MCP_URL"] == f"{URL_MCP}/mcp"
    assert envs["MCP_USE_OIDC"] == "TRUE"
    assert envs["GOOGLE_CLOUD_LOCATION"] == "global"  # BUSSOLA_LOCAL_MODELO (Q-15)
    assert envs["GOOGLE_GENAI_USE_VERTEXAI"] == "TRUE"
    assert envs["BUSSOLA_MODEL"]
    assert "GOOGLE_API_KEY" not in envs


def test_deploy_do_agente_sem_o_mcp_aborta_antes_do_deploy(binarios):
    r = _rodar("deploy.sh", "agent", "--imagem", "c000", binarios=binarios)
    assert r.returncode != 0
    assert "bussola-mcp não existe" in r.stderr
    assert _chamadas(binarios, "gcloud run deploy") == []


def test_deploy_plano_b_injeta_a_chave_so_pelo_secret_manager(binarios):
    valor = "valor-da-chave-que-nao-pode-vazar"
    r = _rodar(
        "deploy.sh",
        "agent",
        "--llm",
        "gemini-api",
        "--imagem",
        "c000",
        binarios=binarios,
        servicos="bussola-mcp bussola-agent",
        GOOGLE_API_KEY=valor,
    )
    assert r.returncode == 0, r.stderr
    comando = _deploy(binarios)
    assert "--set-secrets GOOGLE_API_KEY=gemini-api-key:latest" in comando
    assert "--clear-secrets" not in comando
    assert _envs(comando)["GOOGLE_GENAI_USE_VERTEXAI"] == "FALSE"
    assert valor not in comando + r.stdout + r.stderr


@pytest.mark.parametrize(
    ("args", "codigo"),
    [
        ((), 2),
        (("nao-existe",), 1),
        (("mcp", "--com-trafego"), 1),
        (("mcp", "--tag", "producao"), 1),
        (("mcp", "--llm", "gemini-api"), 1),
        (("agent", "--llm", "outro"), 1),
    ],
)
def test_deploy_argumentos_invalidos_nao_chamam_o_gcloud(args, codigo, binarios):
    assert _rodar("deploy.sh", *args, binarios=binarios).returncode == codigo
    assert _chamadas(binarios, "gcloud") == []


@pytest.mark.parametrize("script", ["build_push.sh", "deploy.sh"])
def test_scripts_nunca_movem_trafego_nem_alteram_iam(script):
    texto = (DEPLOY / script).read_text(encoding="utf-8")
    proibido = (
        r"update-traffic|--to-latest|--to-revisions|iam-policy|(?<!no-)--allow-unauthenticated"
    )
    assert re.search(proibido, texto) is None


# ---------------------------------------------------------------------------
# iam_datasets.sh
# ---------------------------------------------------------------------------


def _concessoes() -> list[tuple[str, str]]:
    texto = (DEPLOY / "iam_datasets.sh").read_text(encoding="utf-8")
    bloco = re.search(r'CONCESSOES="([^"]+)"', texto).group(1)
    return [tuple(linha.split(":", 1)) for linha in bloco.split()]


def test_iam_simulacao_lista_as_concessoes_e_nao_executa(binarios):
    r = _rodar("iam_datasets.sh", binarios=binarios)
    assert r.returncode == 0, r.stderr
    concessoes = _concessoes()
    assert ("bussola_dados", "roles/bigquery.dataViewer") in concessoes
    for dataset, papel in concessoes:
        padrao = (
            rf"GRANT `{papel}` ON SCHEMA `batalha-time-07-lkbv\.{dataset}` "
            rf'TO "serviceAccount:{SA_DEFAULT}"'
        )
        assert re.search(padrao, r.stdout), dataset
    assert _chamadas(binarios) == []


def test_iam_so_concede_em_nivel_de_dataset(binarios):
    r = _rodar("iam_datasets.sh", binarios=binarios)
    assert "ON SCHEMA" in r.stdout
    assert re.search(r"projects add-iam-policy-binding|ON PROJECT", r.stdout) is None


def test_iam_sem_terminal_recusa_e_nao_aplica(binarios):
    r = _rodar("iam_datasets.sh", "--aplicar", binarios=binarios)
    assert r.returncode != 0
    assert "terminal" in r.stderr
    assert _chamadas(binarios, "bq ") == []


def test_iam_nao_tem_como_dispensar_a_confirmacao_humana():
    texto = (DEPLOY / "iam_datasets.sh").read_text(encoding="utf-8")
    assert "/dev/tty" in texto
    assert re.search(r"--yes|--force|--no-confirm|\s-y\b|CONFIRMO=|AUTO_?APPROVE", texto) is None
