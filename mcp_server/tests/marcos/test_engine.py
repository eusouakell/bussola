"""Engine de marcos financeiros (ciclo 009, FR-001 a FR-024).

Funções puras: cada caso monta o :class:`ContextoFinanceiro` que quer, sem I/O.
Os casos com o cliente-âncora usam ``RepositorioFake`` só para provar que
``contexto_de_perfil`` lê as fixtures corretamente.
"""

import pytest

from bussola_mcp.contratos import (
    ID_ANCORA,
    CodigoMotivo,
    ContextoFinanceiro,
    RegrasMarco,
    TipoMarco,
)
from bussola_mcp.dominio import marcos
from bussola_mcp.dominio.fakes import RepositorioFake

REGRAS = RegrasMarco()

# Perfil saudável: sobra alta, sem dívida, reserva formada, saldo positivo.
SAUDAVEL = {
    "renda_media": 10000.0,
    "gasto_medio": 5000.0,
    "sobra_media": 5000.0,
    "sobra_mediana": 5000.0,
    "meses_negativos": 0,
    "meses_considerados": 12,
    "saldo_atual": 60000.0,
    "recursos_disponiveis": 60000.0,
    "juros_pagos_media": 0.0,
    "parcelas_mensais": 0.0,
    "comprometimento_renda_pct": 0.0,
    "meses_ate_fim_parcela": None,
    "dados_ausentes": ["PATRIMONIO", "INVESTIMENTOS"],
}


def contexto(**mudancas: object) -> ContextoFinanceiro:
    return ContextoFinanceiro(**{**SAUDAVEL, **mudancas})  # type: ignore[arg-type]


def codigos(plano) -> set[str]:
    return {m.codigo.value for m in plano.motivos}


# ---------------------------------------------------------------------------
# Aritmética (R1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("falta", "aporte", "esperado"),
    [
        (0.0, 100.0, 0),
        (-5.0, 100.0, 0),
        (1000.0, 0.0, None),
        (1000.0, -1.0, None),
        (1000.0, 300.0, 4),
    ],
)
def test_meses_para(falta: float, aporte: float, esperado: int | None) -> None:
    assert marcos.meses_para(falta, aporte) == esperado


def test_aporte_para_arredonda_em_2_casas() -> None:
    assert marcos.aporte_para(1000.0, 3) == 333.33
    assert marcos.aporte_para(-10.0, 3) == 0.0


# ---------------------------------------------------------------------------
# Contexto a partir das linhas do repositório (FR-003)
# ---------------------------------------------------------------------------


def test_contexto_do_ancora_bate_com_os_valores_de_referencia() -> None:
    """Contratos §8: renda ≈ 7.451, gasto ≈ 4.615, juros ≈ 61 (tolerância de 1%)."""
    repo = RepositorioFake()
    ctx = marcos.contexto_de_perfil(
        repo.perfil_mensal(ID_ANCORA, 202512), repo.parcelas(ID_ANCORA, 202512), REGRAS
    )
    assert ctx.renda_media == pytest.approx(7451.0, rel=0.01)
    assert ctx.gasto_medio == pytest.approx(4615.0, rel=0.01)
    assert ctx.juros_pagos_media == pytest.approx(61.0, rel=0.02)
    assert ctx.meses_considerados == 12
    assert ctx.meses_negativos == 1
    assert ctx.saldo_atual == pytest.approx(47597.68, rel=0.001)
    assert ctx.recursos_disponiveis == ctx.saldo_atual
    assert ctx.parcelas_mensais == pytest.approx(109.62, rel=0.01)
    assert ctx.comprometimento_renda_pct < 2.0
    assert ctx.meses_ate_fim_parcela == 0
    assert ctx.dados_ausentes == ["PATRIMONIO", "INVESTIMENTOS"]


def test_contexto_sem_saldo_atual_zera_recursos_e_marca_reserva_ausente() -> None:
    repo = RepositorioFake()
    regras = RegrasMarco(usar_saldo_atual=False)
    ctx = marcos.contexto_de_perfil(
        repo.perfil_mensal(ID_ANCORA, 202512), repo.parcelas(ID_ANCORA, 202512), regras
    )
    assert ctx.recursos_disponiveis == 0.0
    assert "RESERVA" in ctx.dados_ausentes


