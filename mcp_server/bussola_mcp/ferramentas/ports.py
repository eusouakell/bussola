"""Ports of the tool layer (ports & adapters).

The tools depend only on these abstractions:

- ``RepositorioFinanceiro`` and ``BuscadorContexto`` (contract, ``dominio/interfaces.py``);
- :class:`FinancialComputations`, owned by cycle 003, which mirrors the
  metrics and simulation functions of contratos §4 (``dominio/metricas.py`` and
  ``dominio/simulacao.py``, cycle 001).

Each computation returns a :class:`Computation` with the ``dados`` model of the
tool, the period actually considered and the deterministic warnings. Domain
failures are raised as :class:`DomainError` (mapped to a contract error code)
and backend failures as :class:`BackendUnavailable` (mapped to
``INDISPONIVEL``). The tool runner turns both into the error envelope; they
never reach the MCP client as exceptions.
"""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from bussola_mcp.contratos import CodigoErro, Periodo
from bussola_mcp.dominio.interfaces import BuscadorContexto, RepositorioFinanceiro


@dataclass(frozen=True)
class Computation:
    """Result of a computation: ``dados`` of the tool, period and warnings."""

    dados: BaseModel
    periodo: Periodo
    avisos: tuple[str, ...] = field(default=())

    def with_avisos(self, *avisos: str) -> "Computation":
        """Copy with extra warnings appended (no duplicates, order kept)."""
        merged = list(self.avisos)
        for aviso in avisos:
            if aviso not in merged:
                merged.append(aviso)
        return Computation(dados=self.dados, periodo=self.periodo, avisos=tuple(merged))


class DomainError(Exception):
    """Domain outcome that maps to a contract error code (never ``INDISPONIVEL``)."""

    def __init__(self, codigo: CodigoErro, mensagem: str | None = None) -> None:
        super().__init__(codigo.value)
        self.codigo = codigo
        self.mensagem = mensagem


class BackendUnavailable(Exception):
    """Data or search backend failed. The detail goes only to the log."""

    def __init__(self, mensagem: str | None = None) -> None:
        super().__init__(mensagem or "backend indisponível")
        self.mensagem = mensagem


@runtime_checkable
class FinancialComputations(Protocol):
    """One method per data tool of contratos §5.

    Mapping to contratos §4 (cycle 001):

    - ``perfil_financeiro``, ``capacidade_poupanca``, ``oportunidades_corte``,
      ``dividas_e_parcelas``, ``resumo_mes`` and ``referencia_coorte`` →
      ``metricas.<same name>`` over the repository rows;
    - ``simular_objetivo`` → ``simulacao.aporte_para_prazo`` (``prazo_meses``
      given) or ``simulacao.prazo_para_meta`` (``aporte_mensal`` given; a
      computed term above 360 months raises ``DomainError(PRAZO_IMPLAUSIVEL)``);
    - ``comparar_cenarios`` → ``simulacao.gerar_cenarios``;
    - ``planejar_marcos`` → ``marcos.contexto_de_perfil`` + ``marcos.planejar``
      sobre as linhas do repositório (ciclo 009).

    Inputs arrive already validated by the ``Entrada*`` models. Every read is
    scoped by ``id_usuario`` and cut at ``ate_anomes``.
    """

    def perfil_financeiro(self, id_usuario: str, ate_anomes: int) -> Computation: ...

    def capacidade_poupanca(self, id_usuario: str, ate_anomes: int) -> Computation: ...

    def oportunidades_corte(self, id_usuario: str, ate_anomes: int, top_n: int) -> Computation: ...

    def dividas_e_parcelas(self, id_usuario: str, ate_anomes: int) -> Computation: ...

    def simular_objetivo(
        self,
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int | None,
        aporte_mensal: float | None,
        usar_saldo_atual: bool,
    ) -> Computation: ...

    def comparar_cenarios(
        self, id_usuario: str, ate_anomes: int, valor_alvo: float, prazo_meses: int
    ) -> Computation: ...

    def resumo_mes(self, id_usuario: str, ate_anomes: int, anomes: int) -> Computation: ...

    def referencia_coorte(
        self, id_usuario: str, ate_anomes: int, categoria: str
    ) -> Computation: ...

    def planejar_marcos(
        self,
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int,
        prioridade: str | None,
        usar_saldo_atual: bool,
    ) -> Computation: ...


@dataclass(frozen=True)
class ToolDependencies:
    """Adapters injected into the tools by the server factory."""

    repository: RepositorioFinanceiro
    searcher: BuscadorContexto
    computations: FinancialComputations
