"""DDL de ``bussola_app`` ↔ modelos de ``persistencia.py`` (AC-03, TS-01).

Compara, tabela a tabela, nomes, tipos e nulidade das colunas do arquivo
``contracts/bigquery/bussola_app.sql`` com os campos dos modelos Pydantic.
"""

import re
import types
import typing
from datetime import datetime
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel

from bussola_agent.persistencia import TABELAS

DDL = Path(__file__).resolve().parents[3] / "contracts" / "bigquery" / "bussola_app.sql"

_RE_TABELA = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?bussola_app\.(\w+)`?\s*\((.*?)\)\s*"
    r"(?:PARTITION|CLUSTER|OPTIONS|;)",
    re.IGNORECASE | re.DOTALL,
)
_RE_COLUNA = re.compile(r"^\s*`?(\w+)`?\s+(\w+)(\s+NOT\s+NULL)?", re.IGNORECASE)


def _sem_comentarios(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def ler_ddl() -> dict[str, dict[str, tuple[str, bool]]]:
    """``{tabela: {coluna: (tipo, anulavel)}}`` a partir do DDL."""
    sql = _sem_comentarios(DDL.read_text(encoding="utf-8"))
    tabelas: dict[str, dict[str, tuple[str, bool]]] = {}
    for nome, corpo in _RE_TABELA.findall(sql):
        colunas: dict[str, tuple[str, bool]] = {}
        for definicao in corpo.split(","):
            if not definicao.strip():
                continue
            casamento = _RE_COLUNA.match(definicao)
            assert casamento, f"Coluna não reconhecida em {nome}: {definicao.strip()!r}"
            coluna, tipo, not_null = casamento.groups()
            colunas[coluna] = (tipo.upper(), not_null is None)
        tabelas[nome] = colunas
    return tabelas


def _tipo_bq(anotacao: object) -> tuple[str, bool]:
    """Tipo BigQuery equivalente à anotação Pydantic e se o campo aceita ``None``."""
    anulavel = False
    origem = typing.get_origin(anotacao)
    if origem in (typing.Union, types.UnionType):
        argumentos = [a for a in typing.get_args(anotacao) if a is not type(None)]
        anulavel = len(argumentos) < len(typing.get_args(anotacao))
        assert len(argumentos) == 1, f"União não suportada: {anotacao}"
        anotacao = argumentos[0]
        origem = typing.get_origin(anotacao)
    if origem is typing.Literal:
        valores = typing.get_args(anotacao)
        assert all(isinstance(v, str) for v in valores)
        return "STRING", anulavel
    if origem is dict or anotacao is dict:
        return "JSON", anulavel
    if isinstance(anotacao, type):
        if issubclass(anotacao, bool):
            return "BOOL", anulavel
        if issubclass(anotacao, Enum) and issubclass(anotacao, str):
            return "STRING", anulavel
        if issubclass(anotacao, str):
            return "STRING", anulavel
        if issubclass(anotacao, int):
            return "INT64", anulavel
        if issubclass(anotacao, float):
            return "FLOAT64", anulavel
        if issubclass(anotacao, datetime):
            return "TIMESTAMP", anulavel
    raise AssertionError(f"Tipo sem equivalente no BigQuery: {anotacao}")


def colunas_do_modelo(modelo: type[BaseModel]) -> dict[str, tuple[str, bool]]:
    return {nome: _tipo_bq(campo.annotation) for nome, campo in modelo.model_fields.items()}


def test_ddl_existe_e_tem_as_quatro_tabelas() -> None:
    assert DDL.is_file(), f"DDL não encontrado: {DDL}"
    assert set(ler_ddl()) == {"planos", "consentimentos", "auditoria", "acompanhamento"}


def test_cada_tabela_tem_modelo() -> None:
    assert set(TABELAS) == set(ler_ddl())


@pytest.mark.parametrize("tabela", sorted(TABELAS))
def test_colunas_nomes_tipos_e_nulidade(tabela: str) -> None:
    esperado = ler_ddl()[tabela]
    obtido = colunas_do_modelo(TABELAS[tabela])
    assert list(obtido) == list(esperado), "nomes ou ordem das colunas divergem"
    for coluna, (tipo, anulavel) in esperado.items():
        assert obtido[coluna] == (tipo, anulavel), f"{tabela}.{coluna}"


@pytest.mark.parametrize("tabela", sorted(TABELAS))
def test_campos_obrigatorios_sem_padrao_none(tabela: str) -> None:
    """Coluna ``NOT NULL`` nunca tem ``None`` como padrão no modelo."""
    esperado = ler_ddl()[tabela]
    for nome, campo in TABELAS[tabela].model_fields.items():
        if not esperado[nome][1]:
            assert campo.default is not None or campo.is_required() or campo.default_factory
