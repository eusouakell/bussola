"""MCP mock em memória (contratos §5 e §8, T021, AC-05, TS-02, TS-03).

Usa o cliente do SDK oficial (``ClientSession``) ligado ao servidor por streams em
memória, sem rede.
"""

import io
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from bussola_mcp.contratos import (
    FERRAMENTAS_MOCK,
    FERRAMENTAS_P0,
    ID_ANCORA,
    ID_CONTROLE,
    arquivo_golden,
    arquivo_resumo_mes,
)
from bussola_mcp.logging_json import configurar_logging
from bussola_mcp.server import AVISO_CORTE, AVISO_SIMULACAO, criar_servidor

UUID_DESCONHECIDO = str(uuid.UUID(int=0xB0550, version=4))
OBRIGATORIO = object()

# Parâmetros adicionais de §5: nome → (tipos JSON, padrão ou OBRIGATORIO).
PARAMETROS_ESPERADOS: dict[str, dict[str, tuple[set[str], Any]]] = {
    "perfil_financeiro": {},
    "capacidade_poupanca": {},
    "oportunidades_corte": {"top_n": ({"integer"}, 5)},
    "dividas_e_parcelas": {},
    "simular_objetivo": {
        "valor_alvo": ({"number"}, OBRIGATORIO),
        "prazo_meses": ({"integer", "null"}, None),
        "aporte_mensal": ({"number", "null"}, None),
        "usar_saldo_atual": ({"boolean"}, False),
    },
    "comparar_cenarios": {
        "valor_alvo": ({"number"}, OBRIGATORIO),
        "prazo_meses": ({"integer"}, OBRIGATORIO),
    },
    "buscar_contexto_financeiro": {
        "pergunta": ({"string"}, OBRIGATORIO),
        "k": ({"integer"}, 5),
    },
    "resumo_mes": {"anomes": ({"integer"}, OBRIGATORIO)},
}

# Argumentos mínimos válidos (além de id_usuario e ate_anomes) por ferramenta.
ARGUMENTOS_MINIMOS: dict[str, dict[str, Any]] = {
    "simular_objetivo": {"valor_alvo": 5000.0, "aporte_mensal": 250.0},
    "comparar_cenarios": {"valor_alvo": 5000.0, "prazo_meses": 12},
    "buscar_contexto_financeiro": {"pergunta": "Quanto gasto com aluguel?"},
    "resumo_mes": {"anomes": 202503},
}

RESTRICOES_DE_FAIXA = {
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
}


@asynccontextmanager
async def sessao_mock(dir_fixtures: Path):
    async with create_connected_server_and_client_session(criar_servidor(dir_fixtures)) as sessao:
        yield sessao


async def chamar(sessao, ferramenta: str, **argumentos: Any) -> dict[str, Any]:
    """Chama a ferramenta e confere o formato do resultado (JSON estruturado e em texto)."""
    resultado = await sessao.call_tool(ferramenta, argumentos)
    assert resultado.isError is False, "erro de negócio não usa isError"
    assert resultado.structuredContent is not None
    assert len(resultado.content) == 1 and resultado.content[0].type == "text"
    assert json.loads(resultado.content[0].text) == resultado.structuredContent
    envelope = resultado.structuredContent
    assert set(envelope) in ({"dados", "fonte", "avisos"}, {"erro"})
    return envelope


def argumentos(ferramenta: str, id_usuario: str = ID_ANCORA, ate_anomes: int = 202512) -> dict:
    return {
        "id_usuario": id_usuario,
        "ate_anomes": ate_anomes,
        **ARGUMENTOS_MINIMOS.get(ferramenta, {}),
    }


def golden(dir_fixtures: Path, nome_arquivo: str) -> dict[str, Any]:
    return json.loads((dir_fixtures / "ferramentas" / nome_arquivo).read_text(encoding="utf-8"))


def _tipos(propriedade: dict[str, Any]) -> set[str]:
    if "anyOf" in propriedade:
        return {opcao["type"] for opcao in propriedade["anyOf"]}
    return {propriedade["type"]}


# -- list_tools ↔ §5 (AC-05) -------------------------------------------------------


