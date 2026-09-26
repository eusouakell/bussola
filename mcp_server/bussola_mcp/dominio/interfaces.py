"""Interfaces de domínio do MCP server (contratos §4).

Protocols ``runtime_checkable`` implementados pelos fakes do 000
(:mod:`bussola_mcp.dominio.fakes`), pelo ``RepositorioBigQuery`` do 001 e pelos
buscadores do 002. As ferramentas dependem só destas assinaturas.

Toda leitura por cliente recebe ``id_usuario`` e ``ate_anomes``: o escopo por
cliente e o corte temporal são obrigatórios (constituição III e IV).
"""

from typing import Protocol, runtime_checkable

from bussola_mcp.contratos import (
    Categoria,
    EntradaCategoria,
    GastoCategoria,
    Parcela,
    PerfilMes,
    Recorrente,
    RefCoorte,
    Trecho,
)


@runtime_checkable
class RepositorioFinanceiro(Protocol):
    """Leitura das tabelas de ``bussola_dados`` (§3), sempre com escopo e corte."""

    def usuario_existe(self, id_usuario: str) -> bool: ...

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]: ...

    def gastos_categoria(
        self, id_usuario: str, ate_anomes: int, desde_anomes: int | None = None
    ) -> list[GastoCategoria]: ...

    def entradas_categoria(self, id_usuario: str, ate_anomes: int) -> list[EntradaCategoria]: ...

    def recorrentes(self, id_usuario: str, ate_anomes: int) -> list[Recorrente]: ...

    def parcelas(self, id_usuario: str, ate_anomes: int) -> list[Parcela]: ...

    def categorias(self) -> list[Categoria]: ...

    def referencia_coorte(self, faixa_renda: str, macro: str | None = None) -> list[RefCoorte]: ...


@runtime_checkable
class BuscadorContexto(Protocol):
    """Busca de trechos do corpus (``bussola_rag``) do cliente e da coorte, até o corte."""

    def buscar(self, id_usuario: str, pergunta: str, k: int, ate_anomes: int) -> list[Trecho]: ...
