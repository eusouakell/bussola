"""Gera as fixtures provisórias de ``contracts/fixtures/`` (contratos §8; FR-015, FR-016).

Fluxo:

1. três consultas **parametrizadas** em ``hackathon_dados.extrato_sintetico`` (só leitura):
   o extrato de 2025 dos 2 usuários de fixture, os pares macro/micro do catálogo e um
   agregado anônimo por usuário para ``referencia_coorte``;
2. funções **puras** de referência (sem I/O) montam as linhas das 7 tabelas de
   ``bussola_dados``, os golden P0 dos dois cortes, ``resumo_mes__AAAAMM`` e os trechos RAG;
3. tudo é validado com os modelos de ``bussola_mcp.contratos`` e gravado em JSON
   determinístico (chaves ordenadas, indentação 2, UTF-8, ``ensure_ascii=False``).

As fixtures são **provisórias** (contratos §8): o 001 as regenera a partir das tabelas
oficiais. O contrato não tem campo para essa marca; ela fica registrada aqui e no PR.

Uso, com ADC (``gcloud auth application-default login``)::

    cd mcp_server && uv run python ../data/scripts/gerar_fixtures.py --saida ../contracts/fixtures

Leituras adotadas onde o 001 (§3.1/§3.4) é ambíguo (a mais simples em cada caso):

- empates de ``anomesdia`` seguem a cadeia de ``saldo_apos`` (saldo antes = ``saldo_apos``
  menos o valor com sinal); sem encaixe, vale a ordem estável ``tipo, descr, vlr, saldo_apos``;
- ``recorrentes`` considera só saídas, e a recorrência (≥ 3 meses) é medida no ano todo;
- ``parcelas`` inclui todo lançamento com ``parcela_total > 1``, sem filtro de ``tipo``;
- ``categorias`` usa palavras-chave sobre a micro (e depois a macro), com uma lista de
  essenciais que nunca são discricionárias; o seed revisado do 001 substitui essa regra;
- ``referencia_coorte`` usa, por faixa × macro, os usuários com gasto na macro e só publica
  grupos com pelo menos :data:`QTD_MIN_COORTE` usuários;
- as regras de cada golden estão nas docstrings das funções ``golden_*``.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
import unicodedata
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from itertools import groupby
from operator import attrgetter
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bussola_mcp.contratos import (
    ANOMES_MAX,
    ANOMES_MIN,
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS,
    FERRAMENTAS_P0,
    ID_ANCORA,
    ID_CONTROLE,
    MODELOS_TABELA,
    TABELAS_FERRAMENTA,
    Categoria,
    Cenario,
    CorteSugerido,
    DadosBuscarContexto,
    DadosCapacidadePoupanca,
    DadosCompararCenarios,
    DadosDividasParcelas,
    DadosOportunidadesCorte,
    DadosPerfilFinanceiro,
    DadosResumoMes,
    DadosSimularObjetivo,
    EntradaCategoria,
    FaixaRenda,
    Fonte,
    FonteRenda,
    GastoCategoria,
    GastoMacro,
    Oportunidade,
    Origem,
    Parcela,
    ParcelaAtiva,
    PerfilMes,
    Periodo,
    PontoMensal,
    Recorrente,
    RefCoorte,
    RegrasCenario,
    Resposta,
    Saldo,
    TipoDocumento,
    Trecho,
    UsuarioFixture,
    anomes_valido,
    arquivo_golden,
    arquivo_resumo_mes,
    brl,
    id_usuario_valido,
)

RAIZ_REPO = Path(__file__).resolve().parents[2]
SAIDA_PADRAO = RAIZ_REPO / "contracts" / "fixtures"

TABELA_ORIGEM = "hackathon_dados.extrato_sintetico"
IDS_FIXTURE: tuple[str, str] = (ID_ANCORA, ID_CONTROLE)

TOP_MAX = 10  # golden de oportunidades_corte e buscar_contexto_financeiro (R-10)
MESES_MIN_RECORRENCIA = 3
QTD_MIN_COORTE = 5  # grupos menores não são publicados (nunca dado individual)
TRECHOS_COORTE = 3
TOLERANCIA_SALDO = 0.005

TABELAS_DADOS: tuple[str, ...] = (
    "perfil_mensal",
    "gastos_categoria",
    "entradas_categoria",
    "recorrentes",
    "parcelas",
    "categorias",
    "referencia_coorte",
)

# ---------------------------------------------------------------------------
# SQL de referência (sempre parametrizado; nenhum valor entra por formatação de string)
# ---------------------------------------------------------------------------

SQL_EXTRATO = f"""
SELECT
  id_usuario, anomesdia, anomes, tipo, descr, vlr,
  nom_cate_macro, nom_cate_micro, saldo_apos, parcela_atual, parcela_total
FROM `{TABELA_ORIGEM}`
WHERE id_usuario IN UNNEST(@ids_usuario)
  AND anomes BETWEEN @anomes_inicio AND @anomes_fim
