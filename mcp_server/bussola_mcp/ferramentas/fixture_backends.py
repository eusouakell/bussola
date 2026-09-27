"""Fixture-backed adapters for fake mode (``BUSSOLA_FAKES=TRUE`` or ``--fixtures``).

They wrap the contract fakes (:mod:`bussola_mcp.dominio.fakes`) and add the
behaviour a server needs: a missing or invalid fixture file becomes
:class:`BackendUnavailable` (``INDISPONIVEL`` for the caller), instead of an
empty table. Only successful loads are cached, so a fixture created while the
server runs (``make fixtures``) starts being served.
"""

from collections.abc import Callable
from pathlib import Path

from bussola_mcp.contratos import (
    Categoria,
    EntradaCategoria,
    GastoCategoria,
    Parcela,
    PerfilMes,
    Recorrente,
    RefCoorte,
    TemaConhecimento,
    Trecho,
)
from bussola_mcp.dominio.fakes import (
    ARQUIVO_TRECHOS,
    ARQUIVO_USUARIOS,
    DIR_TABELAS,
    BuscadorFake,
    RepositorioFake,
    resolver_dir_fixtures,
)
from bussola_mcp.ferramentas.ports import BackendUnavailable

MISSING_FIXTURES_MESSAGE = "Dados de exemplo indisponíveis."


class FixtureRepository:
    """``RepositorioFinanceiro`` over ``contracts/fixtures/`` that fails loudly."""

    def __init__(self, fixtures_dir: Path | str | None = None) -> None:
        self.fixtures_dir = resolver_dir_fixtures(fixtures_dir)
        self._fake: RepositorioFake | None = None

    def _require(self, relative: Path | str) -> RepositorioFake:
        if not (self.fixtures_dir / relative).is_file():
            raise BackendUnavailable(MISSING_FIXTURES_MESSAGE)
        if self._fake is None:
            self._fake = RepositorioFake(self.fixtures_dir)
        return self._fake

    def _table(self, name: str) -> RepositorioFake:
        return self._require(Path(DIR_TABELAS) / f"{name}.json")

    def _read[T](self, call: Callable[[], T]) -> T:
        try:
            return call()
        except (OSError, ValueError) as exc:
            # A partially loaded fake could keep bad state: start over next time.
            self._fake = None
            raise BackendUnavailable(MISSING_FIXTURES_MESSAGE) from exc

    # -- RepositorioFinanceiro ------------------------------------------------

    def usuario_existe(self, id_usuario: str) -> bool:
        fake = self._require(ARQUIVO_USUARIOS)
        return self._read(lambda: fake.usuario_existe(id_usuario))

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        fake = self._table("perfil_mensal")
        return self._read(lambda: fake.perfil_mensal(id_usuario, ate_anomes))

    def gastos_categoria(
        self, id_usuario: str, ate_anomes: int, desde_anomes: int | None = None
    ) -> list[GastoCategoria]:
        fake = self._table("gastos_categoria")
        return self._read(lambda: fake.gastos_categoria(id_usuario, ate_anomes, desde_anomes))

    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]:
        fake = self._table("entradas_categoria")
        return self._read(lambda: fake.entradas_categoria(id_usuario, ate_anomes))

    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]:
        fake = self._table("recorrentes")
        return self._read(lambda: fake.recorrentes(id_usuario, ate_anomes))

    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]:
        fake = self._table("parcelas")
        return self._read(lambda: fake.parcelas(id_usuario, ate_anomes))

    def categorias(self) -> list[Categoria]:
        fake = self._table("categorias")
        return self._read(fake.categorias)

    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]:
        fake = self._table("referencia_coorte")
        return self._read(lambda: fake.referencia_coorte(faixa_renda, macro))


class FixtureSearcher:
    """``BuscadorContexto`` over ``rag/trechos_exemplo.json`` that fails loudly."""

    def __init__(self, fixtures_dir: Path | str | None = None) -> None:
        self.fixtures_dir = resolver_dir_fixtures(fixtures_dir)
        self._fake: BuscadorFake | None = None

    def buscar(self, pergunta: str, k: int, tema: TemaConhecimento | None = None) -> list[Trecho]:
        if not (self.fixtures_dir / ARQUIVO_TRECHOS).is_file():
            raise BackendUnavailable(MISSING_FIXTURES_MESSAGE)
        if self._fake is None:
            self._fake = BuscadorFake(self.fixtures_dir)
        try:
            return self._fake.buscar(pergunta, k, tema)
        except (OSError, ValueError) as exc:
            self._fake = None
            raise BackendUnavailable(MISSING_FIXTURES_MESSAGE) from exc
