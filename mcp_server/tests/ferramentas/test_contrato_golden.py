"""Contrato por ferramenta sobre as fixtures oficiais (contratos §8, critério §6 do ciclo).

Com as fixtures de ``contracts/fixtures/``, o envelope de cada ferramenta de
``FERRAMENTAS_GOLDEN`` bate com o golden ``__ate_202506`` e ``__ate_202512``
para a entrada canônica. ``resumo_mes`` bate com o golden de cada mês.
"""

import pytest
from apoio_ferramentas import (
    BUSCA,
    DIR_OFICIAL,
    argumentos,
    chamar,
    ler_golden,
    sessao,
)

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS,
    FERRAMENTAS_GOLDEN,
    ID_ANCORA,
    ID_CONTROLE,
    TABELAS_FERRAMENTA,
    Resposta,
    arquivo_golden,
    arquivo_resumo_mes,
)

MESES = tuple(range(202501, 202513))
ENTRADA_GOLDEN: dict[str, dict[str, object]] = {
    "oportunidades_corte": {"top_n": 10},
    "simular_objetivo": dict(ENTRADA_CANONICA_SIMULACAO),
    "comparar_cenarios": dict(ENTRADA_CANONICA_SIMULACAO),
}


def _argumentos_golden(ferramenta: str, corte: int) -> dict[str, object]:
    return {"id_usuario": ID_ANCORA, "ate_anomes": corte, **ENTRADA_GOLDEN.get(ferramenta, {})}


@pytest.mark.parametrize("corte", CORTES_GOLDEN)
@pytest.mark.parametrize("ferramenta", FERRAMENTAS_GOLDEN)
async def test_envelope_bate_com_o_golden(ferramenta, corte):
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(cliente, ferramenta, _argumentos_golden(ferramenta, corte))
    assert envelope == ler_golden(DIR_OFICIAL, arquivo_golden(ferramenta, corte))


async def test_resumo_mes_bate_com_o_golden_de_cada_mes():
    async with sessao(DIR_OFICIAL) as cliente:
        for anomes in MESES:
            envelope = await chamar(
                cliente, "resumo_mes", argumentos("resumo_mes", anomes=anomes, ate_anomes=202512)
            )
            assert envelope == ler_golden(DIR_OFICIAL, arquivo_resumo_mes(anomes)), anomes


async def test_resumo_mes_nao_depende_do_corte_quando_o_mes_esta_disponivel():
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente, "resumo_mes", argumentos("resumo_mes", anomes=202503, ate_anomes=202503)
        )
    assert envelope == ler_golden(DIR_OFICIAL, arquivo_resumo_mes(202503))


async def test_oportunidades_respeita_top_n():
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente, "oportunidades_corte", argumentos("oportunidades_corte", top_n=3)
        )
    golden = ler_golden(DIR_OFICIAL, arquivo_golden("oportunidades_corte", 202512))
    assert envelope["dados"]["categorias"] == golden["dados"]["categorias"][:3]
    assert envelope["fonte"] == golden["fonte"]


async def test_oportunidades_top_n_padrao_e_5():
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente, "oportunidades_corte", {"id_usuario": ID_ANCORA, "ate_anomes": 202512}
        )
    assert len(envelope["dados"]["categorias"]) == 5


async def test_cenario_7_comparar_cenarios_ancora_202506():
    """Cenário §7: comparar_cenarios(âncora, 202506, 60000, 24) → 3 cenários, fim 202506."""
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente,
            "comparar_cenarios",
            {
                "id_usuario": ID_ANCORA,
                "ate_anomes": 202506,
                "valor_alvo": 60000.0,
                "prazo_meses": 24,
            },
        )
    assert len(envelope["dados"]["cenarios"]) == 3
    assert {c["nome"] for c in envelope["dados"]["cenarios"]} == {
        "conservador",
        "equilibrado",
        "acelerado",
    }
    assert envelope["fonte"]["periodo"]["fim"] == 202506


async def test_cenario_7_simular_objetivo_ancora_202512_modo_prazo():
    """Cenário §7 (parte verificável sem o 001): prazo informado → ``modo = "prazo"``.

    A coerência de ``aporte_mensal``/``viavel`` com ``aporte_para_prazo`` fica em
    ``test_simulacao_coerencia.py``, que roda quando o 001 estiver em ``main``.
    """
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente,
            "simular_objetivo",
            {
                "id_usuario": ID_ANCORA,
                "ate_anomes": 202512,
                "valor_alvo": 60000.0,
                "prazo_meses": 24,
            },
        )
    assert envelope["dados"]["modo"] == "prazo"
    assert envelope["dados"]["aporte_mensal"] > 0
    assert isinstance(envelope["dados"]["viavel"], bool)