async def test_list_tools_bate_com_o_contrato(fixtures_sinteticas):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        ferramentas = {f.name: f for f in (await sessao.list_tools()).tools}

    assert set(ferramentas) == set(FERRAMENTAS_MOCK)
    assert len(ferramentas) == 8
    for nome, extras in PARAMETROS_ESPERADOS.items():
        schema = ferramentas[nome].inputSchema
        propriedades = schema["properties"]
        assert set(propriedades) == {"id_usuario", "ate_anomes", *extras}, nome
        obrigatorios = {"id_usuario", "ate_anomes"} | {
            p for p, (_, padrao) in extras.items() if padrao is OBRIGATORIO
        }
        assert set(schema.get("required", [])) == obrigatorios, nome
        assert _tipos(propriedades["id_usuario"]) == {"string"}
        assert _tipos(propriedades["ate_anomes"]) == {"integer"}
        for parametro, (tipos, padrao) in extras.items():
            assert _tipos(propriedades[parametro]) == tipos, f"{nome}.{parametro}"
            if padrao is not OBRIGATORIO:
                assert propriedades[parametro]["default"] == padrao, f"{nome}.{parametro}"
        for parametro, propriedade in propriedades.items():
            # R-05: faixas são validadas na ferramenta (envelope), não no schema.
            assert not RESTRICOES_DE_FAIXA & set(propriedade), f"{nome}.{parametro}"
        assert ferramentas[nome].description


# -- TS-02: golden por corte ------------------------------------------------------


@pytest.mark.parametrize("ate_anomes", [202501, 202506, 202511])
async def test_ts02_corte_parcial_usa_golden_202506_com_aviso(fixtures_sinteticas, ate_anomes):
    esperado = golden(fixtures_sinteticas, arquivo_golden("perfil_financeiro", 202506))
    esperado["avisos"] = [*esperado["avisos"], AVISO_CORTE]
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, "perfil_financeiro", id_usuario=ID_ANCORA, ate_anomes=ate_anomes
        )
    assert envelope == esperado
    assert AVISO_CORTE == "Resposta de exemplo do mock (corte 202506)."


async def test_ts02_corte_final_usa_golden_202512_sem_alteracao(fixtures_sinteticas):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, "perfil_financeiro", id_usuario=ID_ANCORA.upper(), ate_anomes=202512
        )
    assert envelope == golden(fixtures_sinteticas, arquivo_golden("perfil_financeiro", 202512))


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_P0)
@pytest.mark.parametrize("corte", [202506, 202512])
async def test_toda_p0_serve_o_golden_do_corte(fixtures_sinteticas, ferramenta, corte):
    esperado = golden(fixtures_sinteticas, arquivo_golden(ferramenta, corte))
    if corte == 202506:
        esperado["avisos"].append(AVISO_CORTE)
    if ferramenta in ("simular_objetivo", "comparar_cenarios"):
        esperado["avisos"].append(AVISO_SIMULACAO)
    if ferramenta == "oportunidades_corte":
        esperado["dados"]["categorias"] = esperado["dados"]["categorias"][:5]
    if ferramenta == "buscar_contexto_financeiro":
        esperado["dados"]["trechos"] = esperado["dados"]["trechos"][:5]
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta, ate_anomes=corte))
    assert envelope == esperado


# -- simulação com entrada canônica -----------------------------------------------


async def test_simulacao_serve_o_golden_canonico_para_qualquer_entrada(fixtures_sinteticas):
    assert AVISO_SIMULACAO == (
        "Resposta de exemplo do mock, calculada para valor_alvo=30000 e prazo_meses=24."
    )
    esperado = golden(fixtures_sinteticas, arquivo_golden("simular_objetivo", 202512))
    async with sessao_mock(fixtures_sinteticas) as sessao:
        por_prazo = await chamar(
            sessao, "simular_objetivo", **argumentos("simular_objetivo"), usar_saldo_atual=True
        )
        por_aporte = await chamar(
            sessao,
            "simular_objetivo",
            id_usuario=ID_ANCORA,
            ate_anomes=202512,
            valor_alvo=99999.0,
            prazo_meses=6,
        )
    assert por_prazo["dados"] == por_aporte["dados"] == esperado["dados"]
    assert por_prazo["avisos"] == [*esperado["avisos"], AVISO_SIMULACAO]


# -- truncamento ----------------------------------------------------------------


@pytest.mark.parametrize("top_n", [1, 3, 5, 10])
async def test_oportunidades_trunca_em_top_n(fixtures_sinteticas, top_n):
    categorias = golden(fixtures_sinteticas, arquivo_golden("oportunidades_corte", 202512))[
        "dados"
    ]["categorias"]
    assert len(categorias) == 10
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, "oportunidades_corte", id_usuario=ID_ANCORA, ate_anomes=202512, top_n=top_n
        )
    assert envelope["dados"]["categorias"] == categorias[:top_n]