def test_contexto_de_periodo_vazio() -> None:
    ctx = marcos.contexto_de_perfil([], [], REGRAS)
    assert ctx.meses_considerados == 0
    assert ctx.renda_media == 0.0
    assert ctx.comprometimento_renda_pct == 0.0


# ---------------------------------------------------------------------------
# Motivos: um caso por gatilho (FR-001, AC-01)
# ---------------------------------------------------------------------------


def test_objetivo_que_cabe_nao_gera_motivo_nem_marco() -> None:
    """AC-02: objetivo que cabe e perfil sem gatilho estrutural."""
    plano = marcos.planejar(valor_alvo=80000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    assert plano.motivos == []
    assert plano.marcos == []
    assert plano.proximo is None
    assert plano.trajetoria_incerta is False
    assert plano.ressalvas == []


def test_motivo_prazo_nao_cabe_e_premissa_irrealista() -> None:
    plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    assert CodigoMotivo.PRAZO_NAO_CABE in [m.codigo for m in plano.motivos]
    assert CodigoMotivo.PREMISSA_IRREALISTA in [m.codigo for m in plano.motivos]
    assert plano.marcos
    motivo = next(m for m in plano.motivos if m.codigo is CodigoMotivo.PRAZO_NAO_CABE)
    assert motivo.observado == plano.aporte_necessario
    assert motivo.limite == plano.capacidade_sustentavel


def test_motivo_capacidade_insuficiente() -> None:
    plano = marcos.planejar(
        valor_alvo=20000.0,
        prazo_meses=24,
        contexto=contexto(sobra_media=-100.0, sobra_mediana=-100.0),
        regras=REGRAS,
    )
    assert CodigoMotivo.CAPACIDADE_INSUFICIENTE in [m.codigo for m in plano.motivos]
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.EQUILIBRAR_FLUXO


def test_motivo_risco_excessivo_por_meses_negativos() -> None:
    plano = marcos.planejar(
        valor_alvo=20000.0,
        prazo_meses=24,
        contexto=contexto(meses_negativos=6, meses_considerados=12),
        regras=REGRAS,
    )
    assert CodigoMotivo.RISCO_EXCESSIVO in [m.codigo for m in plano.motivos]
    assert plano.proximo is not None
    assert plano.proximo.nivel == 1


def test_um_mes_negativo_em_doze_nao_acende_risco() -> None:
    """O âncora tem 1 mês negativo em 12: não é fluxo de caixa frágil."""
    plano = marcos.planejar(
        valor_alvo=80000.0,
        prazo_meses=24,
        contexto=contexto(meses_negativos=1, meses_considerados=12),
        regras=REGRAS,
    )
    assert plano.motivos == []


def test_motivo_risco_excessivo_por_saldo_negativo() -> None:
    plano = marcos.planejar(
        valor_alvo=20000.0,
        prazo_meses=24,
        contexto=contexto(saldo_atual=-1500.0, recursos_disponiveis=0.0),
        regras=REGRAS,
    )
    assert CodigoMotivo.RISCO_EXCESSIVO in [m.codigo for m in plano.motivos]


@pytest.mark.parametrize(
    "mudancas",
    [
        {"juros_pagos_media": 120.0},  # 1,2% da renda
        {"parcelas_mensais": 4000.0, "comprometimento_renda_pct": 40.0},
    ],
)
def test_motivo_divida_a_resolver(mudancas: dict[str, float]) -> None:
    plano = marcos.planejar(
        valor_alvo=80000.0, prazo_meses=24, contexto=contexto(**mudancas), regras=REGRAS
    )
    assert CodigoMotivo.DIVIDA_A_RESOLVER in [m.codigo for m in plano.motivos]
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.REDUZIR_DIVIDA_CARA


def test_juros_abaixo_do_piso_nao_acende_divida() -> None:
    """Q-009-2: R$ 61 de juros sobre renda de R$ 7.451 (0,8%) não é dívida cara."""
    plano = marcos.planejar(
        valor_alvo=80000.0,
        prazo_meses=24,
        contexto=contexto(renda_media=7451.0, juros_pagos_media=61.0),
        regras=REGRAS,
    )
    assert CodigoMotivo.DIVIDA_A_RESOLVER not in [m.codigo for m in plano.motivos]


def test_motivo_sem_reserva() -> None:
    plano = marcos.planejar(
        valor_alvo=80000.0,
        prazo_meses=24,
        contexto=contexto(saldo_atual=2000.0, recursos_disponiveis=2000.0),
        regras=REGRAS,
    )
    assert CodigoMotivo.SEM_RESERVA in [m.codigo for m in plano.motivos]
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.FORMAR_RESERVA


def test_motivo_valor_distante_dos_recursos() -> None:
    plano = marcos.planejar(
        valor_alvo=1000000.0, prazo_meses=120, contexto=contexto(), regras=REGRAS
    )
    assert CodigoMotivo.VALOR_DISTANTE_DOS_RECURSOS in [m.codigo for m in plano.motivos]


def test_motivo_renda_nao_sustenta() -> None:
    plano = marcos.planejar(valor_alvo=200000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    motivo = next(m for m in plano.motivos if m.codigo is CodigoMotivo.RENDA_NAO_SUSTENTA)
    assert motivo.limite == pytest.approx(3000.0)  # 30% de 10.000


def test_todos_os_oito_motivos_tem_caso_coberto() -> None:
    """Guarda: nenhum código novo entra sem teste."""
    assert len(CodigoMotivo) == 8


# ---------------------------------------------------------------------------
# Prioridade (FR-008, FR-009, AC-03 a AC-05, AC-13)
# ---------------------------------------------------------------------------


def test_divida_cara_vem_antes_de_reserva_e_de_patrimonio() -> None:
    """AC-03: nível 1 antes de qualquer nível posterior."""
    plano = marcos.planejar(
        valor_alvo=300000.0,
        prazo_meses=24,
        contexto=contexto(
            renda_media=4000.0,
            gasto_medio=3500.0,
            sobra_media=300.0,
            sobra_mediana=300.0,
            saldo_atual=1200.0,
            recursos_disponiveis=1200.0,
            parcelas_mensais=1600.0,
            comprometimento_renda_pct=40.0,
            juros_pagos_media=90.0,
            meses_ate_fim_parcela=8,
        ),
        regras=REGRAS,
    )
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.REDUZIR_DIVIDA_CARA
    assert plano.proximo.nivel == 1
    assert plano.proximo.ordem == 1
    assert CodigoMotivo.SEM_RESERVA in [m.codigo for m in plano.motivos]


def test_sem_divida_e_sem_reserva_o_proximo_e_formar_reserva() -> None:
    """AC-04."""
    plano = marcos.planejar(
        valor_alvo=300000.0,
        prazo_meses=24,
        contexto=contexto(saldo_atual=3000.0, recursos_disponiveis=3000.0),
        regras=REGRAS,
    )
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.FORMAR_RESERVA
    assert plano.proximo.valor_alvo is not None
    assert plano.proximo.prazo_meses is not None


def test_sem_gatilho_de_nivel_1_e_2_o_proximo_e_de_acumulacao() -> None:
    """AC-05: reserva formada e sem dívida ⇒ nível 3."""
    plano = marcos.planejar(
        valor_alvo=1000000.0, prazo_meses=120, contexto=contexto(), regras=REGRAS
    )
    assert plano.proximo is not None
    assert plano.proximo.nivel == 3
    assert plano.proximo.tipo in {TipoMarco.ACUMULAR_PARTE_DA_META, TipoMarco.AUMENTAR_CAPACIDADE}


def test_so_nivel_4_aceso_o_proximo_e_ajustar_prazo() -> None:
    """AC-05, ressalva: sem gatilho de 1, 2 ou 3, sobra o ajuste de prazo."""
    plano = marcos.planejar(
        valor_alvo=200000.0,
        prazo_meses=24,
        contexto=contexto(renda_media=60000.0, sobra_media=5000.0, sobra_mediana=5000.0),
        regras=REGRAS,
    )
    assert {m.codigo for m in plano.motivos} == {
        CodigoMotivo.PRAZO_NAO_CABE,
        CodigoMotivo.PREMISSA_IRREALISTA,
    }
    assert plano.proximo is not None
    assert plano.proximo.tipo is TipoMarco.AJUSTAR_PRAZO
    assert plano.proximo.prazo_meses is not None and plano.proximo.prazo_meses > 24


def test_perfis_diferentes_com_o_mesmo_objetivo_recebem_marcos_diferentes() -> None:
    """AC-13."""
    endividado = contexto(
        renda_media=4000.0,
        gasto_medio=3500.0,
        sobra_media=300.0,
        sobra_mediana=300.0,
        saldo_atual=500.0,
        recursos_disponiveis=500.0,
        parcelas_mensais=1600.0,
        comprometimento_renda_pct=40.0,
        meses_ate_fim_parcela=8,
    )
    a = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=endividado, regras=REGRAS)
    b = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    assert a.proximo is not None and b.proximo is not None
    assert a.proximo.tipo is not b.proximo.tipo


def test_reserva_com_alvo_parcial_quando_o_prazo_nao_cabe() -> None:
    """FR-021/Q-009-1: alvo de 3× gasto médio, parcial de 1× quando não cabe no horizonte."""
    magro = contexto(
        renda_media=4000.0,
        gasto_medio=3000.0,
        sobra_media=250.0,
        sobra_mediana=250.0,
        saldo_atual=0.0,
        recursos_disponiveis=0.0,
    )
    plano = marcos.planejar(valor_alvo=50000.0, prazo_meses=12, contexto=magro, regras=REGRAS)
    reservas = [m for m in plano.marcos if m.tipo is TipoMarco.FORMAR_RESERVA]
    assert reservas
    assert reservas[0].valor_alvo == pytest.approx(3000.0)  # 1× gasto médio
    assert "parcial" in reservas[0].titulo.lower() or "primeira" in reservas[0].titulo.lower()


def test_trajetoria_respeita_o_maximo_e_a_ordem_sequencial() -> None:
    plano = marcos.planejar(
        valor_alvo=300000.0,
        prazo_meses=24,
        contexto=contexto(
            renda_media=4000.0,
            gasto_medio=3000.0,
            sobra_media=-50.0,
            sobra_mediana=-50.0,
            meses_negativos=6,
            saldo_atual=-200.0,
            recursos_disponiveis=0.0,
            parcelas_mensais=1600.0,
            comprometimento_renda_pct=40.0,
            meses_ate_fim_parcela=5,
        ),
        regras=RegrasMarco(fator_desnivel_incerto=1e9),
    )
    assert len(plano.marcos) <= REGRAS.max_marcos
    assert [m.ordem for m in plano.marcos] == list(range(1, len(plano.marcos) + 1))
    assert [m.nivel for m in plano.marcos] == sorted(m.nivel for m in plano.marcos)


# ---------------------------------------------------------------------------
# Trajetória incerta, ressalvas e proibições (FR-010, FR-011, FR-024)
# ---------------------------------------------------------------------------


def test_desnivel_grande_marca_trajetoria_incerta_e_devolve_so_o_proximo() -> None:
    """AC-07 e FR-024."""
    plano = marcos.planejar(
        valor_alvo=5000000.0, prazo_meses=12, contexto=contexto(), regras=REGRAS
    )
    assert plano.trajetoria_incerta is True
    assert len(plano.marcos) == 1
    assert plano.proximo == plano.marcos[0]
    assert any("não garante" in r for r in plano.ressalvas)
    assert any("responsável" in r for r in plano.ressalvas)


def test_ressalva_de_nao_garantia_sempre_que_ha_marco() -> None:
    plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    assert plano.marcos
    assert any("não garante o objetivo final" in r for r in plano.ressalvas)
    assert any("decisão" in r.lower() for r in plano.ressalvas)


TERMOS_PROIBIDOS = (
    "inviável",
    "inviavel",
    "impossível",
    "impossivel",
    "nunca",
    "desista",
    "abandone",
    "mais barato",
    "aumento de renda",
    "renda maior",
    "empréstimo",
    "emprestimo",
    "financiamento",
    "com certeza",
    "garantido",
    "garantimos",
    "vai conseguir",
)

CASOS_DE_TEXTO = [
    (80000.0, 24, {}),
    (300000.0, 24, {}),
    (5000000.0, 12, {}),
    (300000.0, 24, {"sobra_media": -100.0, "sobra_mediana": -100.0, "meses_negativos": 8}),
    (300000.0, 24, {"parcelas_mensais": 4000.0, "comprometimento_renda_pct": 40.0}),
    (300000.0, 24, {"saldo_atual": 1000.0, "recursos_disponiveis": 1000.0}),
    (200000.0, 24, {"renda_media": 60000.0}),
    (1000000.0, 120, {}),
]


def frases(plano) -> list[str]:
    saida = [*plano.ressalvas, *(m.explicacao for m in plano.motivos)]
    for marco in plano.marcos:
        saida += [marco.titulo, marco.indicador, marco.por_que, marco.relacao_com_objetivo]
    return saida


@pytest.mark.parametrize(("valor", "prazo", "mudancas"), CASOS_DE_TEXTO)
def test_nenhuma_frase_usa_termo_proibido(
    valor: float, prazo: int, mudancas: dict[str, float]
) -> None:
    """AC-08: as nove proibições da fonte, varridas em todas as frases geradas."""
    plano = marcos.planejar(
        valor_alvo=valor, prazo_meses=prazo, contexto=contexto(**mudancas), regras=REGRAS
    )
    for frase in frases(plano):
        baixa = frase.lower()
        for termo in TERMOS_PROIBIDOS:
            assert termo not in baixa, f"{termo!r} em {frase!r}"


@pytest.mark.parametrize(("valor", "prazo", "mudancas"), CASOS_DE_TEXTO)
def test_todo_marco_tem_indicador_e_valor_ou_prazo(
    valor: float, prazo: int, mudancas: dict[str, float]
) -> None:
    """AC-06."""
    plano = marcos.planejar(
        valor_alvo=valor, prazo_meses=prazo, contexto=contexto(**mudancas), regras=REGRAS
    )
    for marco in plano.marcos:
        assert marco.indicador.strip()
        assert marco.valor_alvo is not None or marco.prazo_meses is not None
        for numero in (marco.valor_alvo, marco.aporte_mensal):
            if numero is not None:
                assert round(numero, 2) == numero
        if marco.prazo_meses is not None:
            assert isinstance(marco.prazo_meses, int)
            assert 1 <= marco.prazo_meses <= REGRAS.prazo_maximo_marco


def test_avisos_declaram_dado_ausente_e_premissas() -> None:
    """AC-09 e FR-004."""
    plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=contexto(), regras=REGRAS)
    avisos = marcos.avisos_do_plano(contexto(), REGRAS, plano)
    assert any("patrimônio" in a.lower() for a in avisos)
    assert any("rendimento" in a.lower() for a in avisos)
    assert any("saldo atual" in a.lower() for a in avisos)
    assert any("não garante" in a for a in avisos)


