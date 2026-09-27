"""Códigos de erro do ciclo §3.3, por código e por ferramenta aplicável.

Erros de negócio voltam como resultado da ferramenta (``{erro: {codigo, mensagem}}``,
``isError`` falso), nunca como exceção nem stack.
"""

import json
from pathlib import Path

import pytest
from apoio_ferramentas import (
    BUSCA,
    FERRAMENTAS_CLIENTE,
    TODAS,
    UUID_DESCONHECIDO,
    BuscadorEspiao,
    CalculosFixos,
    RepositorioEspiao,
    argumentos,
    chamar,
    codigo,
    deps_golden,
    sessao,
)

from bussola_mcp.contratos import (
    ID_ANCORA,
    ID_CONTROLE,
    MENSAGENS_ERRO,
    CodigoErro,
    arquivo_golden,
)
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.golden_adapter import (
    CUT_UNAVAILABLE_MESSAGE,
    GoldenFixtureComputations,
)
from bussola_mcp.ferramentas.ports import DomainError, ToolDependencies

# ``planejar_marcos`` (009) não tem golden gravado: ``gerar_fixtures.py`` só grava
# os de ``FERRAMENTAS_GOLDEN``, e ela calcula sempre pelo domínio.
GOLDEN_P0 = tuple(
    f
    for f in FERRAMENTAS_CLIENTE
    if f not in ("resumo_mes", "referencia_coorte", "planejar_marcos")
)
SEGREDO = "SELECT * FROM `batalha-time-07-lkbv.bussola_dados.x` Bearer ya29.segredo"


def _deps(fixtures: Path, *, repo_erro=None, buscador_erro=None) -> ToolDependencies:
    repositorio = RepositorioEspiao(FixtureRepository(fixtures), erro=repo_erro)
    buscador = FixtureSearcher(fixtures)
    if buscador_erro is not None:
        buscador = BuscadorEspiao(erro=buscador_erro)
    return ToolDependencies(
        repository=repositorio,
        searcher=buscador,
        computations=GoldenFixtureComputations(fixtures, repositorio),
    )


def _reescrever_tabela(fixtures: Path, tabela: str, filtro) -> None:
    caminho = fixtures / "bussola_dados" / f"{tabela}.json"
    linhas = json.loads(caminho.read_text(encoding="utf-8"))
    caminho.write_text(json.dumps([linha for linha in linhas if filtro(linha)]), encoding="utf-8")


async def _codigo_de(fixtures: Path, ferramenta: str, args: dict, deps=None) -> dict:
    """Sem ``deps``, usa o adaptador de golden explícito (regras D-04 a D-06)."""
    async with sessao(deps=deps or deps_golden(fixtures)) as cliente:
        return await chamar(cliente, ferramenta, args)


def _assert_erro(envelope: dict, esperado: CodigoErro) -> None:
    assert codigo(envelope) == esperado, envelope
    assert envelope["erro"]["mensagem"]


# ---------------------------------------------------------------------------
# ENTRADA_INVALIDA
# ---------------------------------------------------------------------------

ID_INVALIDOS = [
    "nao-e-uuid",
    "a8098c1a-f86e-11da-bd1a-00112ba7a6a0",  # UUID v1
    "36a21505-d6d4-42d3-b319-d51a133c726",  # curto
    "' OR 1=1 --",
]


@pytest.mark.parametrize("id_usuario", ID_INVALIDOS)
@pytest.mark.parametrize("ferramenta", TODAS)
async def test_id_usuario_invalido(fixtures_sinteticas, ferramenta, id_usuario):
    envelope = await _codigo_de(
        fixtures_sinteticas, ferramenta, argumentos(ferramenta, id_usuario=id_usuario)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert "id_usuario" in envelope["erro"]["mensagem"]
    assert id_usuario not in envelope["erro"]["mensagem"]


@pytest.mark.parametrize("ate_anomes", [202412, 202513, 202601, 0])
@pytest.mark.parametrize("ferramenta", TODAS)
async def test_ate_anomes_fora_da_faixa(fixtures_sinteticas, ferramenta, ate_anomes):
    args = argumentos(ferramenta, ate_anomes=ate_anomes)
    if ferramenta == "resumo_mes":
        args["anomes"] = 202501
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, args)
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert "ate_anomes" in envelope["erro"]["mensagem"]


