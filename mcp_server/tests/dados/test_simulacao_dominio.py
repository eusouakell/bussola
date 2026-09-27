"""Testes das funções puras de ``dominio/simulacao.py`` (ciclo 001, T007).

Cobre casos conhecidos, bordas (sobra ≤ 0, saldo ≥ alvo, prazo impossível), ausência
de divisão por zero (TS-04), ordem dos cenários (TS-03) e validação de entrada.
"""

import dataclasses
import math

import pytest

from bussola_mcp.contratos import (
    ENTRADA_CANONICA_SIMULACAO,
    Categoria,
    GastoCategoria,
    Parcela,
    PerfilMes,
    RegrasCenario,
)
from bussola_mcp.dominio.simulacao import (
    MAX_TERM_MONTHS,
    REASON_NO_CONTRIBUTION,
    REASON_NO_INCOME,
    REASON_NO_INSTALLMENTS,
    REASON_NO_SAVINGS,
    REASON_NO_SPENDING,
    REASON_NO_SURPLUS,
    REASON_TARGET_COVERED,
    REASON_TERM_TOO_LONG,
    REASON_TERM_TOO_SHORT,
    Capacidade,
    ResultadoAporte,
    ResultadoPrazo,
    aporte_para_prazo,
    format_brl_whole,
    format_months,
    format_percent,
    gerar_cenarios,
    impacto_cortes,
    impacto_dividas,
    mean_brl,
    median_brl,
    months_to_reach,
    normalize_label,
    opportunity_criterion,
    prazo_para_meta,
    rank_opportunities,
)

ID = "36a21505-d6d4-42d3-b319-d51a133c7269"


def _gasto(anomes: int, macro: str, micro: str, total: float) -> GastoCategoria:
    return GastoCategoria(
        id_usuario=ID, anomes=anomes, macro=macro, micro=micro, total=total, qtd=1
    )


def _perfil(anomes: int, sobra: float) -> PerfilMes:
    return PerfilMes(
        id_usuario=ID,
        anomes=anomes,
        renda=5000.0,
        gasto=round(5000.0 - sobra, 2),
        sobra=sobra,
        saldo_inicial=0.0,
        saldo_final=0.0,
        saldo_minimo=0.0,
        saldo_maximo=0.0,
        juros=0.0,
    )


def _parcela(descr: str, atual: int, total: int, vlr: float) -> Parcela:
    return Parcela(
        id_usuario=ID,
        anomes=202512,
        descr=descr,
        macro="Compras",
        parcela_atual=atual,
        parcela_total=total,
        vlr=vlr,
    )


GASTOS = [
    _gasto(202501, "Lazer", "Restaurantes", 400.0),
    _gasto(202502, "Lazer", "Restaurantes", 600.0),
    _gasto(202501, "Lazer", "Bares", 100.0),
    _gasto(202502, "Lazer", "Bares", 100.0),
    _gasto(202501, "Moradia", "Aluguel", 1000.0),
    _gasto(202502, "Moradia", "Aluguel", 1000.0),
    _gasto(202501, "Alimentação", "Padaria", 80.0),
    _gasto(202502, "Alimentação", "Padaria", 120.0),
]

CATEGORIAS = [
    Categoria(macro="Lazer", micro="Restaurantes", discricionaria=True, corte_max_pct=0.3),
    Categoria(macro="Lazer", micro="Bares", discricionaria=True, corte_max_pct=0.5),
    Categoria(macro="Moradia", micro="Aluguel", discricionaria=False, corte_max_pct=0.0),
]


def _brute_force_term(alvo: float, aporte: float, saldo: float, taxa: float) -> int:
    """Menor n com saldo composto ≥ alvo, por iteração (referência independente)."""
    valor, n = saldo, 0
    while valor < alvo - 1e-9:
        valor = valor * (1 + taxa) + aporte
        n += 1
    return n


# ---------------------------------------------------------------------------
# prazo_para_meta
# ---------------------------------------------------------------------------


def test_prazo_sem_rendimento_caso_conhecido():
    assert prazo_para_meta(30000.0, 1250.0) == ResultadoPrazo(24, True, None)
    assert prazo_para_meta(30000.0, 1000.0, saldo_inicial=6000.0).prazo_meses == 24
    assert prazo_para_meta(30000.0, 1300.0).prazo_meses == 24  # 23,08 → 24