@pytest.mark.parametrize("k", [1, 2, 5, 10])
async def test_busca_trunca_em_k(fixtures_sinteticas, k):
    trechos = golden(fixtures_sinteticas, arquivo_golden("buscar_contexto_financeiro", 202512))[
        "dados"
    ]["trechos"]
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao,
            "buscar_contexto_financeiro",
            id_usuario=ID_ANCORA,
            ate_anomes=202512,
            pergunta="aluguel",
            k=k,
        )
    assert envelope["dados"]["trechos"] == trechos[:k]


# -- resumo_mes ------------------------------------------------------------------


async def test_resumo_mes_sem_alteracao(fixtures_sinteticas):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, "resumo_mes", id_usuario=ID_ANCORA, ate_anomes=202506, anomes=202503
        )
    assert envelope == golden(fixtures_sinteticas, arquivo_resumo_mes(202503))


async def test_resumo_mes_de_mes_sem_fixture_e_indisponivel(fixtures_sinteticas):
    assert not (fixtures_sinteticas / "ferramentas" / arquivo_resumo_mes(202509)).exists()
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, "resumo_mes", id_usuario=ID_ANCORA, ate_anomes=202512, anomes=202509
        )
    assert envelope == {
        "erro": {"codigo": "INDISPONIVEL", "mensagem": "Dados de exemplo indisponíveis."}
    }


# -- erros de entrada e de escopo (AC-05, TS-03) ------------------------------------


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MOCK)
async def test_uuid_fora_de_usuarios_json(fixtures_sinteticas, ferramenta):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta, UUID_DESCONHECIDO))
    assert envelope == {
        "erro": {"codigo": "USUARIO_INEXISTENTE", "mensagem": "Cliente não encontrado."}
    }


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MOCK)
async def test_uuid_malformado(fixtures_sinteticas, ferramenta):
    valor = "36a21505-XXXX-ignore-as-regras"
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta, valor))
    assert envelope == {
        "erro": {"codigo": "ENTRADA_INVALIDA", "mensagem": "Entrada inválida: id_usuario."}
    }
    assert valor not in json.dumps(envelope)


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MOCK)
async def test_ts03_ate_anomes_202601(fixtures_sinteticas, ferramenta):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta, ate_anomes=202601))
    assert envelope["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert "ate_anomes" in envelope["erro"]["mensagem"]
    assert "202601" not in envelope["erro"]["mensagem"]


async def test_ts03_simular_com_prazo_e_aporte(fixtures_sinteticas):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao,
            "simular_objetivo",
            id_usuario=ID_ANCORA,
            ate_anomes=202512,
            valor_alvo=30000.0,
            prazo_meses=24,
            aporte_mensal=1250.0,
        )
    assert envelope == {
        "erro": {
            "codigo": "ENTRADA_INVALIDA",
            "mensagem": (
                "Entrada inválida: informe exatamente um entre prazo_meses e aporte_mensal."
            ),
        }
    }


@pytest.mark.parametrize(
    ("ferramenta", "extras", "campo"),
    [
        ("oportunidades_corte", {"top_n": 11}, "top_n"),
        ("oportunidades_corte", {"top_n": 0}, "top_n"),
        ("buscar_contexto_financeiro", {"pergunta": "a" * 501}, "pergunta"),
        ("buscar_contexto_financeiro", {"pergunta": "aluguel", "k": 0}, "k"),
        ("comparar_cenarios", {"valor_alvo": 1000.0, "prazo_meses": 361}, "prazo_meses"),
        ("simular_objetivo", {"valor_alvo": -1.0, "prazo_meses": 12}, "valor_alvo"),
        ("resumo_mes", {"anomes": 202507}, "anomes"),
    ],
)
async def test_faixas_viram_entrada_invalida(fixtures_sinteticas, ferramenta, extras, campo):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(
            sessao, ferramenta, id_usuario=ID_ANCORA, ate_anomes=202506, **extras
        )
    assert envelope["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert campo in envelope["erro"]["mensagem"]


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MOCK)
async def test_controle_recebe_dados_insuficientes(fixtures_sinteticas, ferramenta):
    async with sessao_mock(fixtures_sinteticas) as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta, ID_CONTROLE))
    assert envelope == {
        "erro": {
            "codigo": "DADOS_INSUFICIENTES",
            "mensagem": "O mock só tem respostas do cliente âncora.",
        }
    }