@pytest.mark.parametrize("valor_alvo", [0, -1.5])
@pytest.mark.parametrize("ferramenta", ["simular_objetivo", "comparar_cenarios"])
async def test_valor_alvo_nao_positivo(fixtures_sinteticas, ferramenta, valor_alvo):
    envelope = await _codigo_de(
        fixtures_sinteticas, ferramenta, argumentos(ferramenta, valor_alvo=valor_alvo)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert "valor_alvo" in envelope["erro"]["mensagem"]


@pytest.mark.parametrize(
    "extra",
    [
        {"prazo_meses": 12, "aporte_mensal": 250.0},  # cenário §7: juntos
        {"prazo_meses": None, "aporte_mensal": None},  # ausentes
        {"prazo_meses": 400, "aporte_mensal": 250.0},  # juntos, mesmo com prazo fora
    ],
)
async def test_simular_exige_exatamente_um_entre_prazo_e_aporte(fixtures_sinteticas, extra):
    envelope = await _codigo_de(
        fixtures_sinteticas, "simular_objetivo", argumentos("simular_objetivo", **extra)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)


async def test_simular_aporte_nao_positivo(fixtures_sinteticas):
    envelope = await _codigo_de(
        fixtures_sinteticas, "simular_objetivo", argumentos("simular_objetivo", aporte_mensal=0)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)


@pytest.mark.parametrize("top_n", [0, 11, -1])
async def test_top_n_fora_da_faixa(fixtures_sinteticas, top_n):
    envelope = await _codigo_de(
        fixtures_sinteticas, "oportunidades_corte", argumentos("oportunidades_corte", top_n=top_n)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert "top_n" in envelope["erro"]["mensagem"]


@pytest.mark.parametrize(
    "extra, campo",
    [
        ({"k": 0}, "k"),
        ({"k": 11}, "k"),
        ({"pergunta": "a" * 501}, "pergunta"),  # cenário §7
        ({"pergunta": "   "}, "pergunta"),
        ({"tema": "politica"}, "tema"),  # cenário §7
    ],
)
async def test_busca_entrada_invalida(fixtures_sinteticas, extra, campo):
    envelope = await _codigo_de(fixtures_sinteticas, BUSCA, argumentos(BUSCA, **extra))
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert campo in envelope["erro"]["mensagem"]
    assert "a" * 50 not in envelope["erro"]["mensagem"]


@pytest.mark.parametrize(
    "extra",
    [
        {"anomes": 202507, "ate_anomes": 202506},  # anomes > ate_anomes
        {"anomes": 202413},
        {"anomes": 202513},
    ],
)
async def test_resumo_mes_anomes_invalido(fixtures_sinteticas, extra):
    envelope = await _codigo_de(
        fixtures_sinteticas, "resumo_mes", argumentos("resumo_mes", **extra)
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)


@pytest.mark.parametrize("categoria", ["", "   ", "x" * 101])
async def test_referencia_coorte_categoria_invalida(fixtures_sinteticas, categoria):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "referencia_coorte",
        argumentos("referencia_coorte", categoria=categoria),
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)
    assert "categoria" in envelope["erro"]["mensagem"]


# ---------------------------------------------------------------------------
# USUARIO_INEXISTENTE
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ferramenta", TODAS)
async def test_usuario_inexistente(fixtures_sinteticas, ferramenta):
    envelope = await _codigo_de(
        fixtures_sinteticas, ferramenta, argumentos(ferramenta, id_usuario=UUID_DESCONHECIDO)
    )
    assert envelope == {
        "erro": {
            "codigo": "USUARIO_INEXISTENTE",
            "mensagem": MENSAGENS_ERRO[CodigoErro.USUARIO_INEXISTENTE],
        }
    }


async def test_id_em_maiusculas_e_o_mesmo_cliente(fixtures_sinteticas):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "referencia_coorte",
        argumentos("referencia_coorte", id_usuario=ID_ANCORA.upper()),
    )
    assert "dados" in envelope


# ---------------------------------------------------------------------------
# PRAZO_IMPLAUSIVEL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("prazo", [0, -3, 361, 1000])
@pytest.mark.parametrize("ferramenta", ["simular_objetivo", "comparar_cenarios"])
async def test_prazo_fora_de_1_a_360(fixtures_sinteticas, ferramenta, prazo):
    args = argumentos(ferramenta, prazo_meses=prazo)
    args.pop("aporte_mensal", None)
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, args)
    assert envelope == {
        "erro": {
            "codigo": "PRAZO_IMPLAUSIVEL",
            "mensagem": MENSAGENS_ERRO[CodigoErro.PRAZO_IMPLAUSIVEL],
        }
    }


@pytest.mark.parametrize("ferramenta", ["simular_objetivo", "comparar_cenarios"])
async def test_prazo_fora_com_outro_erro_continua_entrada_invalida(fixtures_sinteticas, ferramenta):
    args = argumentos(ferramenta, prazo_meses=400, valor_alvo=-1)
    args.pop("aporte_mensal", None)
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, args)
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)


