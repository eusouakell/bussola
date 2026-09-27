"""Métricas por ferramenta de dados (contratos §5) sobre um ``RepositorioFinanceiro``.

Cada função pública tem o nome da ferramenta do 003 e devolve um
:class:`MetricResult` com o ``dados`` exato do contrato, o período considerado e os
avisos determinísticos. As regras são as mesmas dos goldens de ``contracts/fixtures``:
o mesmo código gera as fixtures v1 (``build_dados.py --fixtures``) e responde em
produção.

Garantias:

- **Validação antes do repositório:** as entradas passam pelos modelos ``Entrada*`` do
  contrato. ``id_usuario`` sai validado como UUID v4 (em minúsculas) e ``ate_anomes``
  fica em 202501–202512. Qualquer violação levanta :class:`InvalidInputError`, sem
  ecoar o valor recebido.
- **Corte temporal e escopo (constituição III e IV):** além do filtro do repositório,
  toda linha é refiltrada por ``id_usuario`` e ``anomes <= ate_anomes``.
- **Sem I/O próprio:** só o repositório recebido é lido. Falhas dele (ex.:
  ``RepositoryUnavailableError``) sobem sem tradução.
"""

import math
import statistics
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from operator import attrgetter
from typing import Any, ClassVar, Protocol

from pydantic import BaseModel, ValidationError

from bussola_mcp.contratos import (
    FERRAMENTAS,
    MENSAGENS_ERRO,
    TABELAS_FERRAMENTA,
    CodigoErro,
    DadosCapacidadePoupanca,
    DadosCompararCenarios,
    DadosDividasParcelas,
    DadosOportunidadesCorte,
    DadosPerfilFinanceiro,
    DadosReferenciaCoorte,
    DadosResumoMes,
    DadosSimularObjetivo,
    EntradaCapacidadePoupanca,
    EntradaCompararCenarios,
    EntradaComum,
    EntradaDividasParcelas,
    EntradaOportunidadesCorte,
    EntradaPerfilFinanceiro,
    EntradaReferenciaCoorte,
    EntradaResumoMes,
    EntradaSimularObjetivo,
    FaixaRenda,
    Fonte,
    FonteRenda,
    GastoMacro,
    PerfilMes,
    Periodo,
    PontoMensal,
    RegrasCenario,
    Resposta,
    Saldo,
    brl,
    mensagem_entrada_invalida,
)
from bussola_mcp.dominio.interfaces import RepositorioFinanceiro
from bussola_mcp.dominio.simulacao import (
    MAX_TERM_MONTHS,
    REASON_NO_INCOME,
    REASON_NO_INSTALLMENTS,
    Capacidade,
    aporte_para_prazo,
    format_months,
    gerar_cenarios,
    impacto_dividas,
    mean_brl,
    median_brl,
    normalize_label,
    prazo_para_meta,
    rank_opportunities,
)

__all__ = [
    "COHORT_WARNING",
    "INCOME_BAND_LIMITS",
    "ImplausibleTermError",
    "InsufficientDataError",
    "InvalidInputError",
    "MetricError",
    "MetricResult",
    "build_envelope",
    "capacidade_poupanca",
    "comparar_cenarios",
    "dividas_e_parcelas",
    "income_band",
    "normalize_label",
    "oportunidades_corte",
    "perfil_financeiro",
    "referencia_coorte",
    "resumo_mes",
    "simular_objetivo",
]

INCOME_BAND_LIMITS: tuple[float, ...] = (3000.0, 6000.0, 10000.0, 20000.0)
"""Limites de renda média mensal entre as faixas de :class:`FaixaRenda` (mesmos do 000)."""

COHORT_WARNING = (
    "Referência agregada de 2025 de clientes da mesma faixa de renda, sem dado individual."
)
NO_REFERENCE_MESSAGE = "Sem referência da faixa de renda para esta categoria."
MONTH_UNAVAILABLE_MESSAGE = "Não há dados deste mês para o cliente."
NO_OPPORTUNITIES_WARNING = "Nenhuma categoria discricionária com gasto no período."
NO_SURPLUS_WARNING = "A sobra mensal mediana não é positiva no período."
CONTRIBUTION_ABOVE_SURPLUS_WARNING = "O aporte necessário supera a sobra mensal mediana."
SCENARIOS_NO_SURPLUS_WARNING = (
    "A sobra mensal mediana não é positiva no período; só cortes geram aporte."
)


