"""Modelos Pydantic de I/O: contratos v1 (docs/ciclos/contratos.md §3, §5, §8).

Código de contrato (constituição X): mudanças só via PR ``contracts: <mudança>``,
sempre aditivas.

- Linhas de tabela (§3) espelham o DDL de ``contracts/bigquery/*.sql``.
- Entradas das ferramentas (§5) validam formato e faixas. A validação falha com
  ``pydantic.ValidationError``, que as ferramentas convertem no envelope
  ``ENTRADA_INVALIDA`` via :func:`mensagem_entrada_invalida`.
- ``dados`` de cada ferramenta e os envelopes de sucesso e de erro.
"""

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# Constantes do contrato
# ---------------------------------------------------------------------------

ANOMES_MIN = 202501
ANOMES_MAX = 202512

ID_ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"
ID_CONTROLE = "31e94f2f-1463-49f9-a41a-b3f220ed976a"

UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def id_usuario_valido(valor: object) -> bool:
    """True se ``valor`` é uma string UUID v4 (sem diferenciar maiúsculas)."""
    return isinstance(valor, str) and UUID_V4_RE.fullmatch(valor) is not None


def normalizar_id_usuario(valor: str) -> str:
    """Valida o UUID v4 e devolve em minúsculas. Levanta ``ValueError`` sem ecoar o valor."""
    if not id_usuario_valido(valor):
        raise ValueError("id_usuario deve ser um UUID v4")
    return valor.lower()


def anomes_valido(valor: object) -> bool:
    return (
        isinstance(valor, int) and not isinstance(valor, bool) and ANOMES_MIN <= valor <= ANOMES_MAX
    )


def brl(valor: float) -> float:
    """Valor monetário em BRL com 2 casas (contratos §0)."""
    return round(float(valor), 2)


class CodigoErro(StrEnum):
    USUARIO_INEXISTENTE = "USUARIO_INEXISTENTE"
    ENTRADA_INVALIDA = "ENTRADA_INVALIDA"
    PRAZO_IMPLAUSIVEL = "PRAZO_IMPLAUSIVEL"
    DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"
    INDISPONIVEL = "INDISPONIVEL"


MENSAGENS_ERRO: dict[CodigoErro, str] = {
    CodigoErro.USUARIO_INEXISTENTE: "Cliente não encontrado.",
    CodigoErro.ENTRADA_INVALIDA: "Entrada inválida.",
    CodigoErro.PRAZO_IMPLAUSIVEL: "Prazo implausível para o objetivo informado.",
    CodigoErro.DADOS_INSUFICIENTES: "Dados insuficientes para esta análise.",
    CodigoErro.INDISPONIVEL: "Serviço temporariamente indisponível.",
}


class FaixaRenda(StrEnum):
    ATE_3K = "ate_3k"
    DE_3K_A_6K = "3k_6k"
    DE_6K_A_10K = "6k_10k"
    DE_10K_A_20K = "10k_20k"
    ACIMA_20K = "acima_20k"


class TipoDocumento(StrEnum):
    FICHA_MENSAL = "ficha_mensal"
    PERFIL_ANUAL = "perfil_anual"
    COORTE = "coorte"
    LANCAMENTO = "lancamento"


