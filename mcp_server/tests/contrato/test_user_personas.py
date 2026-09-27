"""``bussola_dados.users``: DDL, fixture e regras de ``web/bff/domain/userAccount.ts``.

A fixture ``contracts/fixtures/bussola_dados/users.json`` é a fonte da carga feita por
``data/scripts/build_dados.py`` e tem as mesmas linhas de ``web/fixtures/users.json``.
As regras de linha (padrão de login, UUID v4, tamanhos máximos) são lidas do próprio
``userAccount.ts``, para o teste quebrar se o BFF mudar sem o contrato acompanhar.
Nenhuma linha tem senha ou hash: o hash fica só no Secret Manager.
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from bussola_mcp.contratos import (
    ID_ANCORA,
    ID_CONTROLE,
    SUPPORT_TABLE_MODELS,
    UUID_V4_RE,
    UserPersona,
)

RAIZ_REPO = Path(__file__).resolve().parents[3]
FIXTURE_CONTRATO = RAIZ_REPO / "contracts" / "fixtures" / "bussola_dados" / "users.json"
FIXTURE_WEB = RAIZ_REPO / "web" / "fixtures" / "users.json"
USER_ACCOUNT_TS = RAIZ_REPO / "web" / "bff" / "domain" / "userAccount.ts"
DDL = RAIZ_REPO / "contracts" / "bigquery" / "bussola_dados.sql"

COLUNAS = ["login", "id_usuario", "display_name", "summary", "featured"]
PALAVRAS_PROIBIDAS = ("senha", "password", "hash", "secret", "token")


def _ler(caminho: Path) -> Any:
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def linhas() -> list[dict[str, Any]]:
    return _ler(FIXTURE_CONTRATO)


@pytest.fixture(scope="module")
def regras_ts() -> dict[str, Any]:
    """Padrões e limites de ``userAccount.ts`` (regex JS simples, compatível com ``re``)."""
    fonte = USER_ACCOUNT_TS.read_text(encoding="utf-8")
    login = re.search(r"LOGIN_PATTERN\s*=\s*/(.+?)/;", fonte)
    uuid = re.search(r"UUID_V4\s*=\s*/(.+?)/;", fonte)
    assert login and uuid, "padrões de userAccount.ts não encontrados"
    limites = {campo: int(n) for campo, n in re.findall(r'text\(row, "(\w+)", (\d+)\)', fonte)}
    assert set(limites) == {"id_usuario", "display_name", "summary"}
    return {"login": re.compile(login[1]), "uuid": re.compile(uuid[1]), "limites": limites}


def test_modelo_e_ddl_sem_senha_nem_hash() -> None:
    assert SUPPORT_TABLE_MODELS["bussola_dados.users"] is UserPersona
    assert list(UserPersona.model_fields) == COLUNAS
    tabela = re.search(
        r"CREATE TABLE IF NOT EXISTS bussola_dados\.users \((.*?)\);", DDL.read_text(), re.DOTALL
    )
    assert tabela, "DDL de bussola_dados.users ausente"
    corpo = tabela[1].lower()
    assert not [p for p in PALAVRAS_PROIBIDAS if p in corpo]


def test_fixture_igual_a_do_front(linhas: list[dict[str, Any]]) -> None:
    assert linhas == _ler(FIXTURE_WEB)


def test_linhas_validam_no_modelo_e_sem_campos_sensiveis(linhas: list[dict[str, Any]]) -> None:
    assert linhas, "fixture vazia"
    for linha in linhas:
        assert list(linha) == COLUNAS
        UserPersona.model_validate(linha)
        texto = json.dumps(linha, ensure_ascii=False).lower()
        assert not [p for p in PALAVRAS_PROIBIDAS if p in texto]


def test_regras_do_user_account(linhas: list[dict[str, Any]], regras_ts: dict[str, Any]) -> None:
    limites = regras_ts["limites"]
    for linha in linhas:
        assert regras_ts["login"].fullmatch(linha["login"])
        assert linha["login"] == linha["login"].strip().lower()
        id_usuario = linha["id_usuario"]
        assert len(id_usuario) <= limites["id_usuario"]
        assert id_usuario == id_usuario.lower()
        assert regras_ts["uuid"].fullmatch(id_usuario)
        assert UUID_V4_RE.fullmatch(id_usuario)
        assert 0 < len(linha["display_name"].strip()) <= limites["display_name"]
        assert linha["display_name"] == linha["display_name"].strip()
        assert len(linha["summary"]) <= limites["summary"]
        assert isinstance(linha["featured"], bool)


def test_logins_e_ids_unicos_com_ancora_e_controle(linhas: list[dict[str, Any]]) -> None:
    logins = [linha["login"] for linha in linhas]
    ids = [linha["id_usuario"] for linha in linhas]
    assert len(set(logins)) == len(logins)
    assert len(set(ids)) == len(ids)
    assert {ID_ANCORA, ID_CONTROLE} <= set(ids)
    assert any(linha["featured"] for linha in linhas)