# ---------------------------------------------------------------------------
# Resultado e erros
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricResult:
    """Resultado de uma métrica: ``dados`` do contrato, período e avisos."""

    dados: BaseModel
    periodo: Periodo
    avisos: tuple[str, ...] = ()


class MetricError(Exception):
    """Erro de domínio com ``codigo`` do contrato e ``mensagem`` em pt-BR."""

    default_code: ClassVar[CodigoErro | None] = None

    def __init__(self, mensagem: str | None = None, *, codigo: CodigoErro | None = None) -> None:
        resolved = codigo if codigo is not None else self.default_code
        if resolved is None:
            raise TypeError("MetricError exige um codigo")
        self.codigo = CodigoErro(resolved)
        self.mensagem = mensagem or MENSAGENS_ERRO[self.codigo]
        super().__init__(self.mensagem)


class InvalidInputError(MetricError, ValueError):
    default_code = CodigoErro.ENTRADA_INVALIDA


class InsufficientDataError(MetricError):
    default_code = CodigoErro.DADOS_INSUFICIENTES


class ImplausibleTermError(MetricError):
    default_code = CodigoErro.PRAZO_IMPLAUSIVEL


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


class _ClientRow(Protocol):
    id_usuario: str
    anomes: int


def _validate[I: EntradaComum](model: type[I], **fields: Any) -> I:
    """Valida com o modelo ``Entrada*`` do contrato, sem ecoar valores na mensagem."""
    try:
        return model.model_validate(fields)
    except ValidationError as exc:
        raise InvalidInputError(mensagem_entrada_invalida(exc)) from None


def _scoped[R: _ClientRow](rows: Iterable[R], id_usuario: str, ate_anomes: int) -> list[R]:
    """Linhas do cliente com ``anomes <= ate_anomes``, em ordem estável de ``anomes``."""
    return sorted(
        (r for r in rows if r.id_usuario.lower() == id_usuario and r.anomes <= ate_anomes),
        key=attrgetter("anomes"),
    )


