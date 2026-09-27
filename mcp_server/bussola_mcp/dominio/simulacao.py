"""Funções puras de simulação (contratos §4) e auxiliares de estatística e texto.

Tudo aqui é determinístico e sem I/O: as funções recebem números ou linhas de
tabela já lidas e devolvem valores imutáveis. Todo valor em BRL sai com 2 casas
(:func:`bussola_mcp.contratos.brl`). O LLM nunca calcula: ele só redige a partir
destes resultados (constituição I).

- Nomes fixados pelo contrato ficam em português (``prazo_para_meta``,
  ``ResultadoPrazo``...). Os auxiliares novos estão em inglês técnico.
- Os textos ao cliente (``motivo``, ``trade_offs``, ``criterio``) estão em pt-BR e
  são frases fixas parametrizadas.
- Entradas negativas, não finitas ou de tipo errado levantam ``ValueError``.
"""

import math
import statistics
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from bussola_mcp.contratos import (
    Categoria,
    Cenario,
    CorteSugerido,
    GastoCategoria,
    Oportunidade,
    Parcela,
    ParcelaAtiva,
    PerfilMes,
    RegrasCenario,
    brl,
)

MAX_TERM_MONTHS = 360
"""Maior prazo plausível, em meses (mesmo limite de ``EntradaSimularObjetivo``)."""

MAX_OPPORTUNITIES = 10
"""Oportunidades consideradas nos cortes do cenário acelerado (golden R-10)."""

REASON_TARGET_COVERED = "O saldo inicial já cobre o valor do objetivo."
REASON_NO_CONTRIBUTION = "Sem aporte mensal positivo, o objetivo não é atingido."
REASON_TERM_TOO_LONG = f"O prazo passa de {MAX_TERM_MONTHS} meses."
REASON_TERM_TOO_SHORT = "O prazo precisa ser de pelo menos 1 mês."
REASON_NO_SURPLUS = "A sobra mensal mediana não é positiva no período."
REASON_NO_SPENDING = "Sem gastos no período para calcular cortes."
REASON_NO_SAVINGS = "Nenhum corte informado gera economia no período."
REASON_NO_INCOME = "Renda média zerada no período; comprometimento não calculado."
REASON_NO_INSTALLMENTS = "Não há parcelas no mês de corte."


# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------