async def test_referencia_coorte_da_faixa_do_cliente():
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente, "referencia_coorte", argumentos("referencia_coorte", categoria="lazer")
        )
    dados = envelope["dados"]
    assert dados == {
        "faixa_renda": "6k_10k",
        "macro": "Lazer",
        "media": 364.2,
        "mediana": 223.47,
        "qtd_usuarios": 490,
    }
    assert envelope["fonte"]["tabelas"] == ["bussola_dados.referencia_coorte"]
    assert envelope["fonte"]["periodo"] == {"inicio": 202501, "fim": 202512}
    assert envelope["avisos"]


def _todas_chamadas() -> list[tuple[str, dict[str, object]]]:
    chamadas: list[tuple[str, dict[str, object]]] = [
        (f, _argumentos_golden(f, 202512)) for f in FERRAMENTAS_GOLDEN
    ]
    chamadas += [
        ("resumo_mes", argumentos("resumo_mes")),
        ("referencia_coorte", argumentos("referencia_coorte")),
        (BUSCA, argumentos(BUSCA, pergunta="Como funciona o rotativo do cartão?")),
        # 009: sem golden gravado, calcula pelo domínio — mas o envelope é o mesmo contrato.
        ("planejar_marcos", argumentos("planejar_marcos")),
    ]
    return chamadas


async def test_todo_sucesso_traz_dados_e_fonte_completos():
    """Critério §6: ``dados`` válidos pelo modelo de §5 e ``fonte`` completa."""
    chamadas = _todas_chamadas()
    assert {f for f, _ in chamadas} == set(FERRAMENTAS)
    async with sessao(DIR_OFICIAL) as cliente:
        for ferramenta, args in chamadas:
            envelope = await chamar(cliente, ferramenta, args)
            assert "erro" not in envelope, (ferramenta, envelope)
            Resposta[FERRAMENTAS[ferramenta][1]].model_validate(envelope)
            fonte = envelope["fonte"]
            assert fonte["ferramenta"] == ferramenta
            assert fonte["tabelas"] == TABELAS_FERRAMENTA[ferramenta]
            assert all(t.startswith("bussola_dados.") for t in fonte["tabelas"])
            periodo = fonte["periodo"]
            assert 202501 <= periodo["inicio"] <= periodo["fim"] <= args["ate_anomes"]
            assert isinstance(envelope["avisos"], list)


async def test_valores_brl_com_no_maximo_duas_casas():
    # ``regras`` (009) são premissas versionadas — frações e contagens, não valores
    # do cliente —, e ``fracao_reserva_parcial`` é 1/3 de propósito. O único valor em
    # BRL de lá é conferido à parte, em test_regras_de_marco_em_brl_tem_duas_casas.
    SEM_BRL = {"regras"}

    def numeros(valor):
        if isinstance(valor, dict):
            for chave, item in valor.items():
                if chave not in SEM_BRL:
                    yield from numeros(item)
        elif isinstance(valor, list):
            for item in valor:
                yield from numeros(item)
        elif isinstance(valor, float):
            yield valor

    async with sessao(DIR_OFICIAL) as cliente:
        for ferramenta, args in _todas_chamadas():
            if ferramenta == BUSCA:
                continue  # score de relevância não é valor em BRL
            envelope = await chamar(cliente, ferramenta, args)
            for numero in numeros(envelope["dados"]):
                assert round(numero, 2) == numero, (ferramenta, numero)


async def test_regras_de_marco_em_brl_tem_duas_casas():
    """O único valor em BRL de ``dados.regras`` do 009 segue a regra das 2 casas."""
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(cliente, "planejar_marcos", argumentos("planejar_marcos"))
    piso = envelope["dados"]["regras"]["piso_valor_marco"]
    assert round(piso, 2) == piso


async def test_controle_existe_nas_fixtures_oficiais():
    """Sanidade: o controle é cliente conhecido (não USUARIO_INEXISTENTE)."""
    async with sessao(DIR_OFICIAL) as cliente:
        envelope = await chamar(
            cliente, "referencia_coorte", argumentos("referencia_coorte", ID_CONTROLE)
        )
    assert "dados" in envelope
