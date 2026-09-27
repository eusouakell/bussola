"""Provisional ``FinancialComputations`` adapter backed by the golden fixtures.

No longer wired: since cycle 001 merged, ``computations.build_computations``
returns ``DomainComputations`` in every mode. This adapter only remains for the
tests of its own rules (D-03 to D-06 of the spec) until it is removed. It
serves the golden envelopes of ``contracts/fixtures/ferramentas/``
(contratos §8) and computes nothing: it only picks the golden that matches the
request, without leaking data after the cut or data of another client.

Rules:

1. only the anchor client of ``usuarios.json`` has goldens; any other known
   client gets ``DADOS_INSUFICIENTES``;
2. no month of ``perfil_mensal`` up to ``ate_anomes`` → ``DADOS_INSUFICIENTES``;
3. cut 202506 or 202512 → exact golden; 202507–202511 → the 202506 golden
   with a warning (period ends at 202506); before 202506 → ``INDISPONIVEL``;
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
from bussola_mcp.ferramentas.fixture_backends import MISSING_FIXTURES_MESSAGE
from bussola_mcp.ferramentas.ports import BackendUnavailable, Computation, DomainError

GOLDEN_DIR = "ferramentas"
PARTIAL_CUT, FINAL_CUT = CORTES_GOLDEN
CANONICAL_TARGET = float(ENTRADA_CANONICA_SIMULACAO["valor_alvo"])
CANONICAL_TERM = int(ENTRADA_CANONICA_SIMULACAO["prazo_meses"])

ONLY_ANCHOR_MESSAGE = "Dados de exemplo disponíveis só para o cliente âncora."
CUT_UNAVAILABLE_MESSAGE = "Dados de exemplo indisponíveis para este corte."
MONTH_UNAVAILABLE_MESSAGE = "Não há dados deste mês para o cliente."
NO_BAND_MESSAGE = "Faixa de renda do cliente indisponível."
NO_REFERENCE_MESSAGE = "Sem referência da faixa de renda para esta categoria."

EARLIER_CUT_WARNING = f"Resposta de exemplo calculada com dados até {PARTIAL_CUT}."
CANONICAL_INPUT_WARNING = (
    f"Resposta de exemplo calculada para valor_alvo={CANONICAL_TARGET:g} "
    f"e prazo_meses={CANONICAL_TERM}."
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

    def _anchor_months(self, id_usuario: str, ate_anomes: int) -> list[int]:
        """Months available up to the cut, only for the anchor client (rules 1–2)."""
        user = self._load_users().get(id_usuario.lower())
        if user is None or user.papel != "ancora":
            raise DomainError(CodigoErro.DADOS_INSUFICIENTES, ONLY_ANCHOR_MESSAGE)
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
        self._anchor_months(id_usuario, ate_anomes)
        corte, avisos = self._golden_cut(ate_anomes)
        golden = self._load_golden(arquivo_golden(ferramenta, corte), FERRAMENTAS[ferramenta][1])
        computation = Computation(
            dados=golden.dados, periodo=golden.fonte.periodo, avisos=tuple(golden.avisos)
        )
        return computation.with_avisos(*avisos)

    # -- FinancialComputations -------------------------------------------------

    def perfil_financeiro(self, id_usuario: str, ate_anomes: int) -> Computation:
        return self._from_golden("perfil_financeiro", id_usuario, ate_anomes)

    def capacidade_poupanca(self, id_usuario: str, ate_anomes: int) -> Computation:
        return self._from_golden("capacidade_poupanca", id_usuario, ate_anomes)

    def oportunidades_corte(self, id_usuario: str, ate_anomes: int, top_n: int) -> Computation:
        computation = self._from_golden("oportunidades_corte", id_usuario, ate_anomes)
        dados = computation.dados
        assert isinstance(dados, DadosOportunidadesCorte)
        truncated = dados.model_copy(update={"categorias": dados.categorias[:top_n]})
        return Computation(dados=truncated, periodo=computation.periodo, avisos=computation.avisos)

    def dividas_e_parcelas(self, id_usuario: str, ate_anomes: int) -> Computation:
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
        computation = self._from_golden("comparar_cenarios", id_usuario, ate_anomes)
        canonical = valor_alvo == CANONICAL_TARGET and prazo_meses == CANONICAL_TERM
        return computation if canonical else computation.with_avisos(CANONICAL_INPUT_WARNING)

    def resumo_mes(self, id_usuario: str, ate_anomes: int, anomes: int) -> Computation:
        months = self._anchor_months(id_usuario, ate_anomes)
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
