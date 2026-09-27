"""Varredura de saídas (critério §6): nenhuma resposta nem log traz SQL, projeto ou credencial.

Chama todas as ferramentas com entradas de sucesso, de erro, com texto parecido
com SQL e com backends que falham com mensagens "sujas" (SQL, projeto, token),
e procura ``SELECT``, ``batalha-time-07``, ``googleapis`` e ``Bearer`` em tudo o
que sai: resultados MCP, catálogo de ferramentas e linhas de log.
"""

import json
import re

import pytest
from apoio_ferramentas import (
    BUSCA,
    DIR_OFICIAL,
    TODAS,
    UUID_DESCONHECIDO,
    BuscadorEspiao,
    RepositorioEspiao,
    argumentos,
    capturar_logs,
    chamar,
    sessao,
)

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE
from bussola_mcp.ferramentas.computations import DomainComputations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository
from bussola_mcp.ferramentas.ports import ToolDependencies

PROIBIDOS = [
    re.compile(r"\bselect\b", re.IGNORECASE),
    re.compile(r"batalha-time-07", re.IGNORECASE),
    re.compile(r"googleapis", re.IGNORECASE),
    re.compile(r"\bbearer\b", re.IGNORECASE),
]
SUJO = (
    "SELECT * FROM `batalha-time-07-lkbv.bussola_dados.perfil_mensal` "
    "https://bigquery.googleapis.com/ Authorization: Bearer ya29.segredo"
)
SQL_DO_USUARIO = "'; SELECT * FROM batalha-time-07-lkbv.bussola_dados.x; --"


def _assert_limpo(texto: str, contexto: object) -> None:
    for padrao in PROIBIDOS:
        assert not padrao.search(texto), (padrao.pattern, contexto)


def _variacoes(ferramenta: str) -> list[dict]:
    """Entradas de sucesso, de erro e com texto parecido com SQL."""
    casos = [
        argumentos(ferramenta, ID_ANCORA, 202506),
        argumentos(ferramenta, ID_ANCORA, 202512),
        argumentos(ferramenta, ID_ANCORA, 202509),
        argumentos(ferramenta, ID_ANCORA, 202503),
        argumentos(ferramenta, ID_CONTROLE, 202512),
        argumentos(ferramenta, UUID_DESCONHECIDO, 202512),
        argumentos(ferramenta, SQL_DO_USUARIO, 202512),
        argumentos(ferramenta, ID_ANCORA, 209912),
    ]
    if ferramenta == BUSCA:
        casos += [
            argumentos(ferramenta, pergunta=SQL_DO_USUARIO),
            argumentos(ferramenta, pergunta="Bearer token googleapis select"),
            argumentos(ferramenta, pergunta="x" * 501),
        ]
    if ferramenta == "referencia_coorte":
        casos.append(argumentos(ferramenta, categoria=SQL_DO_USUARIO[:100]))
    if ferramenta in ("simular_objetivo", "comparar_cenarios"):
        casos.append(argumentos(ferramenta, prazo_meses=999, aporte_mensal=None))
    if ferramenta == "resumo_mes":
        casos.append(argumentos(ferramenta, anomes=202512, ate_anomes=202506))
    return casos


@pytest.mark.parametrize("fixtures_nome", ["oficial", "sintetica"])
async def test_nenhuma_saida_nem_log_com_marcadores_proibidos(fixtures_sinteticas, fixtures_nome):
    fixtures = DIR_OFICIAL if fixtures_nome == "oficial" else fixtures_sinteticas
    with capturar_logs() as logs:
        async with sessao(fixtures) as cliente:
            catalogo = await cliente.list_tools()
            _assert_limpo(catalogo.model_dump_json(), "list_tools")
            for ferramenta in TODAS:
                for args in _variacoes(ferramenta):
                    envelope = await chamar(cliente, ferramenta, args)
                    _assert_limpo(json.dumps(envelope, ensure_ascii=False), (ferramenta, args))
    _assert_limpo(logs.getvalue(), "logs")


async def test_backends_com_falha_suja_nao_vazam(fixtures_sinteticas):
    repositorio = RepositorioEspiao(FixtureRepository(fixtures_sinteticas), erro=RuntimeError(SUJO))
    deps = ToolDependencies(
        repository=repositorio,
        searcher=BuscadorEspiao(erro=ConnectionError(SUJO)),
        computations=DomainComputations(repositorio),
    )
    with capturar_logs() as logs:
        async with sessao(deps=deps) as cliente:
            for ferramenta in TODAS:
                envelope = await chamar(cliente, ferramenta, argumentos(ferramenta))
                assert envelope["erro"]["codigo"] == "INDISPONIVEL"
                _assert_limpo(json.dumps(envelope, ensure_ascii=False), ferramenta)
    texto_logs = logs.getvalue()
    _assert_limpo(texto_logs, "logs")
    assert "ya29" not in texto_logs


async def test_texto_do_usuario_nunca_volta_na_resposta(fixtures_sinteticas):
    async with sessao(fixtures_sinteticas) as cliente:
        busca = await chamar(cliente, BUSCA, argumentos(BUSCA, pergunta=SQL_DO_USUARIO))
        coorte = await chamar(
            cliente,
            "referencia_coorte",
            argumentos("referencia_coorte", categoria=SQL_DO_USUARIO[:100]),
        )
        invalido = await chamar(
            cliente, "perfil_financeiro", argumentos("perfil_financeiro", SQL_DO_USUARIO)
        )
    for envelope in (busca, coorte, invalido):
        assert "batalha" not in json.dumps(envelope, ensure_ascii=False)
        assert "--" not in json.dumps(envelope, ensure_ascii=False)