async def test_prazo_calculado_acima_de_360_vira_prazo_implausivel(fixtures_sinteticas):
    """``prazo_para_meta`` > 360 (001) chega como ``DomainError(PRAZO_IMPLAUSIVEL)``."""
    calculos = CalculosFixos(erro=DomainError(CodigoErro.PRAZO_IMPLAUSIVEL))
    deps = ToolDependencies(
        repository=FixtureRepository(fixtures_sinteticas),
        searcher=FixtureSearcher(fixtures_sinteticas),
        computations=calculos,
    )
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "simular_objetivo",
        argumentos("simular_objetivo", valor_alvo=1_000_000.0, aporte_mensal=10.0),
        deps,
    )
    _assert_erro(envelope, CodigoErro.PRAZO_IMPLAUSIVEL)
    assert calculos.chamadas == [
        ("simular_objetivo", (ID_ANCORA, 202512, 1_000_000.0, None, 10.0, False))
    ]


# ---------------------------------------------------------------------------
# DADOS_INSUFICIENTES
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ferramenta", [*GOLDEN_P0, "resumo_mes"])
async def test_controle_sem_golden_e_calculado_pelo_dominio(fixtures_sinteticas, ferramenta):
    """BUG-05: só o âncora tem golden, mas não ter golden não é não ter histórico.

    A decisão D-06 (``DADOS_INSUFICIENTES`` para quem não é o âncora) fazia o
    cliente de controle parecer sem dados. Agora o cálculo cai no domínio.
    """
    envelope = await _codigo_de(
        fixtures_sinteticas, ferramenta, argumentos(ferramenta, id_usuario=ID_CONTROLE)
    )
    assert "erro" not in envelope, envelope


@pytest.mark.parametrize("ferramenta", [*GOLDEN_P0, "resumo_mes", "referencia_coorte"])
async def test_nenhum_mes_ate_o_corte(fixtures_sinteticas, ferramenta):
    _reescrever_tabela(
        fixtures_sinteticas,
        "perfil_mensal",
        lambda linha: linha["id_usuario"] != ID_ANCORA or linha["anomes"] >= 202507,
    )
    args = argumentos(ferramenta, ate_anomes=202506)
    if ferramenta == "resumo_mes":
        args["anomes"] = 202503
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, args)
    _assert_erro(envelope, CodigoErro.DADOS_INSUFICIENTES)


async def test_resumo_de_mes_sem_dados_do_cliente(fixtures_sinteticas):
    _reescrever_tabela(
        fixtures_sinteticas,
        "perfil_mensal",
        lambda linha: linha["id_usuario"] != ID_ANCORA or linha["anomes"] != 202503,
    )
    envelope = await _codigo_de(
        fixtures_sinteticas, "resumo_mes", argumentos("resumo_mes", anomes=202503)
    )
    _assert_erro(envelope, CodigoErro.DADOS_INSUFICIENTES)


async def test_referencia_de_categoria_desconhecida(fixtures_sinteticas):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "referencia_coorte",
        argumentos("referencia_coorte", categoria="Categoria que não existe"),
    )
    _assert_erro(envelope, CodigoErro.DADOS_INSUFICIENTES)


# ---------------------------------------------------------------------------
# INDISPONIVEL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ferramenta", TODAS)
async def test_sem_fixtures_fica_indisponivel(tmp_path, ferramenta):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    envelope = await _codigo_de(vazio, ferramenta, argumentos(ferramenta))
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)


@pytest.mark.parametrize("ferramenta", FERRAMENTAS_CLIENTE)
async def test_bigquery_indisponivel_nao_vaza_detalhe(fixtures_sinteticas, ferramenta):
    """Cenário §7: repositório que lança exceção → INDISPONIVEL, sem SQL nem token."""
    deps = _deps(fixtures_sinteticas, repo_erro=RuntimeError(SEGREDO))
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, argumentos(ferramenta), deps)
    assert envelope == {
        "erro": {"codigo": "INDISPONIVEL", "mensagem": MENSAGENS_ERRO[CodigoErro.INDISPONIVEL]}
    }


@pytest.mark.parametrize("ferramenta", TODAS)
async def test_falha_ao_verificar_cliente_fica_indisponivel(fixtures_sinteticas, ferramenta):
    class RepositorioQuebrado(FixtureRepository):
        def usuario_existe(self, id_usuario: str) -> bool:
            raise ConnectionError(SEGREDO)

    repositorio = RepositorioQuebrado(fixtures_sinteticas)
    deps = ToolDependencies(
        repository=repositorio,
        searcher=FixtureSearcher(fixtures_sinteticas),
        computations=GoldenFixtureComputations(fixtures_sinteticas, repositorio),
    )
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, argumentos(ferramenta), deps)
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)
    assert "SELECT" not in json.dumps(envelope)


