"""Single wiring point of the ``FinancialComputations`` port.

Today it returns :class:`GoldenFixtureComputations`, because
``dominio/metricas.py`` and ``dominio/simulacao.py`` (cycle 001) are not in
``main`` yet.

Swap after cycle 001 merges (this file only; see ``specs/003-*/plan.md``):

1. add ``DomainComputations(repository)`` here, implementing
   ``FinancialComputations`` with ``metricas.*`` and ``simulacao.*``
   (``aporte_para_prazo`` / ``prazo_para_meta`` for ``simular_objetivo``,
   ``gerar_cenarios`` for ``comparar_cenarios``), converting domain failures
   into ``DomainError`` (``DADOS_INSUFICIENTES``, ``PRAZO_IMPLAUSIVEL`` when the
   computed term exceeds 360 months);
2. make :func:`build_computations` return ``DomainComputations(repository)``.
"""

from pathlib import Path

from bussola_mcp.dominio.interfaces import RepositorioFinanceiro
from bussola_mcp.ferramentas.golden_adapter import GoldenFixtureComputations
from bussola_mcp.ferramentas.ports import FinancialComputations


def build_computations(
    repository: RepositorioFinanceiro, fixtures_dir: Path | str | None = None
) -> FinancialComputations:
    """Adapter of the computation port used by the server, in every mode."""
    return GoldenFixtureComputations(fixtures_dir, repository)