def test_aviso_de_saldo_negativo() -> None:
    ctx = contexto(saldo_atual=-1500.0, recursos_disponiveis=0.0)
    plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=ctx, regras=REGRAS)
    avisos = marcos.avisos_do_plano(ctx, REGRAS, plano)
    assert any("negativo" in a.lower() for a in avisos)


def test_aviso_de_renda_zero() -> None:
    ctx = contexto(renda_media=0.0)
    plano = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=ctx, regras=REGRAS)
    avisos = marcos.avisos_do_plano(ctx, REGRAS, plano)
    assert any("renda média zero" in a.lower() for a in avisos)


# ---------------------------------------------------------------------------
# Determinismo (FR-018, AC-06)
# ---------------------------------------------------------------------------


def test_mesma_entrada_mesma_saida() -> None:
    ctx = contexto(saldo_atual=1200.0, recursos_disponiveis=1200.0, parcelas_mensais=3500.0)
    a = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=ctx, regras=REGRAS)
    b = marcos.planejar(valor_alvo=300000.0, prazo_meses=24, contexto=ctx, regras=REGRAS)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_engine_nao_usa_hora_nem_aleatoriedade() -> None:
    fonte = marcos.__file__
    with open(fonte, encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    for proibido in ("datetime", "random", "time.time", "uuid"):
        assert proibido not in codigo