async def test_embedding_indisponivel(fixtures_sinteticas):
    deps = _deps(fixtures_sinteticas, buscador_erro=TimeoutError(SEGREDO))
    envelope = await _codigo_de(fixtures_sinteticas, BUSCA, argumentos(BUSCA), deps)
    assert envelope == {
        "erro": {"codigo": "INDISPONIVEL", "mensagem": MENSAGENS_ERRO[CodigoErro.INDISPONIVEL]}
    }


async def test_corpus_invalido_fica_indisponivel(fixtures_sinteticas):
    (fixtures_sinteticas / "rag" / "trechos_exemplo.json").write_text("{nao é json", "utf-8")
    envelope = await _codigo_de(fixtures_sinteticas, BUSCA, argumentos(BUSCA))
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)


async def test_tabela_invalida_fica_indisponivel(fixtures_sinteticas):
    (fixtures_sinteticas / "bussola_dados" / "perfil_mensal.json").write_text("[{", "utf-8")
    envelope = await _codigo_de(
        fixtures_sinteticas, "perfil_financeiro", argumentos("perfil_financeiro")
    )
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)


@pytest.mark.parametrize("ferramenta", GOLDEN_P0)
async def test_corte_anterior_a_202506_sem_golden(fixtures_sinteticas, ferramenta):
    envelope = await _codigo_de(
        fixtures_sinteticas, ferramenta, argumentos(ferramenta, ate_anomes=202503)
    )
    assert envelope == {"erro": {"codigo": "INDISPONIVEL", "mensagem": CUT_UNAVAILABLE_MESSAGE}}


@pytest.mark.parametrize("ferramenta", GOLDEN_P0)
async def test_golden_ausente(fixtures_sinteticas, ferramenta):
    (fixtures_sinteticas / "ferramentas" / arquivo_golden(ferramenta, 202512)).unlink()
    envelope = await _codigo_de(fixtures_sinteticas, ferramenta, argumentos(ferramenta))
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)


async def test_resumo_de_mes_sem_golden(fixtures_sinteticas):
    """As fixtures sintéticas não têm ``resumo_mes__202507`` (conftest)."""
    envelope = await _codigo_de(
        fixtures_sinteticas, "resumo_mes", argumentos("resumo_mes", anomes=202507)
    )
    _assert_erro(envelope, CodigoErro.INDISPONIVEL)


async def test_calculo_com_falha_inesperada_fica_indisponivel(fixtures_sinteticas):
    deps = ToolDependencies(
        repository=FixtureRepository(fixtures_sinteticas),
        searcher=FixtureSearcher(fixtures_sinteticas),
        computations=CalculosFixos(erro=ZeroDivisionError(SEGREDO)),
    )
    envelope = await _codigo_de(
        fixtures_sinteticas, "capacidade_poupanca", argumentos("capacidade_poupanca"), deps
    )
    assert envelope == {
        "erro": {"codigo": "INDISPONIVEL", "mensagem": MENSAGENS_ERRO[CodigoErro.INDISPONIVEL]}
    }


# ---------------------------------------------------------------------------
# Precedência
# ---------------------------------------------------------------------------


async def test_entrada_invalida_antes_de_usuario_inexistente(fixtures_sinteticas):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "perfil_financeiro",
        argumentos("perfil_financeiro", id_usuario=UUID_DESCONHECIDO, ate_anomes=202601),
    )
    _assert_erro(envelope, CodigoErro.ENTRADA_INVALIDA)


async def test_prazo_implausivel_antes_de_usuario_inexistente(fixtures_sinteticas):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        "comparar_cenarios",
        argumentos("comparar_cenarios", id_usuario=UUID_DESCONHECIDO, prazo_meses=361),
    )
    _assert_erro(envelope, CodigoErro.PRAZO_IMPLAUSIVEL)


@pytest.mark.parametrize("ferramenta", GOLDEN_P0)
async def test_usuario_inexistente_antes_de_corte_indisponivel(fixtures_sinteticas, ferramenta):
    envelope = await _codigo_de(
        fixtures_sinteticas,
        ferramenta,
        argumentos(ferramenta, id_usuario=UUID_DESCONHECIDO, ate_anomes=202503),
    )
    _assert_erro(envelope, CodigoErro.USUARIO_INEXISTENTE)


async def test_nenhuma_leitura_de_dados_com_entrada_invalida(fixtures_sinteticas):
    deps = _deps(fixtures_sinteticas)
    await _codigo_de(
        fixtures_sinteticas,
        "perfil_financeiro",
        argumentos("perfil_financeiro", ate_anomes=202601),
        deps,
    )
    assert deps.repository.chamadas == []