ORDER BY id_usuario, anomesdia, tipo, descr, vlr, saldo_apos
"""

SQL_CATEGORIAS = f"""
SELECT DISTINCT nom_cate_macro AS macro, nom_cate_micro AS micro
FROM `{TABELA_ORIGEM}`
WHERE anomes BETWEEN @anomes_inicio AND @anomes_fim
ORDER BY macro, micro
"""

# Agregado anônimo: uma linha por usuário × macro, sem id_usuario na saída.
SQL_COORTE = f"""
WITH mensal AS (
  SELECT id_usuario, anomes, SUM(IF(tipo = 'E', vlr, 0)) AS renda
  FROM `{TABELA_ORIGEM}`
  WHERE anomes BETWEEN @anomes_inicio AND @anomes_fim
  GROUP BY id_usuario, anomes
),
usuarios AS (
  SELECT id_usuario, AVG(renda) AS renda_media, COUNT(*) AS meses
  FROM mensal
  GROUP BY id_usuario
),
gastos AS (
  SELECT id_usuario, nom_cate_macro AS macro, SUM(vlr) AS total
  FROM `{TABELA_ORIGEM}`
  WHERE tipo = 'S' AND anomes BETWEEN @anomes_inicio AND @anomes_fim
  GROUP BY id_usuario, nom_cate_macro
)
SELECT u.renda_media AS renda_media, g.macro AS macro, g.total / u.meses AS media_mensal
FROM gastos AS g
JOIN usuarios AS u USING (id_usuario)
ORDER BY macro, renda_media, media_mensal
"""


def parametros_periodo(inicio: int = ANOMES_MIN, fim: int = ANOMES_MAX) -> list[Any]:
    """Parâmetros ``@anomes_inicio`` e ``@anomes_fim``."""
    from google.cloud import bigquery

    return [
        bigquery.ScalarQueryParameter("anomes_inicio", "INT64", inicio),
        bigquery.ScalarQueryParameter("anomes_fim", "INT64", fim),
    ]


def parametros_extrato(
    ids: Sequence[str] = IDS_FIXTURE, inicio: int = ANOMES_MIN, fim: int = ANOMES_MAX
) -> list[Any]:
    """Parâmetros de :data:`SQL_EXTRATO`: ``@ids_usuario`` e o período."""
    from google.cloud import bigquery

    return [
        bigquery.ArrayQueryParameter("ids_usuario", "STRING", list(ids)),
        *parametros_periodo(inicio, fim),
    ]


# ---------------------------------------------------------------------------
# Tipos de entrada das funções puras
# ---------------------------------------------------------------------------


class ErroDados(Exception):
    """Dados de origem inválidos. A mensagem nunca ecoa valores da origem."""


@dataclass(frozen=True, slots=True)
class Lancamento:
    """Uma linha do extrato (``nom_cate_macro``/``nom_cate_micro`` viram ``macro``/``micro``)."""

    id_usuario: str
    anomesdia: datetime
    anomes: int
    tipo: str
    descr: str
    vlr: float
    macro: str
    micro: str
    saldo_apos: float
    parcela_atual: int | None = None
    parcela_total: int | None = None

    @property
    def delta(self) -> float:
        """Efeito no saldo: ``+vlr`` para entrada, ``-vlr`` para saída."""
        return self.vlr if self.tipo == "E" else -self.vlr


@dataclass(frozen=True, slots=True)
class LinhaCoorte:
    """Linha anônima de :data:`SQL_COORTE` (usuário × macro, sem ``id_usuario``)."""

    renda_media: float
    macro: str
    media_mensal: float


def _inteiro_ou_none(valor: Any) -> int | None:
    if valor is None:
        return None
    numero = float(valor)
    if math.isnan(numero):
        return None
    return int(round(numero))


def lancamento_de_linha(linha: Mapping[str, Any]) -> Lancamento:
    """Converte uma linha de :data:`SQL_EXTRATO` (``Row`` do BigQuery ou dict)."""
    return Lancamento(
        id_usuario=str(linha["id_usuario"]),
        anomesdia=linha["anomesdia"],
        anomes=int(linha["anomes"]),
        tipo=str(linha["tipo"]),
        descr=str(linha["descr"] or ""),
        vlr=float(linha["vlr"]),
        macro=str(linha["nom_cate_macro"]),
        micro=str(linha["nom_cate_micro"]),
        saldo_apos=float(linha["saldo_apos"]),
        parcela_atual=_inteiro_ou_none(linha["parcela_atual"]),
        parcela_total=_inteiro_ou_none(linha["parcela_total"]),
    )


def linha_coorte_de(linha: Mapping[str, Any]) -> LinhaCoorte:
    """Converte uma linha de :data:`SQL_COORTE`."""
    return LinhaCoorte(
        renda_media=float(linha["renda_media"]),
        macro=str(linha["macro"]),
        media_mensal=float(linha["media_mensal"]),
    )


# ---------------------------------------------------------------------------
# Helpers puros
# ---------------------------------------------------------------------------


def _agrupar[T](itens: Iterable[T], chave: Callable[[T], Hashable]) -> dict[Any, list[T]]:
    grupos: dict[Any, list[T]] = defaultdict(list)
    for item in itens:
        grupos[chave(item)].append(item)
    return dict(grupos)


def normalizar_texto(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples (usado nas regras por palavra-chave)."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


_RE_PARCELA = re.compile(r"\bparc(?:ela)?\.?\s*\d{1,3}\s*(?:/|de)\s*\d{1,3}\b")
_RE_DATA = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b")


def normalizar_descr(descr: str) -> str:
    """``descr_norm`` do 001: minúsculas, sem marcação de parcela (``parc 1/12``) nem datas."""
    texto = _RE_PARCELA.sub(" ", descr.lower())
    texto = _RE_DATA.sub(" ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _contem_palavra(texto_normalizado: str, palavra: str) -> bool:
    """True se alguma palavra do texto começa com ``palavra``."""
    return re.search(r"\b" + re.escape(palavra), texto_normalizado) is not None


def eh_juros(micro: str) -> bool:
    """Microcategoria de juros: o nome normalizado contém ``juros``."""
    return _contem_palavra(normalizar_texto(micro), "juros")


def _mes_texto(anomes: int) -> str:
    return f"{anomes % 100:02d}/{anomes // 100}"


def _meses_texto(qtd: int) -> str:
    return "1 mês" if qtd == 1 else f"{qtd} meses"


def _reais(valor: float) -> str:
    """Valor em reais sem centavos, com ponto de milhar: ``R$ 1.250``."""
    inteiro = round(valor)
    texto = f"{abs(inteiro):,}".replace(",", ".")
    return f"-R$ {texto}" if inteiro < 0 else f"R$ {texto}"


def _pct_texto(fracao: float) -> str:
    return f"{round(fracao * 100)}%"


def _media(valores: Iterable[float]) -> float:
    return brl(statistics.fmean(valores))


def _mediana(valores: Iterable[float]) -> float:
    return brl(statistics.median(list(valores)))


def _meses_para(restante: float, aporte: float) -> int:
    """Meses inteiros para acumular ``restante`` com ``aporte`` mensal, sem rendimento."""
    if restante <= 0:
        return 0
    return math.ceil(round(restante / aporte, 9))


# ---------------------------------------------------------------------------
# Validação e ordem dos lançamentos
# ---------------------------------------------------------------------------


def validar_lancamentos(
    lancamentos: Sequence[Lancamento], ids_esperados: Sequence[str] = IDS_FIXTURE
) -> list[Lancamento]:
    """Confere a origem e devolve os lançamentos com ``id_usuario`` em minúsculas.

    Aborta com :class:`ErroDados` (sem ecoar valores) quando há ``id_usuario`` fora do
    formato UUID v4, usuário inesperado, usuário esperado sem lançamentos, ``anomes`` fora
    de 202501–202512 ou ``tipo`` diferente de ``E``/``S``.
    """
    invalidos = sum(1 for lanc in lancamentos if not id_usuario_valido(lanc.id_usuario))
    if invalidos:
        raise ErroDados(
            f"{invalidos} linha(s) do extrato com id_usuario fora do formato UUID v4. "
            "Nenhuma fixture foi gravada."
        )
    normalizados = [replace(lanc, id_usuario=lanc.id_usuario.lower()) for lanc in lancamentos]
    esperados = [i.lower() for i in ids_esperados]
    inesperados = {lanc.id_usuario for lanc in normalizados} - set(esperados)
    if inesperados:
        raise ErroDados(
            f"{len(inesperados)} id_usuario fora dos usuários de fixture no extrato lido."
        )
    presentes = {lanc.id_usuario for lanc in normalizados}
    for papel, id_usuario in zip(("âncora", "controle"), esperados, strict=False):
        if id_usuario not in presentes:
            raise ErroDados(f"Sem lançamentos de 2025 para o usuário {papel} ({id_usuario}).")
    fora = sum(1 for lanc in normalizados if not anomes_valido(lanc.anomes))
    if fora:
        raise ErroDados(f"{fora} linha(s) com anomes fora de {ANOMES_MIN}–{ANOMES_MAX}.")
    tipos = sum(1 for lanc in normalizados if lanc.tipo not in ("E", "S"))
    if tipos:
        raise ErroDados(f"{tipos} linha(s) com tipo diferente de 'E' e 'S'.")
    return normalizados


def _chave_estavel(lanc: Lancamento) -> tuple[Any, ...]:
    return (lanc.anomesdia, lanc.tipo, lanc.descr, lanc.vlr, lanc.saldo_apos)


def _indice_proximo(pendentes: list[Lancamento], saldo: float | None) -> int:
    if len(pendentes) == 1:
        return 0
    if saldo is not None:
        for indice, lanc in enumerate(pendentes):
            if abs(lanc.saldo_apos - lanc.delta - saldo) < TOLERANCIA_SALDO:
                return indice
    for indice, lanc in enumerate(pendentes):
        antes = lanc.saldo_apos - lanc.delta
        if not any(
            abs(outro.saldo_apos - antes) < TOLERANCIA_SALDO
            for j, outro in enumerate(pendentes)
            if j != indice
        ):
            return indice
    return 0


def ordenar_lancamentos(lancamentos: Iterable[Lancamento]) -> list[Lancamento]:
    """Ordena por usuário e ``anomesdia``; empates seguem a cadeia de ``saldo_apos``.

    Dentro de um mesmo ``anomesdia``, o próximo lançamento é o que começa do saldo
    corrente (``saldo_apos - delta``). Sem saldo conhecido, é o que começa de um saldo que
    nenhum outro pendente produz. Sem encaixe, vale a ordem estável de :func:`_chave_estavel`.
    O resultado não depende da ordem de entrada.
    """
    resultado: list[Lancamento] = []
    por_usuario = _agrupar(lancamentos, attrgetter("id_usuario"))
    for id_usuario in sorted(por_usuario):
        saldo: float | None = None
        base = sorted(por_usuario[id_usuario], key=_chave_estavel)
        for _, grupo in groupby(base, key=attrgetter("anomesdia")):
            pendentes = list(grupo)
            while pendentes:
                escolhido = pendentes.pop(_indice_proximo(pendentes, saldo))
                resultado.append(escolhido)
                saldo = escolhido.saldo_apos
    return resultado


# ---------------------------------------------------------------------------
# Tabelas de bussola_dados (regras de 001 §3.1)
# ---------------------------------------------------------------------------


def calcular_perfil_mensal(lancamentos: Iterable[Lancamento]) -> list[PerfilMes]:
    """Uma linha por usuário/mês.

    - ``renda`` = Σ entradas; ``gasto`` = Σ saídas; ``sobra`` = ``renda - gasto`` (já em BRL);
    - ``saldo_inicial`` = saldo antes do primeiro lançamento do mês (``saldo_apos - delta``);
    - ``saldo_final`` = ``saldo_apos`` do último lançamento do mês;
    - ``saldo_minimo``/``saldo_maximo`` = mínimo/máximo de ``saldo_apos`` no mês;
    - ``juros`` = Σ saídas cuja micro contém "juros" (:func:`eh_juros`).
    """
    ordenados = ordenar_lancamentos(lancamentos)
    grupos = _agrupar(ordenados, lambda lanc: (lanc.id_usuario, lanc.anomes))
    linhas: list[PerfilMes] = []
    for (id_usuario, anomes), lancs in sorted(grupos.items()):
        renda = brl(math.fsum(lanc.vlr for lanc in lancs if lanc.tipo == "E"))
        gasto = brl(math.fsum(lanc.vlr for lanc in lancs if lanc.tipo == "S"))
        saldos = [lanc.saldo_apos for lanc in lancs]
        juros = math.fsum(lanc.vlr for lanc in lancs if lanc.tipo == "S" and eh_juros(lanc.micro))
        linhas.append(
            PerfilMes(
                id_usuario=id_usuario,
                anomes=anomes,
                renda=renda,
                gasto=gasto,
                sobra=brl(renda - gasto),
                saldo_inicial=brl(lancs[0].saldo_apos - lancs[0].delta),
                saldo_final=brl(lancs[-1].saldo_apos),
                saldo_minimo=brl(min(saldos)),
                saldo_maximo=brl(max(saldos)),
                juros=brl(juros),
            )
        )
    return linhas


def _agregar_por_categoria[M: BaseModel](
    lancamentos: Iterable[Lancamento], tipo: str, modelo: type[M]
) -> list[M]:
    grupos = _agrupar(
        (lanc for lanc in lancamentos if lanc.tipo == tipo),
        lambda lanc: (lanc.id_usuario, lanc.anomes, lanc.macro, lanc.micro),
    )
    return [
        modelo(
            id_usuario=id_usuario,
            anomes=anomes,
            macro=macro,
            micro=micro,
            total=brl(math.fsum(lanc.vlr for lanc in lancs)),
            qtd=len(lancs),
        )
        for (id_usuario, anomes, macro, micro), lancs in sorted(grupos.items())
    ]


def calcular_gastos_categoria(lancamentos: Iterable[Lancamento]) -> list[GastoCategoria]:
    """Saídas (``tipo = 'S'``) por usuário, mês, macro e micro: ``total`` e ``qtd``."""
    return _agregar_por_categoria(lancamentos, "S", GastoCategoria)


def calcular_entradas_categoria(lancamentos: Iterable[Lancamento]) -> list[EntradaCategoria]:
    """Entradas (``tipo = 'E'``) por usuário, mês, macro e micro: ``total`` e ``qtd``."""
    return _agregar_por_categoria(lancamentos, "E", EntradaCategoria)


def calcular_recorrentes(lancamentos: Iterable[Lancamento]) -> list[Recorrente]:
    """Saídas cuja ``descr_norm`` aparece em ≥ 3 meses distintos do ano (por usuário).

    Leitura adotada: só saídas (a tabela não tem ``tipo`` e o mestre fala em gastos
    recorrentes). Uma linha por usuário, mês, ``descr_norm``, macro e micro, com
    ``valor`` = soma do mês.
    """
    saidas = [(lanc, normalizar_descr(lanc.descr)) for lanc in lancamentos if lanc.tipo == "S"]
    saidas = [(lanc, descr) for lanc, descr in saidas if descr]
    meses: dict[tuple[str, str], set[int]] = defaultdict(set)
    for lanc, descr in saidas:
        meses[(lanc.id_usuario, descr)].add(lanc.anomes)
    grupos: dict[tuple[str, int, str, str, str], list[float]] = defaultdict(list)
    for lanc, descr in saidas:
        if len(meses[(lanc.id_usuario, descr)]) >= MESES_MIN_RECORRENCIA:
            chave = (lanc.id_usuario, lanc.anomes, descr, lanc.macro, lanc.micro)
            grupos[chave].append(lanc.vlr)
    return [
        Recorrente(
            id_usuario=id_usuario,
            anomes=anomes,
            descr_norm=descr,
            macro=macro,
            micro=micro,
            valor=brl(math.fsum(valores)),
        )
        for (id_usuario, anomes, descr, macro, micro), valores in sorted(grupos.items())
    ]


def calcular_parcelas(lancamentos: Iterable[Lancamento]) -> list[Parcela]:
    """Lançamentos com ``parcela_total > 1`` (sem filtro de ``tipo``), um por linha."""
    linhas = [
        Parcela(
            id_usuario=lanc.id_usuario,
            anomes=lanc.anomes,
            descr=lanc.descr,
            macro=lanc.macro,
            parcela_atual=lanc.parcela_atual,
            parcela_total=lanc.parcela_total,
            vlr=brl(lanc.vlr),
        )
        for lanc in lancamentos
        if lanc.parcela_total is not None
        and lanc.parcela_total > 1
        and lanc.parcela_atual is not None
    ]
    return sorted(
        linhas,
        key=lambda p: (p.id_usuario, p.anomes, p.descr, p.parcela_atual, p.parcela_total, p.vlr),
    )


# Regra provisória de discricionárias (001 §3.1). A ordem importa: vale a primeira que casar.
REGRAS_DISCRICIONARIAS: tuple[tuple[str, float], ...] = (
    ("assinatura", 0.5),
    ("streaming", 0.5),
    ("delivery", 0.5),
    ("restaurante", 0.3),
    ("comer fora", 0.3),
    ("lanche", 0.3),
    ("lazer", 0.3),
    ("entretenimento", 0.3),
    ("cinema", 0.3),
    ("vestuario", 0.3),
    ("roupa", 0.3),
    ("calcado", 0.3),
    ("compra", 0.3),
    ("viage", 0.2),
    ("turismo", 0.2),
    ("hotel", 0.2),
    ("hosped", 0.2),
    ("passage", 0.2),
)

# Micro com estas palavras nunca é discricionária, mesmo sob uma macro discricionária.
PALAVRAS_ESSENCIAIS: tuple[str, ...] = (
    "mercado",
    "supermercado",
    "hipermercado",
    "farmacia",
    "saude",
    "medic",
    "hospital",
    "aluguel",
    "condominio",
    "financiamento",
    "emprestimo",
    "juros",
    "educacao",
    "escola",
    "faculdade",
    "imposto",
    "tarifa",
    "seguro",
    "energia",
    "agua",
)


def _pct_discricionario(texto_normalizado: str) -> float | None:
    for palavra, pct in REGRAS_DISCRICIONARIAS:
        if _contem_palavra(texto_normalizado, palavra):
            return pct
    return None


def classificar_categoria(macro: str, micro: str) -> Categoria:
    """Classificação provisória por palavra-chave (o seed revisado do 001 a substitui).

    Discricionárias (001 §3.1): assinaturas, streaming e delivery (``corte_max_pct`` 0,5);
    restaurantes/comer fora, lazer e compras/vestuário (0,3); viagens (0,2). A micro tem
    prioridade sobre a macro, e micros essenciais (:data:`PALAVRAS_ESSENCIAIS`) nunca são
    discricionárias. As demais têm ``corte_max_pct = 0``.
    """
    micro_n = normalizar_texto(micro)
    pct: float | None = None
    if not any(_contem_palavra(micro_n, palavra) for palavra in PALAVRAS_ESSENCIAIS):
        pct = _pct_discricionario(micro_n)
        if pct is None:
            pct = _pct_discricionario(normalizar_texto(macro))
    return Categoria(
        macro=macro, micro=micro, discricionaria=pct is not None, corte_max_pct=pct or 0.0
    )


def calcular_categorias(
    pares: Iterable[tuple[str, str]], lancamentos: Iterable[Lancamento] = ()
) -> list[Categoria]:
    """Catálogo macro/micro (pares da origem mais os pares vistos nos lançamentos)."""
    todos = {(macro, micro) for macro, micro in pares}
    todos |= {(lanc.macro, lanc.micro) for lanc in lancamentos}
    return [classificar_categoria(macro, micro) for macro, micro in sorted(todos)]


LIMITES_FAIXA: tuple[float, ...] = (3000.0, 6000.0, 10000.0, 20000.0)
_ORDEM_FAIXA = {faixa.value: indice for indice, faixa in enumerate(FaixaRenda)}
ROTULO_FAIXA = {
    FaixaRenda.ATE_3K.value: "até R$ 3 mil",
    FaixaRenda.DE_3K_A_6K.value: "entre R$ 3 mil e R$ 6 mil",
    FaixaRenda.DE_6K_A_10K.value: "entre R$ 6 mil e R$ 10 mil",
    FaixaRenda.DE_10K_A_20K.value: "entre R$ 10 mil e R$ 20 mil",
    FaixaRenda.ACIMA_20K.value: "acima de R$ 20 mil",
}


def faixa_renda(renda_media: float) -> str:
    """Faixa de renda mensal média: limites inferiores inclusivos (3 mil, 6 mil, 10 mil, 20 mil)."""
    return list(FaixaRenda)[bisect_right(LIMITES_FAIXA, renda_media)].value


def calcular_referencia_coorte(
    linhas: Iterable[LinhaCoorte], qtd_min: int = QTD_MIN_COORTE
) -> list[RefCoorte]:
    """Média e mediana do gasto mensal por faixa de renda × macro, entre todos os usuários.

    Leitura adotada: entram os usuários com gasto na macro (sem zeros para quem não
    gasta). Grupos com menos de ``qtd_min`` usuários não são publicados.
    """
    grupos: dict[tuple[str, str], list[float]] = defaultdict(list)
    for linha in linhas:
        grupos[(faixa_renda(linha.renda_media), linha.macro)].append(linha.media_mensal)
    ordenados = sorted(grupos.items(), key=lambda item: (_ORDEM_FAIXA[item[0][0]], item[0][1]))
    return [
        RefCoorte(
            faixa_renda=faixa,
            macro=macro,
            media=_media(valores),
            mediana=_mediana(valores),
            qtd_usuarios=len(valores),
        )
        for (faixa, macro), valores in ordenados
        if len(valores) >= qtd_min
    ]


def calcular_tabelas(
    lancamentos: Sequence[Lancamento],
    pares_categorias: Iterable[tuple[str, str]],
    linhas_coorte: Iterable[LinhaCoorte],
) -> dict[str, list[BaseModel]]:
    """As 7 tabelas de ``bussola_dados`` (nome sem dataset → linhas validadas)."""
    return {
        "perfil_mensal": list(calcular_perfil_mensal(lancamentos)),
        "gastos_categoria": list(calcular_gastos_categoria(lancamentos)),
        "entradas_categoria": list(calcular_entradas_categoria(lancamentos)),
        "recorrentes": list(calcular_recorrentes(lancamentos)),
        "parcelas": list(calcular_parcelas(lancamentos)),
        "categorias": list(calcular_categorias(pares_categorias, lancamentos)),
        "referencia_coorte": list(calcular_referencia_coorte(linhas_coorte)),
    }


# ---------------------------------------------------------------------------
# Golden das ferramentas (regras de 001 §3.4/§3.5 e contratos §5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DadosUsuario:
    """Linhas de um usuário em ``bussola_dados``."""

    id_usuario: str
    perfil: list[PerfilMes]
    gastos: list[GastoCategoria]
    entradas: list[EntradaCategoria]
    recorrentes: list[Recorrente]
    parcelas: list[Parcela]

    @classmethod
    def de_tabelas(cls, tabelas: Mapping[str, Sequence[Any]], id_usuario: str) -> "DadosUsuario":
        def do_usuario(nome: str) -> list[Any]:
            return [linha for linha in tabelas[nome] if linha.id_usuario == id_usuario]

        return cls(
            id_usuario=id_usuario,
            perfil=sorted(do_usuario("perfil_mensal"), key=attrgetter("anomes")),
            gastos=do_usuario("gastos_categoria"),
            entradas=do_usuario("entradas_categoria"),
            recorrentes=do_usuario("recorrentes"),
            parcelas=do_usuario("parcelas"),
        )

    def meses_ate(self, corte: int) -> list[PerfilMes]:
        """Meses de ``perfil_mensal`` com ``anomes <= corte`` (aborta se não houver)."""
        meses = [p for p in self.perfil if p.anomes <= corte]
        if not meses:
            raise ErroDados(f"Sem meses de perfil até {corte} para gerar o golden.")
        return meses


def _envelope(
    ferramenta: str, dados: BaseModel, inicio: int, fim: int, avisos: Sequence[str] = ()
) -> dict[str, Any]:
    modelo = FERRAMENTAS[ferramenta][1]
    resposta = Resposta[modelo](
        dados=dados,
        fonte=Fonte(
            ferramenta=ferramenta,
            tabelas=list(TABELAS_FERRAMENTA[ferramenta]),
            periodo=Periodo(inicio=inicio, fim=fim),
        ),
        avisos=list(avisos),
    )
    return resposta.model_dump(mode="json")


def _aviso_saldo_negativo(meses: Sequence[PerfilMes]) -> list[str]:
    negativos = sum(1 for p in meses if p.saldo_minimo < 0)
    if not negativos:
        return []
    return [f"Saldo ficou negativo em {_meses_texto(negativos)} do período."]


def golden_perfil_financeiro(dados: DadosUsuario, corte: int) -> dict[str, Any]:
    """``perfil_financeiro`` até ``corte``.

    Médias e mediana dos meses considerados; ``fontes_renda`` = entradas por macro/micro,
    com ``media`` = total ÷ meses considerados (maior primeiro); ``saldo.minimo``/``maximo``
    do período; ``saldo.atual`` = ``saldo_final`` do último mês até o corte.
    """
    meses = dados.meses_ate(corte)
    qtd = len(meses)
    entradas = _agrupar(
        (e for e in dados.entradas if e.anomes <= corte), lambda e: (e.macro, e.micro)
    )
    fontes = sorted(
        (
            FonteRenda(macro=macro, micro=micro, media=brl(math.fsum(e.total for e in itens) / qtd))
            for (macro, micro), itens in entradas.items()
        ),
        key=lambda f: (-f.media, f.macro, f.micro),
    )
    resultado = DadosPerfilFinanceiro(
        renda_media=_media(p.renda for p in meses),
        gasto_medio=_media(p.gasto for p in meses),
        sobra_media=_media(p.sobra for p in meses),
        sobra_mediana=_mediana(p.sobra for p in meses),
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
    return _envelope(
        "perfil_financeiro", resultado, meses[0].anomes, corte, _aviso_saldo_negativo(meses)
    )


def golden_capacidade_poupanca(dados: DadosUsuario, corte: int) -> dict[str, Any]:
    """``capacidade_poupanca`` até ``corte``.

    ``desvio_padrao`` = desvio padrão populacional (``statistics.pstdev``) das sobras;
    ``meses_negativos`` = meses com ``sobra < 0``.
    """
    meses = dados.meses_ate(corte)
    sobras = [p.sobra for p in meses]
    negativos = sum(1 for s in sobras if s < 0)
    resultado = DadosCapacidadePoupanca(
        sobra_media=_media(sobras),
        sobra_mediana=_mediana(sobras),
        desvio_padrao=brl(statistics.pstdev(sobras)),
        meses_negativos=negativos,
        meses_considerados=len(meses),
    )
    avisos = []
    if negativos:
        avisos.append(f"Gasto superou a renda em {_meses_texto(negativos)} do período.")
    return _envelope("capacidade_poupanca", resultado, meses[0].anomes, corte, avisos)


def _criterio(corte_max_pct: float) -> str:
    return (
        f"Categoria discricionária: corte de até {_pct_texto(corte_max_pct)} "
        "da média mensal no período."
    )


def calcular_oportunidades(
    gastos: Iterable[GastoCategoria],
    categorias: Iterable[Categoria],
    meses_considerados: int,
    limite: int = TOP_MAX,
) -> list[Oportunidade]:
    """Só discricionárias. ``media_mensal`` = total ÷ meses considerados;
    ``economia_potencial_mensal`` = ``media_mensal × corte_max_pct``. Ordem: maior economia,
    maior média, macro, micro. Até ``limite`` itens.
    """
    por_categoria = {(c.macro, c.micro): c for c in categorias}
    totais = _agrupar(gastos, lambda g: (g.macro, g.micro))
    oportunidades: list[Oportunidade] = []
    for (macro, micro), itens in totais.items():
        categoria = por_categoria.get((macro, micro))
        if categoria is None or not categoria.discricionaria:
            continue
        media = brl(math.fsum(g.total for g in itens) / meses_considerados)
        if media <= 0:
            continue
        oportunidades.append(
            Oportunidade(
                macro=macro,
                micro=micro,
                media_mensal=media,
                discricionaria=True,
                economia_potencial_mensal=brl(media * categoria.corte_max_pct),
                criterio=_criterio(categoria.corte_max_pct),
            )
        )
    oportunidades.sort(
        key=lambda o: (-o.economia_potencial_mensal, -o.media_mensal, o.macro, o.micro)
    )
    return oportunidades[:limite]


def golden_oportunidades_corte(
    dados: DadosUsuario, categorias: Sequence[Categoria], corte: int
) -> dict[str, Any]:
    """``oportunidades_corte`` até ``corte`` com até 10 itens (o mock corta em ``top_n``)."""
    meses = dados.meses_ate(corte)
    gastos = [g for g in dados.gastos if g.anomes <= corte]
    itens = calcular_oportunidades(gastos, categorias, len(meses))
    avisos = [] if itens else ["Nenhuma categoria discricionária com gasto no período."]
    return _envelope(
        "oportunidades_corte",
        DadosOportunidadesCorte(categorias=itens),
        meses[0].anomes,
        corte,
        avisos,
    )


def golden_dividas_e_parcelas(dados: DadosUsuario, corte: int) -> dict[str, Any]:
    """``dividas_e_parcelas`` até ``corte``.

    Leitura adotada: ``parcelas_ativas`` = parcelas lançadas no mês do corte (a ocorrência
    mais recente de cada compra), com ``meses_restantes = parcela_total - parcela_atual``
    (inclui a última parcela, com 0). ``comprometimento_renda_pct`` = Σ dessas parcelas ÷
    renda média × 100 (escala 0–100, 2 casas). ``juros_pagos_media`` = média de ``juros``.
    """
    meses = dados.meses_ate(corte)
    do_mes = [p for p in dados.parcelas if p.anomes == corte]
    ativas = sorted(
        (
            ParcelaAtiva(
                descr=p.descr,
                parcela_atual=p.parcela_atual,
                parcela_total=p.parcela_total,
                valor=p.vlr,
                meses_restantes=max(0, p.parcela_total - p.parcela_atual),
            )
            for p in do_mes
        ),
        key=lambda a: (-a.valor, a.descr, a.parcela_atual, a.parcela_total),
    )
    renda_media = _media(p.renda for p in meses)
    total_parcelas = math.fsum(a.valor for a in ativas)
    avisos: list[str] = []
    if renda_media > 0:
        comprometimento = brl(total_parcelas / renda_media * 100)
    else:
        comprometimento = 0.0
        avisos.append("Renda média zerada no período; comprometimento não calculado.")
    if not ativas:
        avisos.append("Não há parcelas no mês de corte.")
    resultado = DadosDividasParcelas(
        parcelas_ativas=ativas,
        juros_pagos_media=_media(p.juros for p in meses),
        comprometimento_renda_pct=comprometimento,
    )
    return _envelope("dividas_e_parcelas", resultado, meses[0].anomes, corte, avisos)


def calcular_simulacao(
    meses: Sequence[PerfilMes],
    valor_alvo: float,
    prazo_meses: int | None = None,
    aporte_mensal: float | None = None,
    usar_saldo_atual: bool = False,
) -> tuple[DadosSimularObjetivo, list[str]]:
    """Simulação sem rendimento sobre a sobra mediana dos meses considerados.

    - ``modo="prazo"`` (entrada com ``prazo_meses``): ``aporte = (alvo - saldo_inicial) ÷ prazo``;
    - ``modo="aporte"`` (entrada com ``aporte_mensal``): ``prazo = ⌈(alvo - saldo_inicial) ÷
      aporte⌉``;
    - ``saldo_inicial`` = 0, ou o ``saldo_final`` do último mês (mínimo 0) com
      ``usar_saldo_atual``;
    - ``folga_mensal = sobra_mediana - aporte``; ``viavel`` = sobra mediana positiva e
      folga ≥ 0.
    """
    if (prazo_meses is None) == (aporte_mensal is None):
        raise ValueError("informe exatamente um entre prazo_meses e aporte_mensal")
    capacidade = _mediana(p.sobra for p in meses)
    saldo_inicial = brl(max(0.0, meses[-1].saldo_final)) if usar_saldo_atual else 0.0
    restante = max(0.0, valor_alvo - saldo_inicial)
    if prazo_meses is not None:
        modo = "prazo"
        prazo = prazo_meses
        aporte = brl(restante / prazo_meses)
    else:
        modo = "aporte"
        aporte = brl(aporte_mensal)
        prazo = _meses_para(restante, aporte_mensal)
    folga = brl(capacidade - aporte)
    viavel = capacidade > 0 and folga >= 0
    avisos: list[str] = []
    if capacidade <= 0:
        avisos.append("A sobra mensal mediana não é positiva no período.")
    elif not viavel:
        avisos.append("O aporte necessário supera a sobra mensal mediana.")
    resultado = DadosSimularObjetivo(
        modo=modo,
        valor_alvo=brl(valor_alvo),
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
            "usar_saldo_atual": usar_saldo_atual,
        },
    )
    return resultado, avisos


def golden_simular_objetivo(
    dados: DadosUsuario,
    corte: int,
    valor_alvo: float = ENTRADA_CANONICA_SIMULACAO["valor_alvo"],
    prazo_meses: int | None = ENTRADA_CANONICA_SIMULACAO["prazo_meses"],
    aporte_mensal: float | None = None,
    usar_saldo_atual: bool = False,
) -> dict[str, Any]:
    """``simular_objetivo`` até ``corte``; por padrão, a entrada canônica (R-09)."""
    meses = dados.meses_ate(corte)
    resultado, avisos = calcular_simulacao(
        meses, valor_alvo, prazo_meses, aporte_mensal, usar_saldo_atual
    )
    return _envelope("simular_objetivo", resultado, meses[0].anomes, corte, avisos)


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
            f"Atinge a meta em {_meses_texto(prazo)}, dentro do prazo de "
            f"{_meses_texto(prazo_desejado)}."
        )
    else:
        frases.append(
            f"Precisa de {_meses_texto(prazo)}, além do prazo de {_meses_texto(prazo_desejado)}."
        )
    if capacidade > 0:
        frases.append(f"Compromete {_pct_texto(pct)} da sobra mensal mediana ({_reais(base)}/mês).")
    for corte in cortes:
        frases.append(f"Exige reduzir {_reais(corte.valor_mensal)}/mês em {corte.micro}.")
    return frases


def calcular_cenarios(
    meses: Sequence[PerfilMes],
    oportunidades: Sequence[Oportunidade],
    valor_alvo: float,
    prazo_meses: int,
    regras: RegrasCenario | None = None,
) -> tuple[DadosCompararCenarios, list[str]]:
    """Cenários de :class:`RegrasCenario` sobre a sobra mediana (sem valores fixos).

    ``aporte = pct × sobra_mediana`` (0 se a sobra mediana não for positiva). No cenário
    ``acelerado`` (com ``cortes_no_acelerado``) somam-se as economias de todas as
    oportunidades com economia positiva, que viram ``cortes_sugeridos``. ``prazo = ⌈(alvo -
    saldo_inicial) ÷ aporte⌉`` (0 e inviável sem aporte); ``viavel = prazo ≤ prazo_meses``.
    """
    regras = regras or RegrasCenario()
    capacidade = _mediana(p.sobra for p in meses)
    restante = max(0.0, valor_alvo - regras.saldo_inicial)
    cortes = [
        CorteSugerido(macro=o.macro, micro=o.micro, valor_mensal=o.economia_potencial_mensal)
        for o in oportunidades
        if o.economia_potencial_mensal > 0
    ]
    cenarios: list[Cenario] = []
    for nome, pct in regras.pct_capacidade.items():
        base = brl(pct * max(capacidade, 0.0))
        do_cenario = cortes if nome == "acelerado" and regras.cortes_no_acelerado else []
        aporte = brl(base + math.fsum(c.valor_mensal for c in do_cenario))
        if aporte > 0:
            prazo = _meses_para(restante, aporte)
            viavel = prazo <= prazo_meses
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
                trade_offs=_trade_offs(
                    prazo, prazo_meses, aporte, pct, base, capacidade, do_cenario
                ),
            )
        )
    avisos: list[str] = []
    if capacidade <= 0:
        avisos.append("A sobra mensal mediana não é positiva no período; só cortes geram aporte.")
    return DadosCompararCenarios(cenarios=cenarios, regras=regras), avisos


def golden_comparar_cenarios(
    dados: DadosUsuario,
    categorias: Sequence[Categoria],
    corte: int,
    valor_alvo: float = ENTRADA_CANONICA_SIMULACAO["valor_alvo"],
    prazo_meses: int = ENTRADA_CANONICA_SIMULACAO["prazo_meses"],
) -> dict[str, Any]:
    """``comparar_cenarios`` até ``corte``; por padrão, a entrada canônica (R-09).

    Os cortes do cenário acelerado são as mesmas oportunidades (até 10) de
    :func:`golden_oportunidades_corte`.
    """
    meses = dados.meses_ate(corte)
    gastos = [g for g in dados.gastos if g.anomes <= corte]
    oportunidades = calcular_oportunidades(gastos, categorias, len(meses))
    resultado, avisos = calcular_cenarios(meses, oportunidades, valor_alvo, prazo_meses)
    return _envelope("comparar_cenarios", resultado, meses[0].anomes, corte, avisos)


def filtrar_trechos(trechos: Iterable[Trecho], id_usuario: str, corte: int) -> list[Trecho]:
    """Escopo e tempo do buscador: trechos do cliente ou de coorte, com ``anomes`` nulo ou
    ``≤ corte``; ordem por ``score`` decrescente e ``doc_id``."""
    visiveis = [
        t
        for t in trechos
        if (t.origem.id_usuario == id_usuario or t.tipo == TipoDocumento.COORTE.value)
        and (t.anomes is None or t.anomes <= corte)
    ]
    return sorted(visiveis, key=lambda t: (-t.score, t.doc_id))


def golden_buscar_contexto(
    dados: DadosUsuario, trechos: Sequence[Trecho], corte: int
) -> dict[str, Any]:
    """``buscar_contexto_financeiro`` até ``corte`` com até 10 trechos (o mock corta em ``k``).

    Independe da pergunta: é o ranking fixo de :func:`gerar_trechos` após o filtro.
    """
    meses = dados.meses_ate(corte)
    visiveis = filtrar_trechos(trechos, dados.id_usuario, corte)[:TOP_MAX]
    avisos = [] if visiveis else ["Nenhum trecho encontrado para o período."]
    return _envelope(
        "buscar_contexto_financeiro",
        DadosBuscarContexto(trechos=visiveis),
        meses[0].anomes,
        corte,
        avisos,
    )


def _gastos_macro(gastos: Iterable[GastoCategoria]) -> list[GastoMacro]:
    por_macro = _agrupar(gastos, attrgetter("macro"))
    return sorted(
        (
            GastoMacro(macro=macro, total=brl(math.fsum(g.total for g in itens)))
            for macro, itens in por_macro.items()
        ),
        key=lambda g: (-g.total, g.macro),
    )


def golden_resumo_mes(dados: DadosUsuario, anomes: int) -> dict[str, Any]:
    """``resumo_mes`` de um mês: valores de ``perfil_mensal`` e gastos por macro do mês."""
    perfil = next((p for p in dados.perfil if p.anomes == anomes), None)
    if perfil is None:
        raise ErroDados(f"Sem perfil do mês {anomes} para o resumo_mes.")
    avisos: list[str] = []
    if perfil.saldo_minimo < 0:
        avisos.append("Saldo ficou negativo neste mês.")
    if perfil.sobra < 0:
        avisos.append("Gasto superou a renda neste mês.")
    resultado = DadosResumoMes(
        anomes=anomes,
        renda=perfil.renda,
        gasto=perfil.gasto,
        sobra=perfil.sobra,
        gastos_macro=_gastos_macro(g for g in dados.gastos if g.anomes == anomes),
    )
    return _envelope("resumo_mes", resultado, anomes, anomes, avisos)


# ---------------------------------------------------------------------------
# Trechos RAG de exemplo (FR-016)
# ---------------------------------------------------------------------------


def _texto_ficha(
    perfil: PerfilMes, gastos: Sequence[GastoCategoria], parcelas: Sequence[Parcela]
) -> str:
    partes = [
        f"Ficha de {_mes_texto(perfil.anomes)}: renda {_reais(perfil.renda)}, "
        f"gasto {_reais(perfil.gasto)} e sobra {_reais(perfil.sobra)}."
    ]
    maiores = _gastos_macro(gastos)[:3]
    if maiores:
        partes.append(
            "Maiores gastos: " + ", ".join(f"{g.macro} {_reais(g.total)}" for g in maiores) + "."
        )
    partes.append(
        f"Saldo inicial {_reais(perfil.saldo_inicial)}, final {_reais(perfil.saldo_final)} "
        f"e mínimo {_reais(perfil.saldo_minimo)}."
    )
    if perfil.juros > 0:
        partes.append(f"Juros pagos: {_reais(perfil.juros)}.")
    if parcelas:
        total = math.fsum(p.vlr for p in parcelas)
        partes.append(f"Parcelas no mês: {len(parcelas)}, somando {_reais(total)}.")
    if perfil.saldo_minimo < 0:
        partes.append("O saldo ficou negativo no mês.")
    return " ".join(partes)


def _texto_perfil_anual(meses: Sequence[PerfilMes], recorrentes: Sequence[Recorrente]) -> str:
    qtd = len(meses)
    renda = _reais(_media(p.renda for p in meses))
    gasto = _reais(_media(p.gasto for p in meses))
    sobra = _reais(_media(p.sobra for p in meses))
    partes = [
        f"Perfil de {meses[-1].anomes // 100}: renda média {renda}, gasto médio {gasto} "
        f"e sobra média {sobra} em {_meses_texto(qtd)}."
    ]
    por_micro = _agrupar(recorrentes, attrgetter("micro"))
    medias = sorted(
        ((micro, math.fsum(r.valor for r in itens) / qtd) for micro, itens in por_micro.items()),
        key=lambda item: (-item[1], item[0]),
    )[:5]
    if medias:
        partes.append(
            "Gastos recorrentes: "
            + ", ".join(f"{micro} {_reais(media)}/mês" for micro, media in medias)
            + "."
        )
    negativos = sum(1 for p in meses if p.saldo_minimo < 0)
    if negativos:
        partes.append(f"O saldo ficou negativo em {_meses_texto(negativos)}.")
    return " ".join(partes)


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalizar_texto(texto)).strip("_")


def gerar_trechos(
    usuarios: Sequence[DadosUsuario],
    referencia_coorte: Sequence[RefCoorte],
    id_ancora: str,
    faixa_ancora: str,
) -> list[Trecho]:
    """Trechos determinísticos no formato de ``buscar_contexto_financeiro``.

    - ``ficha_mensal`` de cada usuário (âncora e controle), ``score = 0,50 + 0,03 × mês``;
    - ``perfil_anual`` do âncora (``anomes`` = último mês, ``score = 0,95``);
    - ``coorte`` das 3 maiores macros da faixa do âncora (``score`` 0,70, 0,69, 0,68), sem
      ``id_usuario`` nem ``anomes``.

    Os textos usam só valores agregados e nomes de categoria, nunca ``descr``.
    """
    trechos: list[Trecho] = []
    for dados in usuarios:
        for perfil in dados.perfil:
            trechos.append(
                Trecho(
                    doc_id=f"{TipoDocumento.FICHA_MENSAL.value}:{dados.id_usuario}:{perfil.anomes}",
                    tipo=TipoDocumento.FICHA_MENSAL.value,
                    anomes=perfil.anomes,
                    texto=_texto_ficha(
                        perfil,
                        [g for g in dados.gastos if g.anomes == perfil.anomes],
                        [p for p in dados.parcelas if p.anomes == perfil.anomes],
                    ),
                    score=round(0.50 + 0.03 * (perfil.anomes % 100), 4),
                    origem=Origem(
                        id_usuario=dados.id_usuario, anomes=perfil.anomes, categoria=None
                    ),
                )
            )
        if dados.id_usuario == id_ancora and dados.perfil:
            ultimo = dados.perfil[-1].anomes
            trechos.append(
                Trecho(
                    doc_id=f"{TipoDocumento.PERFIL_ANUAL.value}:{dados.id_usuario}:{ultimo // 100}",
                    tipo=TipoDocumento.PERFIL_ANUAL.value,
                    anomes=ultimo,
                    texto=_texto_perfil_anual(dados.perfil, dados.recorrentes),
                    score=0.95,
                    origem=Origem(id_usuario=dados.id_usuario, anomes=ultimo, categoria=None),
                )
            )
    da_faixa = sorted(
        (r for r in referencia_coorte if r.faixa_renda == faixa_ancora),
        key=lambda r: (-r.media, r.macro),
    )[:TRECHOS_COORTE]
    if not da_faixa:
        raise ErroDados(
            "Sem referência de coorte para a faixa do âncora; FR-016 exige ao menos um "
            "trecho de coorte."
        )
    for indice, ref in enumerate(da_faixa):
        trechos.append(
            Trecho(
                doc_id=f"{TipoDocumento.COORTE.value}:{ref.faixa_renda}:{_slug(ref.macro)}",
                tipo=TipoDocumento.COORTE.value,
                anomes=None,
                texto=(
                    f"Clientes com renda {ROTULO_FAIXA[ref.faixa_renda]} gastam em média "
                    f"{_reais(ref.media)}/mês com {ref.macro} (mediana {_reais(ref.mediana)}, "
                    f"{ref.qtd_usuarios} clientes)."
                ),
                score=round(0.70 - 0.01 * indice, 4),
                origem=Origem(id_usuario=None, anomes=None, categoria=ref.macro),
            )
        )
    return sorted(trechos, key=lambda t: (-t.score, t.doc_id))


# ---------------------------------------------------------------------------
# Conjunto completo, validação e gravação
# ---------------------------------------------------------------------------


def calcular_usuarios(
    perfil: Sequence[PerfilMes], id_ancora: str = ID_ANCORA, id_controle: str = ID_CONTROLE
) -> list[UsuarioFixture]:
    """``usuarios.json``: faixa de renda pela renda média de todos os meses lidos."""
    usuarios = []
    for id_usuario, papel in ((id_ancora, "ancora"), (id_controle, "controle")):
        rendas = [p.renda for p in perfil if p.id_usuario == id_usuario]
        if not rendas:
            raise ErroDados(f"Sem perfil mensal para o usuário {papel}.")
        usuarios.append(
            UsuarioFixture(
                id_usuario=id_usuario,
                papel=papel,
                faixa_renda=faixa_renda(statistics.fmean(rendas)),
            )
        )
    return usuarios


def _json_linhas(linhas: Iterable[BaseModel]) -> list[dict[str, Any]]:
    return [linha.model_dump(mode="json") for linha in linhas]


def gerar_conjunto(
    lancamentos: Sequence[Lancamento],
    pares_categorias: Iterable[tuple[str, str]],
    linhas_coorte: Iterable[LinhaCoorte],
    *,
    id_ancora: str = ID_ANCORA,
    id_controle: str = ID_CONTROLE,
) -> dict[str, Any]:
    """Todas as fixtures (caminho relativo → objeto JSON), sem I/O.

    Layout de contratos §8: ``usuarios.json``, ``bussola_dados/<tabela>.json``,
    ``ferramentas/<ferramenta>__ate_<corte>.json``, ``ferramentas/resumo_mes__<AAAAMM>.json``
    e ``rag/trechos_exemplo.json``.
    """
    id_ancora, id_controle = id_ancora.lower(), id_controle.lower()
    validos = validar_lancamentos(lancamentos, (id_ancora, id_controle))
    tabelas = calcular_tabelas(validos, pares_categorias, linhas_coorte)
    usuarios = calcular_usuarios(tabelas["perfil_mensal"], id_ancora, id_controle)
    ancora = DadosUsuario.de_tabelas(tabelas, id_ancora)
    controle = DadosUsuario.de_tabelas(tabelas, id_controle)
    categorias = tabelas["categorias"]
    trechos = gerar_trechos(
        [ancora, controle], tabelas["referencia_coorte"], id_ancora, usuarios[0].faixa_renda
    )

    conjunto: dict[str, Any] = {"usuarios.json": _json_linhas(usuarios)}
    for nome in TABELAS_DADOS:
        conjunto[f"bussola_dados/{nome}.json"] = _json_linhas(tabelas[nome])
    for corte in CORTES_GOLDEN:
        golden = {
            "perfil_financeiro": golden_perfil_financeiro(ancora, corte),
            "capacidade_poupanca": golden_capacidade_poupanca(ancora, corte),
            "oportunidades_corte": golden_oportunidades_corte(ancora, categorias, corte),
            "dividas_e_parcelas": golden_dividas_e_parcelas(ancora, corte),
            "simular_objetivo": golden_simular_objetivo(ancora, corte),
            "comparar_cenarios": golden_comparar_cenarios(ancora, categorias, corte),
            "buscar_contexto_financeiro": golden_buscar_contexto(ancora, trechos, corte),
        }
        for ferramenta in FERRAMENTAS_P0:
            conjunto[f"ferramentas/{arquivo_golden(ferramenta, corte)}"] = golden[ferramenta]
    for mes in range(1, 13):
        anomes = (ANOMES_MIN // 100) * 100 + mes
        conjunto[f"ferramentas/{arquivo_resumo_mes(anomes)}"] = golden_resumo_mes(ancora, anomes)
    conjunto["rag/trechos_exemplo.json"] = _json_linhas(trechos)
    return dict(sorted(conjunto.items()))


def _validar_lista(modelo: type[BaseModel], obj: Any, caminho: str) -> None:
    if not isinstance(obj, list):
        raise ErroDados(f"{caminho}: esperado uma lista de linhas.")
    for linha in obj:
        modelo.model_validate(linha)


def validar_conjunto(conjunto: Mapping[str, Any]) -> None:
    """Valida cada arquivo com o modelo de ``bussola_mcp.contratos`` correspondente.

    Levanta ``pydantic.ValidationError`` ou :class:`ErroDados` (caminho desconhecido ou
    golden com mais de 10 itens).
    """
    for caminho, obj in conjunto.items():
        pasta, _, arquivo = caminho.rpartition("/")
        nome = arquivo.removesuffix(".json")
        if caminho == "usuarios.json":
            _validar_lista(UsuarioFixture, obj, caminho)
        elif caminho == "rag/trechos_exemplo.json":
            _validar_lista(Trecho, obj, caminho)
        elif pasta == "bussola_dados" and f"bussola_dados.{nome}" in MODELOS_TABELA:
            _validar_lista(MODELOS_TABELA[f"bussola_dados.{nome}"], obj, caminho)
        elif pasta == "ferramentas" and nome.partition("__")[0] in FERRAMENTAS:
            ferramenta = nome.partition("__")[0]
            resposta = Resposta[FERRAMENTAS[ferramenta][1]].model_validate(obj)
            if resposta.fonte.ferramenta != ferramenta:
                raise ErroDados(f"{caminho}: fonte.ferramenta não confere com o arquivo.")
            itens = getattr(resposta.dados, "categorias", None) or getattr(
                resposta.dados, "trechos", None
            )
            if itens is not None and len(itens) > TOP_MAX:
                raise ErroDados(f"{caminho}: mais de {TOP_MAX} itens.")
        else:
            raise ErroDados(f"Caminho de fixture fora do layout de contratos §8: {caminho}.")


def serializar(obj: Any) -> str:
    """JSON determinístico: chaves ordenadas, indentação 2, sem escapar acentos, ``\\n`` final."""
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def gravar(saida: Path | str, conjunto: Mapping[str, Any]) -> list[Path]:
    """Grava o conjunto em ``saida`` (UTF-8) e devolve os caminhos gravados."""
    base = Path(saida)
    caminhos: list[Path] = []
    for relativo, obj in sorted(conjunto.items()):
        destino = base / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(serializar(obj), encoding="utf-8")
        caminhos.append(destino)
    return caminhos


# ---------------------------------------------------------------------------
# CLI (única parte com I/O e BigQuery)
# ---------------------------------------------------------------------------


def _criar_cliente_bigquery(projeto: str) -> Any:
    from google.cloud import bigquery

    return bigquery.Client(project=projeto)


def consultar(cliente: Any, sql: str, parametros: Sequence[Any]) -> list[Any]:
    """Executa ``sql`` com parâmetros nomeados e devolve as linhas."""
    from google.cloud import bigquery

    config = bigquery.QueryJobConfig(query_parameters=list(parametros))
    return list(cliente.query(sql, job_config=config).result())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gerar_fixtures.py",
        description=(
            "Gera as fixtures provisórias de contracts/fixtures/ (contratos §8) a partir de "
            f"{TABELA_ORIGEM}, com SQL parametrizado e ADC."
        ),
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="diretório de saída (padrão: contracts/fixtures na raiz do repositório)",
    )
    parser.add_argument(
        "--projeto",
        default=None,
        help="projeto GCP dos jobs (padrão: variável GOOGLE_CLOUD_PROJECT)",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    criar_cliente: Callable[[str], Any] = _criar_cliente_bigquery,
) -> int:
    args = _parser().parse_args(argv)
    projeto = args.projeto or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not projeto:
        print("Erro: informe --projeto ou defina GOOGLE_CLOUD_PROJECT.", file=sys.stderr)
        return 2
    cliente = criar_cliente(projeto)
    try:
        lancamentos = [
            lancamento_de_linha(linha)
            for linha in consultar(cliente, SQL_EXTRATO, parametros_extrato())
        ]
        pares = [
            (str(linha["macro"]), str(linha["micro"]))
            for linha in consultar(cliente, SQL_CATEGORIAS, parametros_periodo())
        ]
        coorte = [
            linha_coorte_de(linha) for linha in consultar(cliente, SQL_COORTE, parametros_periodo())
        ]
        conjunto = gerar_conjunto(lancamentos, pares, coorte)
        validar_conjunto(conjunto)
    except ErroDados as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    caminhos = gravar(args.saida, conjunto)
    print(
        f"{len(caminhos)} arquivos gravados em {args.saida} "
        f"({len(lancamentos)} lançamentos lidos). Fixtures provisórias (contratos §8)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
