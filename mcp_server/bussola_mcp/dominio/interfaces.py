"""Interfaces de domínio do MCP server (contratos §4).

Protocols ``runtime_checkable`` implementados pelos fakes do 000
(:mod:`bussola_mcp.dominio.fakes`), pelo ``RepositorioBigQuery`` do 001 e pelos
buscadores do 002. As ferramentas dependem só destas assinaturas.

Toda leitura por cliente recebe ``id_usuario`` e ``ate_anomes``: o escopo por
cliente e o corte temporal são obrigatórios (constituição III e IV). O buscador
não recebe nenhum dos dois: o corpus é conhecimento geral, sem dado de cliente
(Q-17).

As falhas de **infraestrutura** de cada porta também são parte da porta:
:class:`RepositoryUnavailableError` e :class:`SearcherUnavailableError`. Ficam
aqui, e não no módulo de cada adaptador, para a camada de aplicação tratá-las
sem importar o BigQuery nem o RAG (varredura R6). As mensagens são genéricas:
nunca SQL, projeto, credencial ou nome de provedor (constituição II).
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
    TemaConhecimento,
    Trecho,
)


class RepositoryUnavailableError(RuntimeError):
    """Falha de leitura no repositório. A mensagem é genérica e segura para o cliente."""

    def __init__(self, mensagem: str = "Leitura de dados indisponível.") -> None:
        super().__init__(mensagem)


class SearcherUnavailableError(RuntimeError):
    """Falha do backend de busca do corpus de conhecimento.

    Superclasse de ``rag.embedding.EmbeddingUnavailableError``: a ferramenta
    trata a falha pela porta, sem conhecer o adaptador que a levantou.
    """


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
    """Busca no corpus de conhecimento (normas do BACEN, crédito e boas práticas).

    Devolve até ``k`` trechos com ``score > 0``, do mais relevante ao menos
    relevante (empate por ``trecho_id``). ``tema`` restringe a busca a um tema.
    """

    def buscar(
        self, pergunta: str, k: int, tema: TemaConhecimento | None = None
    ) -> list[Trecho]: ...