def test_prazo_saldo_cobre_alvo_da_zero_viavel():
    resultado = prazo_para_meta(30000.0, 500.0, saldo_inicial=30000.0)
    assert resultado == ResultadoPrazo(0, True, REASON_TARGET_COVERED)
    assert prazo_para_meta(30000.0, 0.0, saldo_inicial=45000.0).viavel is True


def test_prazo_sem_aporte_nao_divide_por_zero():
    """TS-04: ``prazo_para_meta(60000, 0)`` é inviável, com motivo, sem ZeroDivisionError."""
    resultado = prazo_para_meta(60000.0, 0)
    assert resultado.viavel is False
    assert resultado.prazo_meses == 0
    assert resultado.motivo == REASON_NO_CONTRIBUTION
    # Com rendimento e sem saldo nem aporte também não há crescimento possível.
    assert prazo_para_meta(60000.0, 0, rendimento_mensal=0.01).motivo == REASON_NO_CONTRIBUTION


def test_prazo_acima_do_limite_e_inviavel_mas_volta_o_prazo():
    resultado = prazo_para_meta(100000.0, 100.0)
    assert resultado.prazo_meses == 1000
    assert resultado.viavel is False
    assert resultado.motivo == REASON_TERM_TOO_LONG
    assert prazo_para_meta(36000.0, 100.0).prazo_meses == MAX_TERM_MONTHS
    assert prazo_para_meta(36000.0, 100.0).viavel is True


@pytest.mark.parametrize(
    ("alvo", "aporte", "saldo", "taxa"),
    [
        (11500.0, 1000.0, 0.0, 0.01),
        (60000.0, 0.0, 30000.0, 0.01),
        (30000.0, 800.0, 2500.0, 0.005),
        (1000.0, 999.0, 0.0, 0.001),
        (250000.0, 1500.0, 10000.0, 0.008),
    ],
)
def test_prazo_com_rendimento_bate_com_iteracao(alvo, aporte, saldo, taxa):
    resultado = prazo_para_meta(alvo, aporte, saldo, taxa)
    assert resultado.prazo_meses == _brute_force_term(alvo, aporte, saldo, taxa)


def test_rendimento_encurta_o_prazo():
    assert prazo_para_meta(11500.0, 1000.0).prazo_meses == 12
    assert prazo_para_meta(11500.0, 1000.0, rendimento_mensal=0.01).prazo_meses == 11


# ---------------------------------------------------------------------------
# aporte_para_prazo
# ---------------------------------------------------------------------------


def test_aporte_da_entrada_canonica():
    entrada = ENTRADA_CANONICA_SIMULACAO
    resultado = aporte_para_prazo(entrada["valor_alvo"], entrada["prazo_meses"])
    assert resultado == ResultadoAporte(1250.0, True, None)


def test_aporte_bordas():
    assert aporte_para_prazo(30000.0, 24, saldo_inicial=6000.0).aporte_mensal == 1000.0
    assert aporte_para_prazo(30000.0, 24, saldo_inicial=30000.0) == ResultadoAporte(
        0.0, True, REASON_TARGET_COVERED
    )
    assert aporte_para_prazo(30000.0, 0) == ResultadoAporte(0.0, False, REASON_TERM_TOO_SHORT)
    longo = aporte_para_prazo(30000.0, 400)
    assert longo == ResultadoAporte(75.0, False, REASON_TERM_TOO_LONG)


def test_aporte_com_rendimento():
    taxa = 0.01
    esperado = round(12000.0 * taxa / ((1 + taxa) ** 12 - 1), 2)
    resultado = aporte_para_prazo(12000.0, 12, rendimento_mensal=taxa)
    assert resultado.aporte_mensal == esperado == 946.19
    assert resultado.aporte_mensal < aporte_para_prazo(12000.0, 12).aporte_mensal
    # O saldo inicial rendendo já passa do alvo: aporte mínimo 0.
    assert aporte_para_prazo(10000.0, 120, 9000.0, 0.01).aporte_mensal == 0.0


