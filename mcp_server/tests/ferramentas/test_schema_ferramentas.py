"""Catálogo MCP do servidor real: 10 ferramentas com nomes e schemas de contratos §5.

Usa o cliente do SDK (``ClientSession``) em memória (decisão D-08 da spec).
"""

import pytest
from apoio_ferramentas import (
    OBRIGATORIO,
    PARAMETROS_ESPERADOS,
    RESTRICOES_DE_FAIXA,
    sessao,
    tipos_json,
)

from bussola_mcp.contratos import FERRAMENTAS
from bussola_mcp.server import SERVICO


@pytest.fixture
async def ferramentas_listadas(fixtures_sinteticas):
    # Sem yield dentro da sessão: o task group do SDK precisa fechar na mesma task.
    async with sessao(fixtures_sinteticas) as cliente:
        listadas = (await cliente.list_tools()).tools
    return {f.name: f for f in listadas}


async def test_lista_exatamente_as_10_ferramentas_do_contrato(ferramentas_listadas):
    assert set(ferramentas_listadas) == set(FERRAMENTAS)
    assert len(ferramentas_listadas) == 10


@pytest.mark.parametrize("nome", sorted(FERRAMENTAS))
async def test_parametros_tipos_e_padroes_de_cada_ferramenta(ferramentas_listadas, nome):
    schema = ferramentas_listadas[nome].inputSchema
    propriedades = schema["properties"]
    esperados = {
        "id_usuario": ({"string"}, OBRIGATORIO),
        "ate_anomes": ({"integer"}, OBRIGATORIO),
        **PARAMETROS_ESPERADOS[nome],
    }
    assert set(propriedades) == set(esperados)
    obrigatorios = {p for p, (_, padrao) in esperados.items() if padrao is OBRIGATORIO}
    assert set(schema.get("required", [])) == obrigatorios
    for parametro, (tipos, padrao) in esperados.items():
        assert tipos_json(propriedades[parametro]) == tipos, parametro
        if padrao is not OBRIGATORIO:
            assert propriedades[parametro]["default"] == padrao, parametro


@pytest.mark.parametrize("nome", sorted(FERRAMENTAS))
async def test_schema_sem_restricoes_de_faixa(ferramentas_listadas, nome):
    """Faixas ficam na validação da ferramenta, não no schema (research R-05 do 000)."""
    for propriedade in ferramentas_listadas[nome].inputSchema["properties"].values():
        chaves = set(propriedade)
        for opcao in propriedade.get("anyOf", []):
            chaves |= set(opcao)
        assert not chaves & RESTRICOES_DE_FAIXA


@pytest.mark.parametrize("nome", sorted(FERRAMENTAS))
async def test_ferramentas_read_only_com_descricao_em_pt_br(ferramentas_listadas, nome):
    ferramenta = ferramentas_listadas[nome]
    assert ferramenta.annotations is not None
    assert ferramenta.annotations.readOnlyHint is True
    assert ferramenta.annotations.idempotentHint is True
    assert ferramenta.description and len(ferramenta.description) > 20


async def test_nome_do_servidor_e_instrucoes(fixtures_sinteticas):
    async with sessao(fixtures_sinteticas) as cliente:
        # A sessão em memória já passou pelo initialize; o nome vem no serverInfo.
        resultado = await cliente.initialize()
    assert resultado.serverInfo.name == SERVICO
    assert resultado.instructions and "buscar_contexto_financeiro" in resultado.instructions