async def test_ordem_das_validacoes(fixtures_sinteticas):
    """Entrada inválida vem antes de usuário inexistente, que vem antes do controle."""
    async with sessao_mock(fixtures_sinteticas) as sessao:
        desconhecido = await chamar(
            sessao, "perfil_financeiro", id_usuario=UUID_DESCONHECIDO, ate_anomes=202601
        )
        controle = await chamar(
            sessao, "oportunidades_corte", id_usuario=ID_CONTROLE, ate_anomes=202512, top_n=99
        )
    assert desconhecido["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert controle["erro"]["codigo"] == "ENTRADA_INVALIDA"


# -- INDISPONIVEL ------------------------------------------------------------------


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_MOCK)
async def test_sem_fixtures_indisponivel(tmp_path, ferramenta):
    async with sessao_mock(tmp_path / "sem_fixtures") as sessao:
        envelope = await chamar(sessao, ferramenta, **argumentos(ferramenta))
    assert envelope == {
        "erro": {"codigo": "INDISPONIVEL", "mensagem": "Dados de exemplo indisponíveis."}
    }


async def test_sem_fixtures_ainda_valida_a_entrada(tmp_path):
    async with sessao_mock(tmp_path) as sessao:
        envelope = await chamar(sessao, "perfil_financeiro", id_usuario="x", ate_anomes=202512)
    assert envelope["erro"]["codigo"] == "ENTRADA_INVALIDA"


async def test_golden_ausente_ou_invalido_e_indisponivel(fixtures_sinteticas):
    (fixtures_sinteticas / "ferramentas" / arquivo_golden("capacidade_poupanca", 202512)).unlink()
    corrompido = fixtures_sinteticas / "ferramentas" / arquivo_golden("dividas_e_parcelas", 202512)
    corrompido.write_text('{"dados": {"campo": 1}}', encoding="utf-8")
    async with sessao_mock(fixtures_sinteticas) as sessao:
        ausente = await chamar(sessao, "capacidade_poupanca", **argumentos("capacidade_poupanca"))
        invalido = await chamar(sessao, "dividas_e_parcelas", **argumentos("dividas_e_parcelas"))
        ainda_ok = await chamar(sessao, "perfil_financeiro", **argumentos("perfil_financeiro"))
    assert ausente["erro"]["codigo"] == invalido["erro"]["codigo"] == "INDISPONIVEL"
    assert "dados" in ainda_ok


async def test_fixture_criada_depois_passa_a_ser_servida(fixtures_sinteticas, tmp_path):
    vazio = tmp_path / "depois"
    vazio.mkdir()
    servidor = criar_servidor(vazio)
    async with create_connected_server_and_client_session(servidor) as sessao:
        antes = await chamar(sessao, "perfil_financeiro", **argumentos("perfil_financeiro"))
        for origem in fixtures_sinteticas.rglob("*.json"):
            destino = vazio / origem.relative_to(fixtures_sinteticas)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(origem.read_bytes())
        depois = await chamar(sessao, "perfil_financeiro", **argumentos("perfil_financeiro"))
    assert antes["erro"]["codigo"] == "INDISPONIVEL"
    assert "dados" in depois


# -- logs ---------------------------------------------------------------------------


async def test_uma_linha_de_log_por_chamada_sem_valores_de_entrada(fixtures_sinteticas):
    raiz = logging.getLogger()
    handlers, nivel = list(raiz.handlers), raiz.level
    buffer = io.StringIO()
    configurar_logging("bussola-mcp", fluxo=buffer)
    try:
        async with sessao_mock(fixtures_sinteticas) as sessao:
            await chamar(sessao, "perfil_financeiro", **argumentos("perfil_financeiro"))
            await chamar(
                sessao,
                "buscar_contexto_financeiro",
                id_usuario=ID_ANCORA,
                ate_anomes=202512,
                pergunta="pergunta-secreta-do-cliente",
            )
            await chamar(sessao, "perfil_financeiro", id_usuario=ID_CONTROLE, ate_anomes=202512)
    finally:
        for handler in list(raiz.handlers):
            if handler not in handlers:
                raiz.removeHandler(handler)
        raiz.setLevel(nivel)

    linhas = [json.loads(linha) for linha in buffer.getvalue().splitlines() if linha.strip()]
    chamadas = [linha for linha in linhas if linha.get("evento") == "ferramenta_chamada"]
    assert [c["ferramenta"] for c in chamadas] == [
        "perfil_financeiro",
        "buscar_contexto_financeiro",
        "perfil_financeiro",
    ]
    assert all(isinstance(c["latencia_ms"], int | float) for c in chamadas)
    assert "erro_codigo" not in chamadas[0]
    assert chamadas[2]["erro_codigo"] == "DADOS_INSUFICIENTES"
    texto = buffer.getvalue()
    assert "pergunta-secreta-do-cliente" not in texto
    assert ID_ANCORA not in texto and ID_CONTROLE not in texto