class _Modelo(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


# ---------------------------------------------------------------------------
# §3 bussola_dados: linhas de tabela (espelham o DDL)
# ---------------------------------------------------------------------------


class PerfilMes(_Modelo):
    id_usuario: str
    anomes: int
    renda: float
    gasto: float
    sobra: float
    saldo_inicial: float
    saldo_final: float
    saldo_minimo: float
    saldo_maximo: float
    juros: float


class GastoCategoria(_Modelo):
    id_usuario: str
    anomes: int
    macro: str
    micro: str
    total: float
    qtd: int


class EntradaCategoria(_Modelo):
    id_usuario: str
    anomes: int
    macro: str
    micro: str
    total: float
    qtd: int


class Recorrente(_Modelo):
    id_usuario: str
    anomes: int
    descr_norm: str
    macro: str
    micro: str
    valor: float


class Parcela(_Modelo):
    id_usuario: str
    anomes: int
    descr: str
    macro: str
    parcela_atual: int
    parcela_total: int
    vlr: float


class Categoria(_Modelo):
    macro: str
    micro: str
    discricionaria: bool
    corte_max_pct: float


class RefCoorte(_Modelo):
    faixa_renda: str
    macro: str
    media: float
    mediana: float
    qtd_usuarios: int


# §3 bussola_rag


class Documento(_Modelo):
    doc_id: str
    id_usuario: str | None
    tipo: str
    anomes: int | None
    texto: str
    fonte: dict[str, Any]
    embedding: list[float]
    modelo_embedding: str
    gerado_em: datetime


# Tabela (dataset.tabela) → modelo de linha. Base do teste DDL ↔ Pydantic.
MODELOS_TABELA: dict[str, type[_Modelo]] = {
    "bussola_dados.perfil_mensal": PerfilMes,
    "bussola_dados.gastos_categoria": GastoCategoria,
    "bussola_dados.entradas_categoria": EntradaCategoria,
    "bussola_dados.recorrentes": Recorrente,
    "bussola_dados.parcelas": Parcela,
    "bussola_dados.categorias": Categoria,
    "bussola_dados.referencia_coorte": RefCoorte,
    "bussola_rag.documentos": Documento,
}

# ---------------------------------------------------------------------------
# §5 envelopes
# ---------------------------------------------------------------------------


class Periodo(_Modelo):
    inicio: int
    fim: int


class Fonte(_Modelo):
    ferramenta: str
    tabelas: list[str]
    periodo: Periodo


class Erro(_Modelo):
    codigo: CodigoErro
    mensagem: str


class RespostaErro(_Modelo):
    erro: Erro


class Resposta[D: BaseModel](_Modelo):
    dados: D
    fonte: Fonte
    avisos: list[str] = Field(default_factory=list)


def envelope_erro(codigo: CodigoErro, mensagem: str | None = None) -> dict[str, Any]:
    """Envelope de erro serializado (resultado da ferramenta, não exceção)."""
    erro = Erro(codigo=codigo, mensagem=mensagem or MENSAGENS_ERRO[codigo])
    return RespostaErro(erro=erro).model_dump(mode="json")


def mensagem_entrada_invalida(exc: ValidationError) -> str:
    """Mensagem de ``ENTRADA_INVALIDA`` que cita só nomes de campos e regras fixas.

    Nunca ecoa o valor recebido nem nomes de campos desconhecidos (constituição II/V).
    """
    campos: list[str] = []
    regras: list[str] = []
    for erro in exc.errors(include_input=False, include_url=False):
        if erro["type"] == "extra_forbidden":
            regra = "parâmetro não esperado"
            if regra not in regras:
                regras.append(regra)
            continue
        loc = [p for p in erro["loc"] if isinstance(p, str)]
        if loc:
            if loc[0] not in campos:
                campos.append(loc[0])
        elif erro["type"] == "value_error":
            regra = str(erro.get("ctx", {}).get("error", "")).strip()
            if regra and regra not in regras:
                regras.append(regra)
    partes = campos + regras
    if not partes:
        return MENSAGENS_ERRO[CodigoErro.ENTRADA_INVALIDA]
    return "Entrada inválida: " + "; ".join(partes) + "."


# ---------------------------------------------------------------------------
# §5 entradas das ferramentas
# ---------------------------------------------------------------------------

TextoPergunta = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]
TextoCategoria = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]


class EntradaComum(_Modelo):
    """Parâmetros comuns obrigatórios. O agente os sobrescreve a partir do session.state."""

    id_usuario: str
    ate_anomes: int

    @field_validator("id_usuario", mode="before")
    @classmethod
    def _validar_id_usuario(cls, valor: object) -> str:
        if not isinstance(valor, str):
            raise ValueError("id_usuario deve ser um UUID v4")
        return normalizar_id_usuario(valor)

    @field_validator("ate_anomes")
    @classmethod
    def _validar_ate_anomes(cls, valor: int) -> int:
        if not anomes_valido(valor):
            raise ValueError("ate_anomes deve estar entre 202501 e 202512")
        return valor


class EntradaPerfilFinanceiro(EntradaComum):
    pass


class EntradaCapacidadePoupanca(EntradaComum):
    pass


class EntradaOportunidadesCorte(EntradaComum):
    top_n: int = Field(default=5, ge=1, le=10)


class EntradaDividasParcelas(EntradaComum):
    pass