def _months(repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
    meses = _scoped(repo.perfil_mensal(id_usuario, ate_anomes), id_usuario, ate_anomes)
    if not meses:
        raise InsufficientDataError()
    return meses


def _period(meses: list[PerfilMes], ate_anomes: int) -> Periodo:
    return Periodo(inicio=meses[0].anomes, fim=ate_anomes)


def income_band(renda_media: float) -> str:
    """Faixa de renda (:class:`FaixaRenda`) da renda média mensal, com limites 3k/6k/10k/20k."""
    if isinstance(renda_media, bool) or not isinstance(renda_media, int | float):
        raise ValueError("renda_media deve ser numérico")
    if not math.isfinite(renda_media):
        raise ValueError("renda_media deve ser finito")
    return list(FaixaRenda)[bisect_right(INCOME_BAND_LIMITS, float(renda_media))].value


def build_envelope(ferramenta: str, resultado: MetricResult) -> dict[str, Any]:
    """Envelope de sucesso ``Resposta[...]`` serializado em JSON, como nos goldens."""
    if ferramenta not in FERRAMENTAS:
        raise ValueError("ferramenta desconhecida")
    modelo = FERRAMENTAS[ferramenta][1]
    resposta = Resposta[modelo](
        dados=resultado.dados,
        fonte=Fonte(
            ferramenta=ferramenta,
            tabelas=list(TABELAS_FERRAMENTA[ferramenta]),
            periodo=resultado.periodo,
        ),
        avisos=list(resultado.avisos),
    )
    return resposta.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Métricas (uma por ferramenta de dados)
# ---------------------------------------------------------------------------


def perfil_financeiro(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int
) -> MetricResult:
    """Médias, mediana, fontes de renda, saldos e série mensal até o corte.

    ``fontes_renda`` = entradas por macro/micro com ``media`` = total ÷ meses considerados
    (maior primeiro). ``saldo.atual`` = ``saldo_final`` do último mês até o corte.
    """
    entrada = _validate(EntradaPerfilFinanceiro, id_usuario=id_usuario, ate_anomes=ate_anomes)
    uid, ate = entrada.id_usuario, entrada.ate_anomes
    meses = _months(repo, uid, ate)
    qtd = len(meses)
    por_fonte: dict[tuple[str, str], list[float]] = defaultdict(list)
    for linha in _scoped(repo.entradas_categoria(uid, ate), uid, ate):
        por_fonte[(linha.macro, linha.micro)].append(linha.total)
    fontes = sorted(
        (
            FonteRenda(macro=macro, micro=micro, media=brl(math.fsum(totais) / qtd))
            for (macro, micro), totais in por_fonte.items()
        ),
        key=lambda f: (-f.media, f.macro, f.micro),
    )
    dados = DadosPerfilFinanceiro(
        renda_media=mean_brl(p.renda for p in meses),
        gasto_medio=mean_brl(p.gasto for p in meses),
        sobra_media=mean_brl(p.sobra for p in meses),
        sobra_mediana=median_brl(p.sobra for p in meses),
        fontes_renda=fontes,
        saldo=Saldo(
            minimo=min(p.saldo_minimo for p in meses),
            maximo=max(p.saldo_maximo for p in meses),
            atual=meses[-1].saldo_final,
        ),
        serie_mensal=[
            PontoMensal(anomes=p.anomes, renda=p.renda, gasto=p.gasto, sobra=p.sobra) for p in meses
        ],
        meses_considerados=qtd,
    )
    negativos = sum(1 for p in meses if p.saldo_minimo < 0)
    avisos = (
        (f"Saldo ficou negativo em {format_months(negativos)} do período.",) if negativos else ()
    )
    return MetricResult(dados=dados, periodo=_period(meses, ate), avisos=avisos)


def capacidade_poupanca(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int
) -> MetricResult:
    """Sobra média, mediana, desvio padrão populacional e meses com sobra negativa."""
    entrada = _validate(EntradaCapacidadePoupanca, id_usuario=id_usuario, ate_anomes=ate_anomes)
    meses = _months(repo, entrada.id_usuario, entrada.ate_anomes)
    sobras = [p.sobra for p in meses]
    negativos = sum(1 for s in sobras if s < 0)
    dados = DadosCapacidadePoupanca(
        sobra_media=mean_brl(sobras),
        sobra_mediana=median_brl(sobras),
        desvio_padrao=brl(statistics.pstdev(sobras)),
        meses_negativos=negativos,
        meses_considerados=len(meses),
    )
    avisos = (
        (f"Gasto superou a renda em {format_months(negativos)} do período.",) if negativos else ()
    )
    return MetricResult(dados=dados, periodo=_period(meses, entrada.ate_anomes), avisos=avisos)


def oportunidades_corte(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int, top_n: int = 5
) -> MetricResult:
    """Até ``top_n`` categorias discricionárias com maior economia potencial mensal."""
    entrada = _validate(
        EntradaOportunidadesCorte, id_usuario=id_usuario, ate_anomes=ate_anomes, top_n=top_n
    )
    uid, ate = entrada.id_usuario, entrada.ate_anomes
    meses = _months(repo, uid, ate)
    gastos = _scoped(repo.gastos_categoria(uid, ate), uid, ate)
    itens = rank_opportunities(gastos, repo.categorias(), len(meses), limit=entrada.top_n)
    avisos = () if itens else (NO_OPPORTUNITIES_WARNING,)
    return MetricResult(
        dados=DadosOportunidadesCorte(categorias=itens),
        periodo=_period(meses, ate),
        avisos=avisos,
    )


def dividas_e_parcelas(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int
) -> MetricResult:
    """Parcelas lançadas no mês de corte, juros médios e comprometimento da renda (0–100)."""
    entrada = _validate(EntradaDividasParcelas, id_usuario=id_usuario, ate_anomes=ate_anomes)
    uid, ate = entrada.id_usuario, entrada.ate_anomes
    meses = _months(repo, uid, ate)
    do_mes = [p for p in _scoped(repo.parcelas(uid, ate), uid, ate) if p.anomes == ate]
    renda_media = mean_brl(p.renda for p in meses)
    impacto = impacto_dividas(do_mes, renda_media)
    avisos: list[str] = []
    if renda_media <= 0:
        avisos.append(REASON_NO_INCOME)
    if not impacto.parcelas_ativas:
        avisos.append(REASON_NO_INSTALLMENTS)
    dados = DadosDividasParcelas(
        parcelas_ativas=list(impacto.parcelas_ativas),
        juros_pagos_media=mean_brl(p.juros for p in meses),
        comprometimento_renda_pct=impacto.comprometimento_renda_pct,
    )
    return MetricResult(dados=dados, periodo=_period(meses, ate), avisos=tuple(avisos))


def simular_objetivo(
    repo: RepositorioFinanceiro,
    id_usuario: str,
    ate_anomes: int,
    valor_alvo: float,
    prazo_meses: int | None = None,
    aporte_mensal: float | None = None,
    usar_saldo_atual: bool = False,
) -> MetricResult:
    """Simulação sem rendimento sobre a sobra mediana dos meses considerados.

    - modo ``prazo``: aporte de :func:`aporte_para_prazo`;
    - modo ``aporte``: prazo de :func:`prazo_para_meta` (acima de 360 meses levanta
      :class:`ImplausibleTermError`);
    - ``saldo_inicial`` = 0, ou ``saldo_final`` do último mês (mínimo 0) com
      ``usar_saldo_atual``;
    - ``folga_mensal = sobra_mediana − aporte``; ``viavel`` = sobra mediana positiva e
      folga ≥ 0.
    """
    entrada = _validate(
        EntradaSimularObjetivo,
        id_usuario=id_usuario,
        ate_anomes=ate_anomes,
        valor_alvo=valor_alvo,
        prazo_meses=prazo_meses,
        aporte_mensal=aporte_mensal,
        usar_saldo_atual=usar_saldo_atual,
    )
    meses = _months(repo, entrada.id_usuario, entrada.ate_anomes)
    capacidade = Capacidade.from_profile(meses).sobra_mediana
    saldo_inicial = brl(max(0.0, meses[-1].saldo_final)) if entrada.usar_saldo_atual else 0.0
    if entrada.prazo_meses is not None:
        modo = "prazo"
        prazo = entrada.prazo_meses
        aporte = aporte_para_prazo(entrada.valor_alvo, prazo, saldo_inicial).aporte_mensal
    else:
        modo = "aporte"
        aporte_informado = float(entrada.aporte_mensal or 0.0)
        aporte = brl(aporte_informado)
        prazo = prazo_para_meta(entrada.valor_alvo, aporte_informado, saldo_inicial).prazo_meses
        if prazo > MAX_TERM_MONTHS:
            raise ImplausibleTermError()
    folga = brl(capacidade - aporte)
    viavel = capacidade > 0 and folga >= 0
    avisos: tuple[str, ...] = ()
    if capacidade <= 0:
        avisos = (NO_SURPLUS_WARNING,)
    elif not viavel:
        avisos = (CONTRIBUTION_ABOVE_SURPLUS_WARNING,)
    dados = DadosSimularObjetivo(
        modo=modo,
        valor_alvo=brl(entrada.valor_alvo),
        aporte_mensal=aporte,
        prazo_meses=prazo,
        viavel=viavel,
        folga_mensal=folga,
        premissas={
            "base_capacidade": "sobra_mediana",
            "capacidade_mensal": capacidade,
            "meses_considerados": len(meses),
            "rendimento_mensal": 0.0,
            "saldo_inicial": saldo_inicial,
            "usar_saldo_atual": entrada.usar_saldo_atual,
        },
    )
    return MetricResult(dados=dados, periodo=_period(meses, entrada.ate_anomes), avisos=avisos)


def comparar_cenarios(
    repo: RepositorioFinanceiro,
    id_usuario: str,
    ate_anomes: int,
    valor_alvo: float,
    prazo_meses: int,
    regras: RegrasCenario | None = None,
) -> MetricResult:
    """Cenários de :class:`RegrasCenario` (padrão: 40/60/80% da sobra mediana).

    O cenário acelerado soma os cortes das até 10 oportunidades discricionárias.
    """
    entrada = _validate(
        EntradaCompararCenarios,
        id_usuario=id_usuario,
        ate_anomes=ate_anomes,
        valor_alvo=valor_alvo,
        prazo_meses=prazo_meses,
    )
    uid, ate = entrada.id_usuario, entrada.ate_anomes
    regras = regras if regras is not None else RegrasCenario()
    meses = _months(repo, uid, ate)
    gastos = _scoped(repo.gastos_categoria(uid, ate), uid, ate)
    capacidade = Capacidade.from_profile(meses)
    try:
        cenarios = gerar_cenarios(
            capacidade, entrada.valor_alvo, entrada.prazo_meses, gastos, repo.categorias(), regras
        )
    except ValueError:
        raise InvalidInputError() from None
    avisos = () if capacidade.viavel else (SCENARIOS_NO_SURPLUS_WARNING,)
    return MetricResult(
        dados=DadosCompararCenarios(cenarios=cenarios, regras=regras),
        periodo=_period(meses, ate),
        avisos=avisos,
    )


def resumo_mes(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int, anomes: int
) -> MetricResult:
    """Renda, gasto e sobra de um mês (``anomes <= ate_anomes``) e gastos por macro."""
    entrada = _validate(
        EntradaResumoMes, id_usuario=id_usuario, ate_anomes=ate_anomes, anomes=anomes
    )
    uid, ate, mes = entrada.id_usuario, entrada.ate_anomes, entrada.anomes
    perfil = next(
        (p for p in _scoped(repo.perfil_mensal(uid, ate), uid, ate) if p.anomes == mes), None
    )
    if perfil is None:
        raise InsufficientDataError(MONTH_UNAVAILABLE_MESSAGE)
    por_macro: dict[str, list[float]] = defaultdict(list)
    for gasto in _scoped(repo.gastos_categoria(uid, ate, desde_anomes=mes), uid, ate):
        if gasto.anomes == mes:
            por_macro[gasto.macro].append(gasto.total)
    gastos_macro = sorted(
        (GastoMacro(macro=macro, total=brl(math.fsum(t))) for macro, t in por_macro.items()),
        key=lambda g: (-g.total, g.macro),
    )
    avisos: list[str] = []
    if perfil.saldo_minimo < 0:
        avisos.append("Saldo ficou negativo neste mês.")
    if perfil.sobra < 0:
        avisos.append("Gasto superou a renda neste mês.")
    dados = DadosResumoMes(
        anomes=mes,
        renda=perfil.renda,
        gasto=perfil.gasto,
        sobra=perfil.sobra,
        gastos_macro=gastos_macro,
    )
    return MetricResult(dados=dados, periodo=Periodo(inicio=mes, fim=mes), avisos=tuple(avisos))


def referencia_coorte(
    repo: RepositorioFinanceiro, id_usuario: str, ate_anomes: int, categoria: str
) -> MetricResult:
    """Média e mediana agregadas da faixa de renda do cliente para uma macro (P1).

    A faixa sai da renda média dos meses até o corte (:func:`income_band`). A
    ``categoria`` casa com a macro sem acento e sem diferença de caixa.
    """
    entrada = _validate(
        EntradaReferenciaCoorte, id_usuario=id_usuario, ate_anomes=ate_anomes, categoria=categoria
    )
    uid, ate = entrada.id_usuario, entrada.ate_anomes
    meses = _months(repo, uid, ate)
    faixa = income_band(statistics.fmean(p.renda for p in meses))
    alvo = normalize_label(entrada.categoria)
    linhas = sorted(
        (
            ref
            for ref in repo.referencia_coorte(faixa)
            if ref.faixa_renda == faixa and normalize_label(ref.macro) == alvo
        ),
        key=attrgetter("macro"),
    )
    if not linhas:
        raise InsufficientDataError(NO_REFERENCE_MESSAGE)
    ref = linhas[0]
    dados = DadosReferenciaCoorte(
        faixa_renda=ref.faixa_renda,
        macro=ref.macro,
        media=brl(ref.media),
        mediana=brl(ref.mediana),
        qtd_usuarios=ref.qtd_usuarios,
    )
    return MetricResult(dados=dados, periodo=_period(meses, ate), avisos=(COHORT_WARNING,))