def test_aporte_sai_com_duas_casas():
    resultado = aporte_para_prazo(30000.0, 7)
    assert resultado.aporte_mensal == 4285.71


# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argumentos",
    [
        (0.0, 100.0),
        (-1.0, 100.0),
        (math.nan, 100.0),
        (math.inf, 100.0),
        (True, 100.0),
        ("30000", 100.0),
        (30000.0, -1.0),
        (30000.0, math.inf),
        (30000.0, 100.0, -5.0),
        (30000.0, 100.0, 0.0, -0.01),
        (30000.0, 100.0, 0.0, math.nan),
    ],
)
def test_prazo_rejeita_entradas_invalidas(argumentos):
    with pytest.raises(ValueError):
        prazo_para_meta(*argumentos)


@pytest.mark.parametrize(
    "argumentos",
    [
        (30000.0, 12.5),
        (30000.0, True),
        (30000.0, "24"),
        (-30000.0, 24),
        (30000.0, 24, math.nan),
        (30000.0, 24, 0.0, -0.01),
    ],
)
def test_aporte_rejeita_entradas_invalidas(argumentos):
    with pytest.raises(ValueError):
        aporte_para_prazo(*argumentos)


def test_resultados_sao_imutaveis():
    resultado = prazo_para_meta(30000.0, 1250.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        resultado.prazo_meses = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Capacidade e cenários
# ---------------------------------------------------------------------------


def test_capacidade_da_sobra_mediana():
    capacidade = Capacidade.from_profile(
        [_perfil(202501, 100.0), _perfil(202502, -50.0), _perfil(202503, 300.0)]
    )
    assert capacidade == Capacidade(sobra_mediana=100.0, meses_considerados=3)
    assert capacidade.viavel is True
    assert capacidade.motivo is None


def test_capacidade_sem_sobra_e_inviavel_com_motivo():
    capacidade = Capacidade(sobra_mediana=0.0, meses_considerados=12)
    assert capacidade.viavel is False
    assert capacidade.motivo == REASON_NO_SURPLUS
    with pytest.raises(ValueError):
        Capacidade.from_profile([])


def test_cenarios_em_ordem_de_aporte_e_prazo():
    """TS-03: aportes conservador < equilibrado < acelerado; acelerado com o menor prazo."""
    cenarios = gerar_cenarios(Capacidade(2000.0, 2), 30000.0, 24, GASTOS, CATEGORIAS)
    por_nome = {c.nome: c for c in cenarios}
    assert [c.nome for c in cenarios] == ["conservador", "equilibrado", "acelerado"]
    conservador, equilibrado, acelerado = (
        por_nome["conservador"],
        por_nome["equilibrado"],
        por_nome["acelerado"],
    )
    assert conservador.aporte_mensal < equilibrado.aporte_mensal < acelerado.aporte_mensal
    assert acelerado.prazo_meses == min(c.prazo_meses for c in cenarios)
    assert conservador.aporte_mensal == 800.0
    assert equilibrado.aporte_mensal == 1200.0
    # Cortes: Restaurantes 500 × 30% = 150; Bares 100 × 50% = 50.
    assert [(c.micro, c.valor_mensal) for c in acelerado.cortes_sugeridos] == [
        ("Restaurantes", 150.0),
        ("Bares", 50.0),
    ]
    assert acelerado.aporte_mensal == 1800.0
    assert acelerado.prazo_meses == 17
    assert conservador.cortes_sugeridos == [] and equilibrado.cortes_sugeridos == []
    assert [c.viavel for c in cenarios] == [False, False, True]
    assert conservador.trade_offs[0] == "Precisa de 38 meses, além do prazo de 24 meses."
    assert acelerado.trade_offs[0] == "Atinge a meta em 17 meses, dentro do prazo de 24 meses."
    assert acelerado.trade_offs[1] == "Compromete 80% da sobra mensal mediana (R$ 1.600/mês)."
    assert acelerado.trade_offs[2] == "Exige reduzir R$ 150/mês em Restaurantes."


def test_cenarios_sem_sobra_so_cortes_geram_aporte():
    cenarios = gerar_cenarios(Capacidade(-100.0, 2), 30000.0, 24, GASTOS, CATEGORIAS)
    por_nome = {c.nome: c for c in cenarios}
    for nome in ("conservador", "equilibrado"):
        assert por_nome[nome].aporte_mensal == 0.0
        assert por_nome[nome].prazo_meses == 0
        assert por_nome[nome].viavel is False
        assert por_nome[nome].trade_offs == [
            "Sem sobra mensal positiva para aportar neste cenário."
        ]
    assert por_nome["acelerado"].aporte_mensal == 200.0
    assert por_nome["acelerado"].viavel is False


def test_cenarios_sem_sobra_e_sem_cortes_nao_dividem_por_zero():
    cenarios = gerar_cenarios(Capacidade(0.0, 2), 60000.0, 24, [], CATEGORIAS)
    assert all(c.aporte_mensal == 0.0 and c.prazo_meses == 0 for c in cenarios)
    assert not any(c.viavel for c in cenarios)


def test_cenarios_respeitam_regras_informadas():
    regras = RegrasCenario(pct_capacidade={"leve": 0.1, "forte": 0.9}, cortes_no_acelerado=False)
    cenarios = gerar_cenarios(Capacidade(1000.0, 2), 9000.0, 12, GASTOS, CATEGORIAS, regras)
    assert [(c.nome, c.aporte_mensal, c.prazo_meses) for c in cenarios] == [
        ("leve", 100.0, 90),
        ("forte", 900.0, 10),
    ]


def test_cenarios_rejeitam_prazo_invalido():
    with pytest.raises(ValueError):
        gerar_cenarios(Capacidade(1000.0, 2), 9000.0, 0, GASTOS, CATEGORIAS)
    with pytest.raises(ValueError):
        gerar_cenarios(Capacidade(1000.0, 2), -1.0, 12, GASTOS, CATEGORIAS)


# ---------------------------------------------------------------------------
# Oportunidades
# ---------------------------------------------------------------------------


def test_oportunidades_so_discricionarias_e_ordenadas():
    itens = rank_opportunities(GASTOS, CATEGORIAS, 2)
    assert [(o.micro, o.media_mensal, o.economia_potencial_mensal) for o in itens] == [
        ("Restaurantes", 500.0, 150.0),
        ("Bares", 100.0, 50.0),
    ]
    assert itens[0].criterio == opportunity_criterion(0.3)
    assert rank_opportunities(GASTOS, CATEGORIAS, 2, limit=1)[0].micro == "Restaurantes"
    # Média sobre os meses considerados, não sobre os meses com gasto.
    assert rank_opportunities(GASTOS, CATEGORIAS, 4)[0].media_mensal == 250.0


def test_oportunidades_rejeitam_meses_invalidos():
    with pytest.raises(ValueError):
        rank_opportunities(GASTOS, CATEGORIAS, 0)
    with pytest.raises(ValueError):
        rank_opportunities(GASTOS, CATEGORIAS, True)


# ---------------------------------------------------------------------------
# impacto_cortes
# ---------------------------------------------------------------------------


def test_cortes_por_micro():
    impacto = impacto_cortes(GASTOS, {"restaurantes": 0.5})
    assert impacto.economia_mensal == 250.0
    assert [(c.micro, c.valor_mensal) for c in impacto.itens] == [("Restaurantes", 250.0)]
    assert impacto.nao_encontradas == ()
    assert impacto.viavel is True and impacto.motivo is None


def test_cortes_por_macro_sem_acento_e_maior_fracao():
    impacto = impacto_cortes(GASTOS, {"Restaurantes": 0.2, "LAZER": 0.5, "alimentacao": 0.1})
    assert [(c.micro, c.valor_mensal) for c in impacto.itens] == [
        ("Restaurantes", 250.0),
        ("Bares", 50.0),
        ("Padaria", 10.0),
    ]
    assert impacto.economia_mensal == 310.0


def test_cortes_sem_casamento_voltam_na_ordem():
    impacto = impacto_cortes(GASTOS, {"Viagem": 0.5, "Moradia": 0.0, "Cinema": 0.3})
    assert impacto.nao_encontradas == ("Viagem", "Cinema")
    assert impacto.economia_mensal == 0.0
    assert impacto.viavel is False
    assert impacto.motivo == REASON_NO_SAVINGS


def test_cortes_sem_gastos_nao_dividem_por_zero():
    impacto = impacto_cortes([], {"Lazer": 0.5})
    assert impacto.viavel is False
    assert impacto.motivo == REASON_NO_SPENDING
    assert impacto.nao_encontradas == ("Lazer",)


def test_cortes_com_meses_informados():
    assert impacto_cortes(GASTOS, {"Restaurantes": 1.0}, 4).economia_mensal == 250.0


@pytest.mark.parametrize("fracao", [1.5, -0.1, math.nan, True])
def test_cortes_rejeitam_fracao_invalida(fracao):
    with pytest.raises(ValueError):
        impacto_cortes(GASTOS, {"Lazer": fracao})


def test_cortes_rejeitam_meses_invalidos():
    with pytest.raises(ValueError):
        impacto_cortes(GASTOS, {"Lazer": 0.5}, 0)


# ---------------------------------------------------------------------------
# impacto_dividas
# ---------------------------------------------------------------------------


def test_dividas_ordenadas_e_comprometimento():
    impacto = impacto_dividas([_parcela("b", 2, 10, 200.0), _parcela("a", 5, 5, 300.0)], 5000.0)
    assert [(p.descr, p.valor, p.meses_restantes) for p in impacto.parcelas_ativas] == [
        ("a", 300.0, 0),
        ("b", 200.0, 8),
    ]
    assert impacto.total_mensal == 500.0
    assert impacto.comprometimento_renda_pct == 10.0
    assert impacto.viavel is True and impacto.motivo is None


def test_dividas_sem_renda_nao_dividem_por_zero():
    impacto = impacto_dividas([_parcela("a", 1, 3, 100.0)], 0.0)
    assert impacto.comprometimento_renda_pct == 0.0
    assert impacto.viavel is False
    assert impacto.motivo == REASON_NO_INCOME


def test_dividas_sem_parcelas():
    impacto = impacto_dividas([], 5000.0)
    assert impacto.parcelas_ativas == ()
    assert impacto.total_mensal == 0.0
    assert impacto.comprometimento_renda_pct == 0.0
    assert impacto.viavel is True
    assert impacto.motivo == REASON_NO_INSTALLMENTS


@pytest.mark.parametrize("renda", [math.nan, math.inf, True, "5000"])
def test_dividas_rejeitam_renda_invalida(renda):
    with pytest.raises(ValueError):
        impacto_dividas([], renda)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def test_months_to_reach():
    assert months_to_reach(0.0, 100.0) == 0
    assert months_to_reach(-5.0, 0.0) == 0
    assert months_to_reach(1000.0, 100.0) == 10
    assert months_to_reach(1001.0, 100.0) == 11
    # 1,1 ÷ 0,1 = 11,000000000000002 em ponto flutuante: continua 11.
    assert months_to_reach(1.1, 0.1) == 11
    with pytest.raises(ValueError):
        months_to_reach(100.0, 0.0)


def test_estatisticas_com_duas_casas():
    assert mean_brl([1.0, 2.0, 2.0]) == 1.67
    assert median_brl([1.0, 2.0, 10.0]) == 2.0
    assert median_brl([1.0, 2.0]) == 1.5
    with pytest.raises(ValueError):
        mean_brl([])
    with pytest.raises(ValueError):
        median_brl([])


def test_formatos_de_texto():
    assert format_months(1) == "1 mês"
    assert format_months(0) == "0 meses"
    assert format_months(24) == "24 meses"
    assert format_brl_whole(1250.4) == "R$ 1.250"
    assert format_brl_whole(1234567.6) == "R$ 1.234.568"
    assert format_brl_whole(-1250.0) == "-R$ 1.250"
    assert format_brl_whole(0.4) == "R$ 0"
    assert format_percent(0.3) == "30%"
    assert format_percent(0.8) == "80%"
    assert normalize_label("  Alimentação   Fora  ") == "alimentacao fora"
    assert normalize_label("LAZER") == normalize_label("lazer")
    assert opportunity_criterion(0.3) == (
        "Categoria discricionária: corte de até 30% da média mensal no período."
    )