class EntradaSimularObjetivo(EntradaComum):
    valor_alvo: float = Field(gt=0)
    prazo_meses: int | None = Field(default=None, ge=1, le=360)
    aporte_mensal: float | None = Field(default=None, gt=0)
    usar_saldo_atual: bool = False

    @model_validator(mode="after")
    def _exatamente_um(self) -> "EntradaSimularObjetivo":
        if (self.prazo_meses is None) == (self.aporte_mensal is None):
            raise ValueError("informe exatamente um entre prazo_meses e aporte_mensal")
        return self


class EntradaCompararCenarios(EntradaComum):
    valor_alvo: float = Field(gt=0)
    prazo_meses: int = Field(ge=1, le=360)


class EntradaBuscarContexto(EntradaComum):
    pergunta: TextoPergunta
    k: int = Field(default=5, ge=1, le=10)


class EntradaResumoMes(EntradaComum):
    anomes: int

    @field_validator("anomes")
    @classmethod
    def _validar_anomes(cls, valor: int) -> int:
        if not anomes_valido(valor):
            raise ValueError("anomes deve estar entre 202501 e 202512")
        return valor

    @model_validator(mode="after")
    def _anomes_ate_corte(self) -> "EntradaResumoMes":
        if self.anomes > self.ate_anomes:
            raise ValueError("anomes deve ser menor ou igual a ate_anomes")
        return self


class EntradaReferenciaCoorte(EntradaComum):
    categoria: TextoCategoria


# ---------------------------------------------------------------------------
# §5 dados de cada ferramenta
# ---------------------------------------------------------------------------


class FonteRenda(_Modelo):
    macro: str
    micro: str
    media: float


class Saldo(_Modelo):
    minimo: float
    maximo: float
    atual: float


class PontoMensal(_Modelo):
    anomes: int
    renda: float
    gasto: float
    sobra: float


class DadosPerfilFinanceiro(_Modelo):
    renda_media: float
    gasto_medio: float
    sobra_media: float
    sobra_mediana: float
    fontes_renda: list[FonteRenda]
    saldo: Saldo
    serie_mensal: list[PontoMensal]
    meses_considerados: int


class DadosCapacidadePoupanca(_Modelo):
    sobra_media: float
    sobra_mediana: float
    desvio_padrao: float
    meses_negativos: int
    meses_considerados: int


class Oportunidade(_Modelo):
    macro: str
    micro: str
    media_mensal: float
    discricionaria: bool
    economia_potencial_mensal: float
    criterio: str


class DadosOportunidadesCorte(_Modelo):
    categorias: list[Oportunidade]


class ParcelaAtiva(_Modelo):
    descr: str
    parcela_atual: int
    parcela_total: int
    valor: float
    meses_restantes: int


class DadosDividasParcelas(_Modelo):
    parcelas_ativas: list[ParcelaAtiva]
    juros_pagos_media: float
    comprometimento_renda_pct: float


class DadosSimularObjetivo(_Modelo):
    """``modo="prazo"``: a entrada informou ``prazo_meses`` e o aporte é calculado.

    ``modo="aporte"``: a entrada informou ``aporte_mensal`` e o prazo é calculado.
    """

    modo: Literal["prazo", "aporte"]
    valor_alvo: float
    aporte_mensal: float
    prazo_meses: int
    viavel: bool
    folga_mensal: float
    premissas: dict[str, Any]


class RegrasCenario(_Modelo):
    """Regras dos cenários (contratos §4). É a proposta até a decisão da Q2 do mestre."""

    pct_capacidade: dict[str, float] = Field(
        default_factory=lambda: {"conservador": 0.40, "equilibrado": 0.60, "acelerado": 0.80}
    )
    base: Literal["sobra_mediana"] = "sobra_mediana"
    rendimento_mensal: float = 0.0
    saldo_inicial: float = 0.0
    cortes_no_acelerado: bool = True


class CorteSugerido(_Modelo):
    macro: str
    micro: str
    valor_mensal: float


class Cenario(_Modelo):
    nome: str
    pct_capacidade: float
    aporte_mensal: float
    prazo_meses: int
    viavel: bool
    cortes_sugeridos: list[CorteSugerido]
    trade_offs: list[str]


class DadosCompararCenarios(_Modelo):
    cenarios: list[Cenario]
    regras: RegrasCenario


class Origem(_Modelo):
    id_usuario: str | None
    anomes: int | None
    categoria: str | None


