"""Políticas do repositório (constituição II, V, VII e X; contratos §1 e §7).

Artefatos do ciclo 000 presentes, constituição sem placeholder do template,
mapa de contratos sem ``web/``, ``env.example`` igual a contratos §7, nenhum
segredo versionado e nenhum SQL montado com valor dinâmico.

Adaptado da branch ``alt/000-fundacao-contratos-claude`` (João Paulo).
"""

import ast
import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
CONTRATOS = RAIZ / "docs" / "ciclos" / "contratos.md"

ARTEFATOS_000 = [
    "CLAUDE.md",
    "Makefile",
    ".specify/memory/constitution.md",
    "contracts/bigquery/bussola_dados.sql",
    "contracts/bigquery/bussola_app.sql",
    "contracts/env.example",
    "contracts/fixtures",
    "data/scripts/aplicar_ddl.py",
    "data/scripts/gerar_fixtures.py",
    "mcp_server/pyproject.toml",
    "mcp_server/Dockerfile",
    "mcp_server/bussola_mcp/contratos.py",
    "mcp_server/bussola_mcp/logging_json.py",
    "mcp_server/bussola_mcp/server.py",
    "mcp_server/bussola_mcp/dominio/interfaces.py",
    "mcp_server/bussola_mcp/dominio/fakes.py",
    "mcp_server/tests/contrato",
    "agent/pyproject.toml",
    "agent/Dockerfile",
    "agent/bussola_agent/agent.py",
    "agent/bussola_agent/estado.py",
    "agent/bussola_agent/callbacks.py",
    "agent/bussola_agent/extensoes.py",
    "agent/bussola_agent/persistencia.py",
    "agent/bussola_agent/mcp_conexao.py",
    "agent/bussola_agent/logging_json.py",
    "agent/tests/contrato",
    "deploy/build_push.sh",
    "deploy/deploy.sh",
    "deploy/iam_datasets.sh",
    "deploy/smoke_modelos.py",
]

PADROES_SEGREDO = {
    "chave de API do Google": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "chave privada": re.compile(r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "token OAuth do Google": re.compile(r"ya29\.[0-9A-Za-z_-]{20,}"),
}

_INICIO_SQL = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|MERGE|WITH)\b", re.IGNORECASE)


def _e_texto_sql(no: ast.AST) -> bool:
    return (
        isinstance(no, ast.Constant)
        and isinstance(no.value, str)
        and _INICIO_SQL.match(no.value) is not None
    )


def sql_dinamico(fonte: str) -> list[int]:
    """Linhas com SQL montado a partir de valores (f-string, ``+``, ``%`` ou ``.format``).

    Única exceção: f-string cujos campos são todos constantes de módulo em
    maiúsculas (ex.: ``{TABELA_ORIGEM}``), usadas para nome de tabela fixo. Valores
    entram só como parâmetros (``@id_usuario``).
    """
    achados: list[int] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.JoinedStr):
            if not no.values or not _e_texto_sql(no.values[0]):
                continue
            campos = [v.value for v in no.values if isinstance(v, ast.FormattedValue)]
            if any(not (isinstance(c, ast.Name) and c.id.isupper()) for c in campos):
                achados.append(no.lineno)
        elif isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add | ast.Mod):
            if _e_texto_sql(no.left) or (isinstance(no.op, ast.Add) and _e_texto_sql(no.right)):
                achados.append(no.lineno)
        elif (
            isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and no.func.attr == "format"
            and _e_texto_sql(no.func.value)
        ):
            achados.append(no.lineno)
    return achados


def _arquivos_do_repo() -> list[Path]:
    try:
        saida = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("fora de um repositório git (ex.: dentro da imagem)")
    return [RAIZ / linha for linha in saida.splitlines() if (RAIZ / linha).is_file()]


def _texto(caminho: Path) -> str:
    if caminho.stat().st_size > 1_000_000 or caminho.name == "uv.lock":
        return ""
    return caminho.read_text(encoding="utf-8", errors="ignore")


def _secao(texto: str, inicio: str, fim: str) -> str:
    return texto.split(f"## {inicio}", 1)[1].split(f"## {fim}", 1)[0]


@pytest.mark.parametrize("relativo", ARTEFATOS_000)
def test_artefatos_do_000_existem(relativo):
    assert (RAIZ / relativo).exists(), relativo


def test_constituicao_tem_os_10_principios_e_nenhum_placeholder():
    texto = (RAIZ / ".specify" / "memory" / "constitution.md").read_text(encoding="utf-8")
    principios = re.findall(r"^### ([IVX]+)\. .+$", texto, re.MULTILINE)
    assert principios == ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    assert not re.findall(r"\[[A-Z][A-Z_]{2,}\]", texto)  # [PLACEHOLDER] do template


def test_mapa_de_contratos_1_nao_cita_web():
    mapa = _secao(CONTRATOS.read_text(encoding="utf-8"), "§1", "§2")
    assert "web/" not in mapa  # canal = ADK Web, sem front próprio


def test_env_example_tem_exatamente_as_variaveis_de_contratos_7():
    secao = _secao(CONTRATOS.read_text(encoding="utf-8"), "§7", "§8")
    esperadas: set[str] = set()
    for linha in secao.splitlines():
        if linha.startswith("| `"):
            esperadas |= set(re.findall(r"`([A-Z][A-Z_]+)`", linha.split("|")[1]))
    definidas: dict[str, str] = {}
    for linha in (RAIZ / "contracts" / "env.example").read_text(encoding="utf-8").splitlines():
        if re.match(r"^[A-Z][A-Z_]+=", linha):
            nome, _, valor = linha.partition("=")
            definidas[nome] = valor
    assert esperadas
    assert set(definidas) == esperadas
    assert definidas["GOOGLE_API_KEY"] == ""  # só no Plano B, vindo do Secret Manager


def test_sem_segredos_nos_arquivos_do_repo():
    achados = [
        f"{caminho.relative_to(RAIZ)}: {nome}"
        for caminho in _arquivos_do_repo()
        for nome, padrao in PADROES_SEGREDO.items()
        if padrao.search(_texto(caminho))
    ]
    assert achados == []


def test_sem_sql_montado_com_valor_dinamico():
    achados = [
        f"{caminho.relative_to(RAIZ)}:{linha}"
        for caminho in _arquivos_do_repo()
        if caminho.suffix == ".py"
        for linha in sql_dinamico(_texto(caminho))
    ]
    assert achados == []


@pytest.mark.parametrize(
    "ruim",
    [
        "q = f\"SELECT * FROM t WHERE id = '{x}'\"",
        "q = f'''\nSELECT {tabela} WHERE 1'''",
        "q = f'SELECT * FROM {obj.tabela}'",
        'q = "SELECT * FROM t WHERE id = " + x',
        'q = x + "SELECT 1"',
        "q = \"SELECT * FROM t WHERE id = '%s'\" % x",
        'q = "SELECT {}".format(x)',
        'q = f"with a as (select {x})"',
    ],
)
def test_detector_de_sql_dinamico_pega_os_casos_ruins(ruim):
    assert sql_dinamico(ruim)


@pytest.mark.parametrize(
    "bom",
    [
        'SQL = """\nSELECT a FROM t WHERE id IN UNNEST(@ids)\n"""',
        'SQL = f"""\nSELECT a FROM `{TABELA_ORIGEM}` WHERE id = @id_usuario\n"""',
        'msg = f"Selecionados {n} itens"',
    ],
)
def test_detector_de_sql_dinamico_aceita_consulta_parametrizada(bom):
    assert sql_dinamico(bom) == []
