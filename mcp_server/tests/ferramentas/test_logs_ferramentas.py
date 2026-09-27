"""Logs das ferramentas (contratos §9 e ciclo §3.4).

Uma linha ``ferramenta_chamada`` por chamada com ``ferramenta``, ``latencia_ms``,
``erro_codigo`` e ``ate_anomes``. Nunca a pergunta, textos, ids nem detalhes de
exceção (só o nome da classe em ``excecao``).
"""

import pytest
from apoio_ferramentas import (
    BUSCA,
    TODAS,
    UUID_DESCONHECIDO,
    RepositorioEspiao,
    argumentos,
    capturar_logs,
    chamar,
    linhas_json,
    sessao,
)

from bussola_mcp.contratos import ID_ANCORA, ID_CONTROLE
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.golden_adapter import GoldenFixtureComputations
from bussola_mcp.ferramentas.ports import ToolDependencies
from bussola_mcp.logging_json import CAMPOS_EXTRAS_PERMITIDOS

CAMPOS_BASE = {"severity", "message", "servico", "timestamp"}
PERGUNTA = "Minha pergunta muito pessoal sobre o rotativo do cartão"


def _chamadas(linhas):
    return [linha for linha in linhas if linha.get("evento") == "ferramenta_chamada"]


async def _rodar(fixtures, pares, deps=None):
    with capturar_logs() as buffer:
        async with sessao(fixtures, deps) as cliente:
            envelopes = [await chamar(cliente, f, a) for f, a in pares]
    return envelopes, linhas_json(buffer)


async def test_uma_linha_por_chamada_com_os_campos_de_9(fixtures_sinteticas):
    pares = [(f, argumentos(f)) for f in TODAS]
    _, linhas = await _rodar(fixtures_sinteticas, pares)
    chamadas = _chamadas(linhas)
    assert [linha["ferramenta"] for linha in chamadas] == list(TODAS)
    for linha in chamadas:
        assert set(linha) <= CAMPOS_BASE | set(CAMPOS_EXTRAS_PERMITIDOS)
        assert linha["servico"] == "bussola-mcp"
        assert linha["severity"] == "INFO"
        assert linha["ate_anomes"] == 202512
        assert isinstance(linha["latencia_ms"], int | float) and linha["latencia_ms"] >= 0
        assert "erro_codigo" not in linha
        assert "id_usuario" not in linha


@pytest.mark.parametrize(
    "ferramenta, args, codigo_esperado",
    [
        ("perfil_financeiro", {"id_usuario": UUID_DESCONHECIDO}, "USUARIO_INEXISTENTE"),
        ("capacidade_poupanca", {"id_usuario": ID_CONTROLE}, "DADOS_INSUFICIENTES"),
        ("comparar_cenarios", {"prazo_meses": 361}, "PRAZO_IMPLAUSIVEL"),
    ],
)
async def test_erro_de_negocio_registra_codigo_e_corte(
    fixtures_sinteticas, ferramenta, args, codigo_esperado
):
    _, linhas = await _rodar(fixtures_sinteticas, [(ferramenta, argumentos(ferramenta, **args))])
    (linha,) = _chamadas(linhas)
    assert linha["erro_codigo"] == codigo_esperado
    assert linha["severity"] == "INFO"


async def test_entrada_invalida_nao_registra_corte(fixtures_sinteticas):
    _, linhas = await _rodar(
        fixtures_sinteticas, [("perfil_financeiro", argumentos("perfil_financeiro", "abc"))]
    )
    (linha,) = _chamadas(linhas)
    assert linha["erro_codigo"] == "ENTRADA_INVALIDA"
    assert "ate_anomes" not in linha


async def test_bigquery_indisponivel_loga_codigo_e_so_a_classe_da_excecao(fixtures_sinteticas):
    """Cenário §7: mock que lança exceção → INDISPONIVEL e ``erro_codigo`` no log."""
    repositorio = RepositorioEspiao(
        FixtureRepository(fixtures_sinteticas), erro=RuntimeError("SELECT segredo")
    )
    deps = ToolDependencies(
        repository=repositorio,
        searcher=FixtureSearcher(fixtures_sinteticas),
        computations=GoldenFixtureComputations(fixtures_sinteticas, repositorio),
    )
    envelopes, linhas = await _rodar(
        fixtures_sinteticas, [("perfil_financeiro", argumentos("perfil_financeiro"))], deps
    )
    assert envelopes[0]["erro"]["codigo"] == "INDISPONIVEL"
    (chamada,) = _chamadas(linhas)
    assert chamada["erro_codigo"] == "INDISPONIVEL"
    assert chamada["severity"] == "WARNING"
    (falha,) = [linha for linha in linhas if linha.get("evento") == "ferramenta_falhou"]
    assert falha["excecao"] == "RuntimeError"
    assert falha["ferramenta"] == "perfil_financeiro"
    assert falha["severity"] == "ERROR"
    assert "segredo" not in "".join(str(v) for linha in linhas for v in linha.values())


async def test_fixture_ausente_loga_backend_indisponivel(tmp_path):
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    _, linhas = await _rodar(vazio, [(BUSCA, argumentos(BUSCA))])
    (backend,) = [linha for linha in linhas if linha.get("evento") == "backend_indisponivel"]
    assert backend["severity"] == "WARNING"
    assert backend["excecao"] == "BackendUnavailable"
    (chamada,) = _chamadas(linhas)
    assert chamada["erro_codigo"] == "INDISPONIVEL"


async def test_nunca_loga_pergunta_texto_nem_ids(fixtures_sinteticas):
    pares = [
        (BUSCA, argumentos(BUSCA, pergunta=PERGUNTA)),
        ("referencia_coorte", argumentos("referencia_coorte", categoria="Lazer")),
        ("perfil_financeiro", argumentos("perfil_financeiro", ID_CONTROLE)),
        ("resumo_mes", argumentos("resumo_mes")),
    ]
    _, linhas = await _rodar(fixtures_sinteticas, pares)
    texto = "\n".join(str(linha) for linha in linhas)
    for proibido in (PERGUNTA, "rotativo", ID_ANCORA, ID_CONTROLE, "Lazer", "Aluguel"):
        assert proibido not in texto