class Trecho(_Modelo):
    doc_id: str
    tipo: str
    anomes: int | None
    texto: str
    score: float
    origem: Origem


class DadosBuscarContexto(_Modelo):
    trechos: list[Trecho]


class GastoMacro(_Modelo):
    macro: str
    total: float


class DadosResumoMes(_Modelo):
    anomes: int
    renda: float
    gasto: float
    sobra: float
    gastos_macro: list[GastoMacro]


class DadosReferenciaCoorte(_Modelo):
    faixa_renda: str
    macro: str
    media: float
    mediana: float
    qtd_usuarios: int


# ---------------------------------------------------------------------------
# Catálogo de ferramentas (§5)
# ---------------------------------------------------------------------------

FERRAMENTAS: dict[str, tuple[type[EntradaComum], type[_Modelo]]] = {
    "perfil_financeiro": (EntradaPerfilFinanceiro, DadosPerfilFinanceiro),
    "capacidade_poupanca": (EntradaCapacidadePoupanca, DadosCapacidadePoupanca),
    "oportunidades_corte": (EntradaOportunidadesCorte, DadosOportunidadesCorte),
    "dividas_e_parcelas": (EntradaDividasParcelas, DadosDividasParcelas),
    "simular_objetivo": (EntradaSimularObjetivo, DadosSimularObjetivo),
    "comparar_cenarios": (EntradaCompararCenarios, DadosCompararCenarios),
    "buscar_contexto_financeiro": (EntradaBuscarContexto, DadosBuscarContexto),
    "resumo_mes": (EntradaResumoMes, DadosResumoMes),
    "referencia_coorte": (EntradaReferenciaCoorte, DadosReferenciaCoorte),
}

FERRAMENTAS_P0: tuple[str, ...] = (
    "perfil_financeiro",
    "capacidade_poupanca",
    "oportunidades_corte",
    "dividas_e_parcelas",
    "simular_objetivo",
    "comparar_cenarios",
    "buscar_contexto_financeiro",
)

# Ferramentas servidas pelo MCP mock do 000 (7 P0 + resumo_mes).
FERRAMENTAS_MOCK: tuple[str, ...] = (*FERRAMENTAS_P0, "resumo_mes")

# Tabelas citadas em ``fonte.tabelas`` por ferramenta (sugestão do 000; o 003 pode refinar).
TABELAS_FERRAMENTA: dict[str, list[str]] = {
    "perfil_financeiro": ["bussola_dados.perfil_mensal", "bussola_dados.entradas_categoria"],
    "capacidade_poupanca": ["bussola_dados.perfil_mensal"],
    "oportunidades_corte": ["bussola_dados.gastos_categoria", "bussola_dados.categorias"],
    "dividas_e_parcelas": ["bussola_dados.parcelas", "bussola_dados.perfil_mensal"],
    "simular_objetivo": ["bussola_dados.perfil_mensal"],
    "comparar_cenarios": [
        "bussola_dados.perfil_mensal",
        "bussola_dados.gastos_categoria",
        "bussola_dados.categorias",
    ],
    "buscar_contexto_financeiro": ["bussola_rag.documentos"],
    "resumo_mes": ["bussola_dados.perfil_mensal", "bussola_dados.gastos_categoria"],
    "referencia_coorte": ["bussola_dados.referencia_coorte"],
}

# ---------------------------------------------------------------------------
# §8 fixtures
# ---------------------------------------------------------------------------

CORTES_GOLDEN: tuple[int, int] = (202506, 202512)

# Entrada canônica dos golden de simulação (simular_objetivo / comparar_cenarios).
ENTRADA_CANONICA_SIMULACAO: dict[str, Any] = {"valor_alvo": 30000.0, "prazo_meses": 24}


class UsuarioFixture(_Modelo):
    """Linha de ``contracts/fixtures/usuarios.json``."""

    id_usuario: str
    papel: Literal["ancora", "controle"]
    faixa_renda: str


def arquivo_golden(ferramenta: str, corte: int) -> str:
    """Nome do golden P0: ``<ferramenta>__ate_<corte>.json``."""
    return f"{ferramenta}__ate_{corte}.json"


def arquivo_resumo_mes(anomes: int) -> str:
    """Nome do golden de ``resumo_mes``: ``resumo_mes__<AAAAMM>.json``."""
    return f"resumo_mes__{anomes}.json"
