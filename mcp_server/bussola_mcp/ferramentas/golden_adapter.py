"""Provisional ``FinancialComputations`` adapter backed by the golden fixtures.

No longer wired: since cycle 001 merged, ``computations.build_computations``
returns ``DomainComputations`` in every mode. This adapter only remains for the
tests of its own rules (D-03 to D-06 of the spec) until it is removed. It
serves the golden envelopes of ``contracts/fixtures/ferramentas/``
(contratos §8) and computes nothing: it only picks the golden that matches the
request, without leaking data after the cut or data of another client.

Rules:

1. only the anchor client of ``usuarios.json`` has goldens (``gerar_fixtures``
   records them for the anchor alone); any other client is computed by
   :class:`~bussola_mcp.ferramentas.computations.DomainComputations` over the
   same repository, so having no golden is never mistaken for having no
   history (BUG-05);
2. no month of ``perfil_mensal`` up to ``ate_anomes`` → ``DADOS_INSUFICIENTES``,
   the only honest reason for that code here (same rule as ``metricas``);
3. cut 202506 or 202512 → exact golden; 202507–202511 → the 202506 golden
   with a warning (period ends at 202506); before 202506 → ``INDISPONIVEL``;
   rules 3 to 5 apply to the anchor only, since only it is served a golden;
4. simulations with a non-canonical input get the canonical golden plus a
   warning;
5. ``oportunidades_corte`` is truncated to ``top_n``;
6. ``resumo_mes`` reads ``resumo_mes__<anomes>.json``;
7. ``referencia_coorte`` looks up the client's income band in the repository;
8. a missing or invalid file → :class:`BackendUnavailable` (``INDISPONIVEL``).

Only successful loads are cached. Delete this module when
``computations.build_computations`` switches to the domain adapter.
"""

import unicodedata
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS,
    CodigoErro,
    DadosOportunidadesCorte,
    DadosReferenciaCoorte,
    DadosResumoMes,
    Periodo,
    Resposta,
    UsuarioFixture,
    arquivo_golden,
    arquivo_resumo_mes,
    brl,
)
from bussola_mcp.dominio.fakes import carregar_usuarios, ler_json, resolver_dir_fixtures
from bussola_mcp.dominio.interfaces import RepositorioFinanceiro
from bussola_mcp.ferramentas.computations import DomainComputations
from bussola_mcp.ferramentas.fixture_backends import MISSING_FIXTURES_MESSAGE
from bussola_mcp.ferramentas.ports import BackendUnavailable, Computation, DomainError

GOLDEN_DIR = "ferramentas"
PARTIAL_CUT, FINAL_CUT = CORTES_GOLDEN
CANONICAL_TARGET = float(ENTRADA_CANONICA_SIMULACAO["valor_alvo"])
CANONICAL_TERM = int(ENTRADA_CANONICA_SIMULACAO["prazo_meses"])

CUT_UNAVAILABLE_MESSAGE = "Dados de exemplo indisponíveis para este corte."
MONTH_UNAVAILABLE_MESSAGE = "Não há dados deste mês para o cliente."
NO_BAND_MESSAGE = "Faixa de renda do cliente indisponível."
NO_REFERENCE_MESSAGE = "Sem referência da faixa de renda para esta categoria."

MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def month_label(anomes: int) -> str:
    """``202506`` → ``"junho/2025"``: mês em pt-BR, nunca o ``anomes`` cru ao cliente."""
    return f"{MONTH_NAMES[anomes % 100 - 1]}/{anomes // 100}"


def brl_label(valor: float) -> str:
    """``30000.0`` → ``"R$ 30.000,00"``: valor em BRL com 2 casas, no formato pt-BR."""
    inteiro, _, centavos = f"{brl(valor):,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


DEMO_WARNING_PREFIX = "Exemplo desta demonstração:"
"""Prefixo estável dos avisos de dado gravado, para o front apresentá-los juntos (BUG-06)."""

EARLIER_CUT_WARNING = f"{DEMO_WARNING_PREFIX} números com dados até {month_label(PARTIAL_CUT)}."
CANONICAL_INPUT_WARNING = (
    f"{DEMO_WARNING_PREFIX} simulação para uma meta de {brl_label(CANONICAL_TARGET)} "
    f"em {CANONICAL_TERM} meses."
)
COHORT_WARNING = (
    "Referência agregada de 2025 de clientes da mesma faixa de renda, sem dado individual."
)


