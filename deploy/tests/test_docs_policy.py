"""Documentação de operação: segredos, confirmação humana e links.

Confere o que o ciclo 007 promete nos docs (FR-008 a FR-012). Nenhum ``echo``
de chave ou token, token só em variável com ``unset``, e nenhum comando que
mova tráfego ou mude IAM sem "confirmação humana" por perto. Confere também
que os links com âncora entre os docs apontam para títulos que existem. Sem
rede e sem GCP.
"""

import re
from pathlib import Path

import pytest
from helm_render import ROOT, WORKFLOWS

OPERATION_DOCS = [
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "docs" / "operacao.md",
    ROOT / "docs" / "roteiro-demo.md",
    ROOT / "deploy" / "README.md",
    ROOT / "deploy" / "helm" / "README.md",
    *sorted((ROOT / "specs" / "007-canal-deploy-demo").glob("*.md")),
]
DEPLOY_FILES = [
    path
    for path in sorted((ROOT / "deploy").rglob("*"))
    if path.is_file()
    and path.suffix in {".sh", ".py", ".jq", ".yaml", ".tpl", ".md"}
    and "__pycache__" not in path.parts
    and path.name != Path(__file__).name
]
WORKFLOW_FILES = sorted(WORKFLOWS.glob("*.yml"))
ALL_FILES = list(dict.fromkeys(OPERATION_DOCS + DEPLOY_FILES + WORKFLOW_FILES))

# Montados em partes para este arquivo não casar consigo mesmo.
SECRET_PATTERNS = [
    re.compile("AI" + r"za[0-9A-Za-z_\-]{20,}"),
    re.compile("ya" + r"29\.[0-9A-Za-z_\-]{10,}"),
    re.compile("BEGIN " + r"[A-Z ]*PRIVATE KEY"),
]
# echo/printf de uma variável de segredo: $TOKEN, ${GOOGLE_API_KEY}, $H etc.
# ($KEY sozinho é a chave do serviço, como mcp ou agent, e não segredo.)
ECHO_SECRET = re.compile(
    r"\b(echo|printf)\b[^\n|;]*"
    r"\$\{?([A-Z_]*(TOKEN|SECRET|PASSWORD|HASH)[A-Z_]*|[A-Z_]+_KEY|H)\b"
)
FENCE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
LINK = re.compile(r"\]\(([^)\s]+)\)")


def _rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _slug(heading: str) -> str:
    """Âncora de título no estilo do GitHub (mantém acentos)."""
    text = heading.strip().lower().replace("`", "")
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    body = FENCE.sub("", path.read_text(encoding="utf-8"))
    return {_slug(m.group(1)) for m in re.finditer(r"^#{1,6} (.+)$", body, re.MULTILINE)}


def _code_blocks(text: str) -> list[tuple[str, str]]:
    """(texto antes do bloco desde o bloco anterior, conteúdo do bloco)."""
    blocks, last = [], 0
    for match in FENCE.finditer(text):
        blocks.append((text[last : match.start()], match.group(1)))
        last = match.end()
    return blocks


def _commands(block: str) -> list[str]:
    """Comandos do bloco, com as continuações (\\) juntadas e sem comentários."""
    joined = re.sub(r"\\\n\s*", " ", block)
    return [line for line in joined.splitlines() if not line.lstrip().startswith("#")]


def test_operation_docs_exist():
    for path in OPERATION_DOCS[:6]:
        assert path.is_file(), _rel(path)
    names = {path.name for path in OPERATION_DOCS}
    assert {"ensaio-antigravity.md", "proposta-constituicao.md", "traceability.md"} <= names


@pytest.mark.parametrize("path", ALL_FILES, ids=_rel)
def test_no_secret_literals(path):
    text = path.read_text(encoding="utf-8")
    for pattern in SECRET_PATTERNS:
        assert not pattern.search(text), f"{_rel(path)}: {pattern.pattern}"


