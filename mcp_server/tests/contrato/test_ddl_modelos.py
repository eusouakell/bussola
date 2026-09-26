"""DDL de ``bussola_dados`` e ``bussola_rag`` ↔ modelos de ``contratos.py`` (AC-03, TS-01).

Compara nome, tipo e nulidade de cada coluna. ``ARRAY`` é exceção na nulidade:
o BigQuery não aceita ``NOT NULL`` em ``ARRAY`` (research R-16).
"""

import re
import types
from datetime import datetime
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import BaseModel

from bussola_mcp.contratos import MODELOS_TABELA

DIR_BIGQUERY = Path(__file__).resolve().parents[3] / "contracts" / "bigquery"
ARQUIVOS_DDL = ("bussola_dados.sql", "bussola_rag.sql")
DATASETS = tuple(arquivo.removesuffix(".sql") for arquivo in ARQUIVOS_DDL)

TIPOS_ESCALARES: dict[Any, str] = {
    str: "STRING",
    int: "INT64",
    float: "FLOAT64",
    bool: "BOOL",
    datetime: "TIMESTAMP",
}

_RE_TABELA = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([\w.]+)`?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)


def _sem_comentarios(sql: str) -> str:
    return "\n".join(linha.split("--", 1)[0] for linha in sql.splitlines())


def _dividir_colunas(corpo: str) -> list[str]:
    """Separa as definições por vírgula de nível zero (ignora ``<...>`` e ``(...)``)."""
    partes: list[str] = []
    atual: list[str] = []
    profundidade = 0
    for caractere in corpo:
        if caractere in "<(":
            profundidade += 1
        elif caractere in ">)":
            profundidade -= 1
        if caractere == "," and profundidade == 0:
            partes.append("".join(atual))
            atual = []
        else:
            atual.append(caractere)
    partes.append("".join(atual))
    return [" ".join(parte.split()) for parte in partes if parte.strip()]


def ler_ddl(caminho: Path) -> dict[str, dict[str, tuple[str, bool]]]:
    """``{"dataset.tabela": {coluna: (tipo, anulavel)}}`` a partir de um ``.sql``."""
    tabelas: dict[str, dict[str, tuple[str, bool]]] = {}
    for nome, corpo in _RE_TABELA.findall(_sem_comentarios(caminho.read_text(encoding="utf-8"))):
        colunas: dict[str, tuple[str, bool]] = {}
        for definicao in _dividir_colunas(corpo):
            coluna, resto = definicao.split(" ", 1)
            nao_nulo = re.search(r"\bNOT\s+NULL\b", resto, re.IGNORECASE) is not None
            tipo = re.sub(r"\bNOT\s+NULL\b", "", resto, flags=re.IGNORECASE)
            tipo = re.sub(r"\s+", "", tipo).upper()
            colunas[coluna] = (tipo, not nao_nulo)
        tabelas[nome] = colunas
    return tabelas


def tipo_bigquery(anotacao: Any) -> tuple[str, bool]:
    """Tipo BigQuery esperado e nulidade de uma anotação de campo Pydantic."""
    anulavel = False
    if get_origin(anotacao) in (Union, types.UnionType):
        argumentos = [a for a in get_args(anotacao) if a is not type(None)]
        anulavel = len(argumentos) < len(get_args(anotacao))
        assert len(argumentos) == 1, f"união não suportada: {anotacao}"
        anotacao = argumentos[0]
    origem = get_origin(anotacao)
    if origem is dict or anotacao is dict:
        return "JSON", anulavel
    if origem is list:
        (item,) = get_args(anotacao)
        return f"ARRAY<{TIPOS_ESCALARES[item]}>", anulavel
    return TIPOS_ESCALARES[anotacao], anulavel


def colunas_do_modelo(modelo: type[BaseModel]) -> dict[str, tuple[str, bool]]:
    return {nome: tipo_bigquery(campo.annotation) for nome, campo in modelo.model_fields.items()}


@pytest.fixture(scope="module")
def ddl() -> dict[str, dict[str, tuple[str, bool]]]:
    tabelas: dict[str, dict[str, tuple[str, bool]]] = {}
    for arquivo in ARQUIVOS_DDL:
        tabelas.update(ler_ddl(DIR_BIGQUERY / arquivo))
    return tabelas


def test_mesmas_tabelas(ddl):
    assert {nome.split(".")[0] for nome in ddl} == set(DATASETS)
    assert set(ddl) == set(MODELOS_TABELA)


@pytest.mark.parametrize("tabela", sorted(MODELOS_TABELA))
def test_colunas_tipos_e_nulidade(ddl, tabela):
    no_ddl = ddl[tabela]
    no_modelo = colunas_do_modelo(MODELOS_TABELA[tabela])
    assert list(no_ddl) == list(no_modelo), "nomes ou ordem das colunas divergem"
    for coluna, (tipo_ddl, anulavel_ddl) in no_ddl.items():
        tipo_modelo, anulavel_modelo = no_modelo[coluna]
        assert tipo_ddl == tipo_modelo, f"{tabela}.{coluna}: tipo"
        if tipo_ddl.startswith("ARRAY<"):
            continue  # BigQuery não aceita NOT NULL em ARRAY
        assert anulavel_ddl == anulavel_modelo, f"{tabela}.{coluna}: nulidade"


def test_colunas_anulaveis_do_rag(ddl):
    anulaveis = {c for c, (_, anulavel) in ddl["bussola_rag.documentos"].items() if anulavel}
    assert anulaveis == {"id_usuario", "anomes", "embedding"}


def test_parser_do_ddl(tmp_path):
    sql = tmp_path / "x.sql"
    sql.write_text(
        "-- comentário, com vírgula\n"
        "CREATE TABLE IF NOT EXISTS ds.t (\n"
        "  a STRING NOT NULL, -- fim de linha\n"
        "  b ARRAY<FLOAT64>,\n"
        "  c int64\n"
        ");\n",
        encoding="utf-8",
    )
    assert ler_ddl(sql) == {
        "ds.t": {"a": ("STRING", False), "b": ("ARRAY<FLOAT64>", True), "c": ("INT64", True)}
    }