def normalize_label(texto: str) -> str:
    """Case- and accent-insensitive key for category names."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sem_acento.casefold().split())


class GoldenFixtureComputations:
    """Implements ``FinancialComputations`` by selecting golden envelopes."""

    def __init__(self, fixtures_dir: Path | str | None, repository: RepositorioFinanceiro) -> None:
        self.fixtures_dir = resolver_dir_fixtures(fixtures_dir)
        self.repository = repository
        self.domain = DomainComputations(repository)
        """Cálculo de domínio dos clientes sem golden gravado (rule 1)."""
        self._users: dict[str, UsuarioFixture] | None = None
        self._goldens: dict[str, Resposta[Any]] = {}

    # -- fixtures --------------------------------------------------------------

    def _load_users(self) -> dict[str, UsuarioFixture]:
        if self._users is None:
            try:
                users = carregar_usuarios(self.fixtures_dir)
            except (OSError, ValueError) as exc:
                raise BackendUnavailable(MISSING_FIXTURES_MESSAGE) from exc
            if users is None:
                raise BackendUnavailable(MISSING_FIXTURES_MESSAGE)
            self._users = users
        return self._users

    def _load_golden(self, file_name: str, dados: type[BaseModel]) -> Resposta[Any]:
        if file_name not in self._goldens:
            try:
                content = ler_json(self.fixtures_dir / GOLDEN_DIR / file_name)
                if content is None:
                    raise BackendUnavailable(MISSING_FIXTURES_MESSAGE)
                self._goldens[file_name] = Resposta[dados].model_validate(content)
            except (OSError, ValueError) as exc:
                raise BackendUnavailable(MISSING_FIXTURES_MESSAGE) from exc
        return self._goldens[file_name]

    # -- rules -----------------------------------------------------------------

    def has_golden(self, id_usuario: str) -> bool:
        """Whether a golden was recorded for the client: only the anchor has one (rule 1)."""
        user = self._load_users().get(id_usuario.lower())
        return user is not None and user.papel == "ancora"

    def _months(self, id_usuario: str, ate_anomes: int) -> list[int]:
        """Months of ``perfil_mensal`` available up to the cut; none → ``DADOS_INSUFICIENTES``."""
        months = [linha.anomes for linha in self.repository.perfil_mensal(id_usuario, ate_anomes)]
        if not months:
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES)
        return months

    @staticmethod
    def _golden_cut(ate_anomes: int) -> tuple[int, tuple[str, ...]]:
        """Golden cut to serve and its warnings (rule 3)."""
        if ate_anomes in CORTES_GOLDEN:
            return ate_anomes, ()
        if PARTIAL_CUT < ate_anomes < FINAL_CUT:
            return PARTIAL_CUT, (EARLIER_CUT_WARNING,)
        raise BackendUnavailable(CUT_UNAVAILABLE_MESSAGE)

    def _from_golden(self, ferramenta: str, id_usuario: str, ate_anomes: int) -> Computation:
        self._months(id_usuario, ate_anomes)
        corte, avisos = self._golden_cut(ate_anomes)
        golden = self._load_golden(arquivo_golden(ferramenta, corte), FERRAMENTAS[ferramenta][1])
        computation = Computation(
            dados=golden.dados, periodo=golden.fonte.periodo, avisos=tuple(golden.avisos)
        )
        return computation.with_avisos(*avisos)

    # -- FinancialComputations -------------------------------------------------
    #
    # Sem golden gravado (rule 1), o cálculo vai para ``self.domain``: o cliente
    # tem histórico, só não tem envelope gravado.

    def perfil_financeiro(self, id_usuario: str, ate_anomes: int) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.perfil_financeiro(id_usuario, ate_anomes)
        return self._from_golden("perfil_financeiro", id_usuario, ate_anomes)

    def capacidade_poupanca(self, id_usuario: str, ate_anomes: int) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.capacidade_poupanca(id_usuario, ate_anomes)
        return self._from_golden("capacidade_poupanca", id_usuario, ate_anomes)

    def oportunidades_corte(self, id_usuario: str, ate_anomes: int, top_n: int) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.oportunidades_corte(id_usuario, ate_anomes, top_n)
        computation = self._from_golden("oportunidades_corte", id_usuario, ate_anomes)
        dados = computation.dados
        assert isinstance(dados, DadosOportunidadesCorte)
        truncated = dados.model_copy(update={"categorias": dados.categorias[:top_n]})
        return Computation(dados=truncated, periodo=computation.periodo, avisos=computation.avisos)

    def dividas_e_parcelas(self, id_usuario: str, ate_anomes: int) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.dividas_e_parcelas(id_usuario, ate_anomes)
        return self._from_golden("dividas_e_parcelas", id_usuario, ate_anomes)

    def simular_objetivo(
        self,
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int | None,
        aporte_mensal: float | None,
        usar_saldo_atual: bool,
    ) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.simular_objetivo(
                id_usuario, ate_anomes, valor_alvo, prazo_meses, aporte_mensal, usar_saldo_atual
            )
        computation = self._from_golden("simular_objetivo", id_usuario, ate_anomes)
        canonical = (
            valor_alvo == CANONICAL_TARGET
            and prazo_meses == CANONICAL_TERM
            and aporte_mensal is None
            and not usar_saldo_atual
        )
        return computation if canonical else computation.with_avisos(CANONICAL_INPUT_WARNING)

    def comparar_cenarios(
        self, id_usuario: str, ate_anomes: int, valor_alvo: float, prazo_meses: int
    ) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.comparar_cenarios(id_usuario, ate_anomes, valor_alvo, prazo_meses)
        computation = self._from_golden("comparar_cenarios", id_usuario, ate_anomes)
        canonical = valor_alvo == CANONICAL_TARGET and prazo_meses == CANONICAL_TERM
        return computation if canonical else computation.with_avisos(CANONICAL_INPUT_WARNING)

    def resumo_mes(self, id_usuario: str, ate_anomes: int, anomes: int) -> Computation:
        if not self.has_golden(id_usuario):
            return self.domain.resumo_mes(id_usuario, ate_anomes, anomes)
        months = self._months(id_usuario, ate_anomes)
        if anomes not in months:
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES, MONTH_UNAVAILABLE_MESSAGE)
        golden = self._load_golden(arquivo_resumo_mes(anomes), DadosResumoMes)
        return Computation(
            dados=golden.dados, periodo=golden.fonte.periodo, avisos=tuple(golden.avisos)
        )

    def referencia_coorte(self, id_usuario: str, ate_anomes: int, categoria: str) -> Computation:
        user = self._load_users().get(id_usuario.lower())
        if user is None:
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES, NO_BAND_MESSAGE)
        months = [linha.anomes for linha in self.repository.perfil_mensal(id_usuario, ate_anomes)]
        if not months:
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES)
        wanted = normalize_label(categoria)
        rows = [
            ref
            for ref in self.repository.referencia_coorte(user.faixa_renda)
            if normalize_label(ref.macro) == wanted
        ]
        if not rows:
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES, NO_REFERENCE_MESSAGE)
        ref = rows[0]
        dados = DadosReferenciaCoorte(
            faixa_renda=ref.faixa_renda,
            macro=ref.macro,
            media=brl(ref.media),
            mediana=brl(ref.mediana),
            qtd_usuarios=ref.qtd_usuarios,
        )
        return Computation(
            dados=dados,
            periodo=Periodo(inicio=min(months), fim=ate_anomes),
            avisos=(COHORT_WARNING,),
        )

    def planejar_marcos(
        self,
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int,
        prioridade: str | None,
        usar_saldo_atual: bool,
    ) -> Computation:
        """Sempre pelo domínio: o 009 não tem golden gravado para nenhum cliente.

        ``gerar_fixtures.py`` grava goldens só das ferramentas de
        ``FERRAMENTAS_GOLDEN``, e ``planejar_marcos`` não está entre elas, então
        aqui não há corte nem entrada canônica a servir.
        """
        return self.domain.planejar_marcos(
            id_usuario, ate_anomes, valor_alvo, prazo_meses, prioridade, usar_saldo_atual
        )