def _number(name: str, value: object, *, positive: bool = False) -> float:
    """``value`` como ``float`` finito e ≥ 0 (> 0 com ``positive``), senão ``ValueError``."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} deve ser numérico")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} deve ser finito")
    if number < 0 or (positive and number == 0):
        raise ValueError(f"{name} deve ser {'positivo' if positive else 'não negativo'}")
    return number


def _integer(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} deve ser inteiro")
    return value


# ---------------------------------------------------------------------------
# Auxiliares de estatística e texto
# ---------------------------------------------------------------------------


def mean_brl(values: Iterable[float]) -> float:
    """Média aritmética (``statistics.fmean``) com 2 casas. Vazio levanta ``ValueError``."""
    return brl(statistics.fmean(list(values)))


def median_brl(values: Iterable[float]) -> float:
    """Mediana com 2 casas. Vazio levanta ``ValueError``."""
    return brl(statistics.median(list(values)))


def months_to_reach(remaining: float, contribution: float) -> int:
    """Meses inteiros para acumular ``remaining`` com aporte mensal fixo, sem rendimento.

    ``remaining ≤ 0`` dá 0. O arredondamento a 9 casas antes do teto evita que um
    resíduo de ponto flutuante (ex.: 24,000000001) vire um mês a mais.
    """
    if remaining <= 0:
        return 0
    if contribution <= 0:
        raise ValueError("contribution deve ser positivo")
    return math.ceil(round(remaining / contribution, 9))


def format_months(quantity: int) -> str:
    """``1 mês`` ou ``N meses``."""
    return "1 mês" if quantity == 1 else f"{quantity} meses"


def format_brl_whole(value: float) -> str:
    """Reais sem centavos, com ponto de milhar: ``R$ 1.250`` ou ``-R$ 1.250``."""
    whole = round(value)
    text = f"{abs(whole):,}".replace(",", ".")
    return f"-R$ {text}" if whole < 0 else f"R$ {text}"


def format_percent(fraction: float) -> str:
    """Fração como percentual inteiro: ``0.3`` → ``30%``."""
    return f"{round(fraction * 100)}%"


def strip_accents(text: str) -> str:
    """Texto em ASCII, sem acento: decompõe em NFKD e descarta o que não é ASCII.

    Base única das chaves de comparação do domínio (rótulos de categoria em
    :func:`normalize_label`, tokens da busca fake). ``rag/text.py`` faz uma
    normalização diferente de propósito: lá o que não é ASCII é preservado.
    """
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def normalize_label(text: str) -> str:
    """Chave de rótulo sem acento, sem diferença de caixa e com espaços simples."""
    return " ".join(strip_accents(text).casefold().split())


def opportunity_criterion(corte_max_pct: float) -> str:
    """Frase fixa do critério de uma oportunidade de corte."""
    return (
        f"Categoria discricionária: corte de até {format_percent(corte_max_pct)} "
        "da média mensal no período."
    )


def _monthly_means(
    gastos: Iterable[GastoCategoria], meses_considerados: int
) -> dict[tuple[str, str], float]:
    """Média mensal por (macro, micro): total ÷ meses considerados, com 2 casas."""
    totals: dict[tuple[str, str], list[float]] = defaultdict(list)
    for gasto in gastos:
        totals[(gasto.macro, gasto.micro)].append(gasto.total)
    return {key: brl(math.fsum(values) / meses_considerados) for key, values in totals.items()}


def rank_opportunities(
    gastos: Iterable[GastoCategoria],
    categorias: Iterable[Categoria],
    meses_considerados: int,
    limit: int = MAX_OPPORTUNITIES,
) -> list[Oportunidade]:
    """Oportunidades de corte, só em categorias discricionárias.

    ``media_mensal`` = total ÷ meses considerados e ``economia_potencial_mensal`` =
    ``media_mensal × corte_max_pct``. Médias ≤ 0 ficam de fora. Ordem: maior economia,
    maior média, macro e micro. Devolve até ``limit`` itens.
    """
    meses = _integer("meses_considerados", meses_considerados)
    if meses < 1:
        raise ValueError("meses_considerados deve ser positivo")
    by_category = {(c.macro, c.micro): c for c in categorias}
    ranked: list[Oportunidade] = []
    for (macro, micro), media in _monthly_means(gastos, meses).items():
        categoria = by_category.get((macro, micro))
        if categoria is None or not categoria.discricionaria or media <= 0:
            continue
        ranked.append(
            Oportunidade(
                macro=macro,
                micro=micro,
                media_mensal=media,
                discricionaria=True,
                economia_potencial_mensal=brl(media * categoria.corte_max_pct),
                criterio=opportunity_criterion(categoria.corte_max_pct),
            )
        )
    ranked.sort(key=lambda o: (-o.economia_potencial_mensal, -o.media_mensal, o.macro, o.micro))
    return ranked[:limit]


# ---------------------------------------------------------------------------
# Resultados (imutáveis)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoPrazo:
    prazo_meses: int
    viavel: bool
    motivo: str | None = None


@dataclass(frozen=True)
class ResultadoAporte:
    aporte_mensal: float
    viavel: bool
    motivo: str | None = None


@dataclass(frozen=True)
class Capacidade:
    """Capacidade mensal de poupança: a sobra mediana dos meses considerados."""

    sobra_mediana: float
    meses_considerados: int

    @property
    def viavel(self) -> bool:
        return self.sobra_mediana > 0

    @property
    def motivo(self) -> str | None:
        return None if self.viavel else REASON_NO_SURPLUS

    @classmethod
    def from_profile(cls, meses: Sequence[PerfilMes]) -> "Capacidade":
        """Capacidade a partir das linhas de ``perfil_mensal`` já cortadas."""
        if not meses:
            raise ValueError("sem meses para calcular a capacidade")
        return cls(sobra_mediana=median_brl(p.sobra for p in meses), meses_considerados=len(meses))


@dataclass(frozen=True)
class ImpactoCortes:
    economia_mensal: float
    itens: tuple[CorteSugerido, ...]
    nao_encontradas: tuple[str, ...]
    viavel: bool
    motivo: str | None = None


@dataclass(frozen=True)
class ImpactoDividas:
    parcelas_ativas: tuple[ParcelaAtiva, ...]
    total_mensal: float
    comprometimento_renda_pct: float
    viavel: bool
    motivo: str | None = None


# ---------------------------------------------------------------------------
# Funções do contrato (§4)
# ---------------------------------------------------------------------------


def prazo_para_meta(
    valor_alvo: float,
    aporte_mensal: float,
    saldo_inicial: float = 0.0,
    rendimento_mensal: float = 0.0,
) -> ResultadoPrazo:
    """Meses para chegar a ``valor_alvo`` com aporte fixo no fim de cada mês.

    - ``saldo_inicial ≥ valor_alvo`` → prazo 0, viável;
    - sem aporte e sem crescimento possível → prazo 0, inviável, sem divisão;
    - sem rendimento: ``⌈(alvo − saldo) ÷ aporte⌉``;
    - com rendimento ``r``: menor ``n`` com ``S(1+r)ⁿ + A((1+r)ⁿ − 1)/r ≥ alvo``;
    - prazo acima de 360 → inviável, mas o prazo calculado volta.
    """
    alvo = _number("valor_alvo", valor_alvo, positive=True)
    aporte = _number("aporte_mensal", aporte_mensal)
    saldo = _number("saldo_inicial", saldo_inicial)
    taxa = _number("rendimento_mensal", rendimento_mensal)
    restante = alvo - saldo
    if restante <= 0:
        return ResultadoPrazo(prazo_meses=0, viavel=True, motivo=REASON_TARGET_COVERED)
    if taxa == 0:
        if aporte <= 0:
            return ResultadoPrazo(prazo_meses=0, viavel=False, motivo=REASON_NO_CONTRIBUTION)
        prazo = months_to_reach(restante, aporte)
    else:
        base = saldo + aporte / taxa
        if base <= 0:
            return ResultadoPrazo(prazo_meses=0, viavel=False, motivo=REASON_NO_CONTRIBUTION)
        ratio = (alvo + aporte / taxa) / base
        prazo = max(1, math.ceil(round(math.log(ratio) / math.log1p(taxa), 9)))
    if prazo > MAX_TERM_MONTHS:
        return ResultadoPrazo(prazo_meses=prazo, viavel=False, motivo=REASON_TERM_TOO_LONG)
    return ResultadoPrazo(prazo_meses=prazo, viavel=True)


def aporte_para_prazo(
    valor_alvo: float,
    prazo_meses: int,
    saldo_inicial: float = 0.0,
    rendimento_mensal: float = 0.0,
) -> ResultadoAporte:
    """Aporte mensal fixo (no fim de cada mês) para chegar a ``valor_alvo`` em ``prazo_meses``.

    - ``saldo_inicial ≥ valor_alvo`` → aporte 0, viável;
    - prazo < 1 → aporte 0, inviável;
    - sem rendimento: ``(alvo − saldo) ÷ prazo``;
    - com rendimento ``r``: ``(alvo − S(1+r)ⁿ) · r ÷ ((1+r)ⁿ − 1)``, mínimo 0;
    - prazo acima de 360 → o aporte volta, mas inviável.
    """
    alvo = _number("valor_alvo", valor_alvo, positive=True)
    prazo = _integer("prazo_meses", prazo_meses)
    saldo = _number("saldo_inicial", saldo_inicial)
    taxa = _number("rendimento_mensal", rendimento_mensal)
    restante = alvo - saldo
    if restante <= 0:
        return ResultadoAporte(aporte_mensal=0.0, viavel=True, motivo=REASON_TARGET_COVERED)
    if prazo < 1:
        return ResultadoAporte(aporte_mensal=0.0, viavel=False, motivo=REASON_TERM_TOO_SHORT)
    if taxa == 0:
        aporte = brl(restante / prazo)
    else:
        growth = math.pow(1 + taxa, prazo)
        aporte = brl(max(0.0, (alvo - saldo * growth) * taxa / (growth - 1)))
    if prazo > MAX_TERM_MONTHS:
        return ResultadoAporte(aporte_mensal=aporte, viavel=False, motivo=REASON_TERM_TOO_LONG)
    return ResultadoAporte(aporte_mensal=aporte, viavel=True)


def _trade_offs(
    prazo: int,
    prazo_desejado: int,
    aporte: float,
    pct: float,
    base: float,
    capacidade: float,
    cortes: Sequence[CorteSugerido],
) -> list[str]:
    frases: list[str] = []
    if aporte <= 0:
        frases.append("Sem sobra mensal positiva para aportar neste cenário.")
    elif prazo <= prazo_desejado:
        frases.append(
            f"Atinge a meta em {format_months(prazo)}, dentro do prazo de "
            f"{format_months(prazo_desejado)}."
        )
    else:
        frases.append(
            f"Precisa de {format_months(prazo)}, além do prazo de {format_months(prazo_desejado)}."
        )
    if capacidade > 0:
        frases.append(
            f"Compromete {format_percent(pct)} da sobra mensal mediana "
            f"({format_brl_whole(base)}/mês)."
        )
    for corte in cortes:
        frases.append(f"Exige reduzir {format_brl_whole(corte.valor_mensal)}/mês em {corte.micro}.")
    return frases


def gerar_cenarios(
    capacidade: Capacidade,
    valor_alvo: float,
    prazo_meses: int,
    gastos: Iterable[GastoCategoria],
    categorias: Iterable[Categoria],
    regras: RegrasCenario | None = None,
) -> list[Cenario]:
    """Cenários de :class:`RegrasCenario` sobre ``max(sobra_mediana, 0)``.

    - ``aporte = pct × capacidade``; no ``acelerado`` (com ``cortes_no_acelerado``)
      somam-se as economias das até 10 oportunidades discricionárias, que viram
      ``cortes_sugeridos``;
    - ``prazo`` vem de :func:`prazo_para_meta` com o saldo inicial e o rendimento das
      regras (0 e inviável sem aporte);
    - ``viavel = prazo ≤ prazo_meses``;
    - ``trade_offs`` são frases fixas. Nenhum percentual ou valor de cenário é fixo.
    """
    regras = regras if regras is not None else RegrasCenario()
    alvo = _number("valor_alvo", valor_alvo, positive=True)
    prazo_desejado = _integer("prazo_meses", prazo_meses)
    if prazo_desejado < 1:
        raise ValueError("prazo_meses deve ser positivo")
    sobra = capacidade.sobra_mediana
    oportunidades = rank_opportunities(
        gastos, categorias, capacidade.meses_considerados, limit=MAX_OPPORTUNITIES
    )
    cortes = [
        CorteSugerido(macro=o.macro, micro=o.micro, valor_mensal=o.economia_potencial_mensal)
        for o in oportunidades
        if o.economia_potencial_mensal > 0
    ]
    cenarios: list[Cenario] = []
    for nome, pct in regras.pct_capacidade.items():
        base = brl(pct * max(sobra, 0.0))
        do_cenario = cortes if nome == "acelerado" and regras.cortes_no_acelerado else []
        aporte = brl(base + math.fsum(c.valor_mensal for c in do_cenario))
        if aporte > 0:
            prazo = prazo_para_meta(
                alvo, aporte, regras.saldo_inicial, regras.rendimento_mensal
            ).prazo_meses
            viavel = prazo <= prazo_desejado
        else:
            prazo, viavel = 0, False
        cenarios.append(
            Cenario(
                nome=nome,
                pct_capacidade=pct,
                aporte_mensal=aporte,
                prazo_meses=prazo,
                viavel=viavel,
                cortes_sugeridos=list(do_cenario),
                trade_offs=_trade_offs(prazo, prazo_desejado, aporte, pct, base, sobra, do_cenario),
            )
        )
    return cenarios


def impacto_cortes(
    gastos: Iterable[GastoCategoria],
    cortes: Mapping[str, float],
    meses_considerados: int | None = None,
) -> ImpactoCortes:
    """Economia mensal de cortar frações de categorias de gasto.

    - As chaves de ``cortes`` casam com a micro ou, na falta, com a macro, sem acento e
      sem diferença de caixa. Os valores são frações de 0 a 1.
    - ``meses_considerados`` padrão = ``anomes`` distintos de ``gastos``.
    - Cada item vale ``brl(média mensal × fração)``. Se duas chaves casam a mesma
      categoria, vale a maior fração. Ordem: maior valor, macro e micro.
    - Chaves sem casamento voltam em ``nao_encontradas``, na ordem da entrada.
    """
    linhas = list(gastos)
    fracoes = {chave: _number(f"cortes[{chave!r}]", valor) for chave, valor in cortes.items()}
    if any(fracao > 1 for fracao in fracoes.values()):
        raise ValueError("as frações de corte devem ficar entre 0 e 1")
    if meses_considerados is None:
        meses = len({g.anomes for g in linhas})
    else:
        meses = _integer("meses_considerados", meses_considerados)
        if meses < 1:
            raise ValueError("meses_considerados deve ser positivo")
    if meses == 0:
        return ImpactoCortes(
            economia_mensal=0.0,
            itens=(),
            nao_encontradas=tuple(fracoes),
            viavel=False,
            motivo=REASON_NO_SPENDING,
        )
    medias = _monthly_means(linhas, meses)
    escolhidas: dict[tuple[str, str], float] = {}
    nao_encontradas: list[str] = []
    for chave, fracao in fracoes.items():
        alvo = normalize_label(chave)
        casadas = [k for k in medias if normalize_label(k[1]) == alvo] or [
            k for k in medias if normalize_label(k[0]) == alvo
        ]
        if not casadas:
            nao_encontradas.append(chave)
        for categoria in casadas:
            escolhidas[categoria] = max(fracao, escolhidas.get(categoria, 0.0))
    itens = sorted(
        (
            CorteSugerido(macro=macro, micro=micro, valor_mensal=valor)
            for (macro, micro), fracao in escolhidas.items()
            if (valor := brl(medias[(macro, micro)] * fracao)) > 0
        ),
        key=lambda c: (-c.valor_mensal, c.macro, c.micro),
    )
    economia = brl(math.fsum(c.valor_mensal for c in itens))
    return ImpactoCortes(
        economia_mensal=economia,
        itens=tuple(itens),
        nao_encontradas=tuple(nao_encontradas),
        viavel=economia > 0,
        motivo=None if economia > 0 else REASON_NO_SAVINGS,
    )


def impacto_dividas(parcelas: Iterable[Parcela], renda_media: float) -> ImpactoDividas:
    """Parcelas ativas e comprometimento da renda.

    Recebe as parcelas do mês de corte. ``meses_restantes = parcela_total −
    parcela_atual`` (mínimo 0). ``comprometimento_renda_pct`` = Σ parcelas ÷ renda média
    × 100, com 2 casas. Renda média ≤ 0 → 0 e inviável, com motivo.
    """
    if isinstance(renda_media, bool) or not isinstance(renda_media, int | float):
        raise ValueError("renda_media deve ser numérico")
    renda = float(renda_media)
    if not math.isfinite(renda):
        raise ValueError("renda_media deve ser finito")
    ativas = tuple(
        sorted(
            (
                ParcelaAtiva(
                    descr=p.descr,
                    parcela_atual=p.parcela_atual,
                    parcela_total=p.parcela_total,
                    valor=p.vlr,
                    meses_restantes=max(0, p.parcela_total - p.parcela_atual),
                )
                for p in parcelas
            ),
            key=lambda a: (-a.valor, a.descr, a.parcela_atual, a.parcela_total),
        )
    )
    total = math.fsum(a.valor for a in ativas)
    if renda <= 0:
        return ImpactoDividas(
            parcelas_ativas=ativas,
            total_mensal=brl(total),
            comprometimento_renda_pct=0.0,
            viavel=False,
            motivo=REASON_NO_INCOME,
        )
    return ImpactoDividas(
        parcelas_ativas=ativas,
        total_mensal=brl(total),
        comprometimento_renda_pct=brl(total / renda * 100),
        viavel=True,
        motivo=None if ativas else REASON_NO_INSTALLMENTS,
    )