@pytest.mark.parametrize("path", ALL_FILES, ids=_rel)
def test_no_echo_of_secret_variables(path):
    text = path.read_text(encoding="utf-8")
    found = [m.group(0) for m in ECHO_SECRET.finditer(text)]
    assert not found, f"{_rel(path)}: {found}"


@pytest.mark.parametrize("path", OPERATION_DOCS, ids=_rel)
def test_identity_tokens_only_in_variables_and_unset(path):
    text = path.read_text(encoding="utf-8")
    for _, block in _code_blocks(text):
        commands = _commands(block)
        for line in commands:
            if re.search(r"gcloud auth print-(identity|access)-token", line):
                assert re.search(r"[A-Z_]+=\$\(gcloud auth print-", line), line
        assigned = {
            m.group(1)
            for line in commands
            for m in re.finditer(r"\b([A-Z_]+)=\$\(gcloud auth print-", line)
        }
        for name in assigned:
            assert f"unset {name}" in block, f"{_rel(path)}: falta unset {name}"


@pytest.mark.parametrize("path", OPERATION_DOCS, ids=_rel)
def test_no_manual_traffic_or_iam_policy_commands(path):
    text = path.read_text(encoding="utf-8")
    for _, block in _code_blocks(text):
        for line in _commands(block):
            assert "update-traffic" not in line, line
            assert "set-iam-policy" not in line, line
            assert not re.search(r"gcloud run deploy\b", line), line
            assert "allUsers" not in line, line


@pytest.mark.parametrize("path", OPERATION_DOCS, ids=_rel)
def test_state_changes_have_human_confirmation_nearby(path):
    text = path.read_text(encoding="utf-8")
    heading = ""
    for before, block in _code_blocks(text):
        headings = re.findall(r"^#{1,6} (.+)$", before, re.MULTILINE)
        heading = headings[-1] if headings else heading
        context = f"{heading}\n{before[-600:]}\n{block}".lower()
        for line in _commands(block):
            applies = "services replace" in line and "--dry-run" not in line
            changes_iam = "add-iam-policy-binding" in line or "--aplicar" in line
            if applies or changes_iam:
                assert "confirmação humana" in context, f"{_rel(path)}: {line.strip()}"


def test_runbook_has_the_sections_agents_md_links_to():
    runbook = ROOT / "docs" / "operacao.md"
    anchors = _anchors(runbook)
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    linked = set(re.findall(r"docs/operacao\.md#([^)\s]+)", agents))
    assert linked, "o AGENTS.md deve apontar para as seções do runbook"
    assert linked <= anchors, sorted(linked - anchors)
    for section in ("status", "smoke", "logs", "troubleshooting", "rollback", "plano-b"):
        assert any(section in anchor for anchor in anchors), section


@pytest.mark.parametrize("path", OPERATION_DOCS, ids=_rel)
def test_relative_links_and_anchors_resolve(path):
    text = FENCE.sub("", path.read_text(encoding="utf-8"))
    for target in LINK.findall(text):
        if re.match(r"[a-z]+:", target):
            continue
        file_part, _, anchor = target.partition("#")
        dest = (path.parent / file_part).resolve() if file_part else path
        assert dest.exists(), f"{_rel(path)}: {target}"
        if anchor and dest.suffix == ".md":
            assert anchor in _anchors(dest), f"{_rel(path)}: {target}"


def test_runbook_uses_the_chart_for_promotion_and_plan_b():
    runbook = (ROOT / "docs" / "operacao.md").read_text(encoding="utf-8")
    for needle in (
        "deploy/helm/promote.jq",
        "templates/promotion.yaml",
        "deploy/helm/traffic.jq",
        "values-plan-b.yaml",
        "values-plan-a.yaml",
        "promote.yml",
        "target=previous",
        "MCP_USE_OIDC=FALSE",
        "make smoke",
    ):
        assert needle in runbook, needle
