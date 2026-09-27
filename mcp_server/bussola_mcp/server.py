"""MCP server da Bússola (ciclo 003): 9 ferramentas read-only em streamable HTTP.

Substitui o mock do 000. Expõe as ferramentas de contratos §5 em ``/mcp``, cada
uma num módulo de :mod:`bussola_mcp.ferramentas`, sobre portas injetadas
(``RepositorioFinanceiro``, ``BuscadorContexto`` e ``FinancialComputations``).

Fábrica única de dependências (contratos §4, :func:`build_dependencies`):

- ``--fixtures DIR`` ou ``BUSSOLA_FAKES=TRUE`` → adaptadores sobre ``contracts/fixtures/``;
- senão → ``RepositorioBigQuery(modo=BQ_MODO_LEITURA)`` (001) e
  ``criar_buscador(RAG_BACKEND)`` (002), importados sob demanda. Enquanto um
  deles não existir em ``main``, cai no adaptador de fixtures e registra
  ``evento=dependencia_ausente``.

Erros de negócio são resultado da ferramenta (envelope ``erro``), nunca
``isError``. Cada chamada gera uma linha de log JSON (contratos §9).

Uso::

    python -m bussola_mcp.server [--host 0.0.0.0] [--port $PORT|8080] [--fixtures DIR]
"""

import argparse
import importlib
import logging
from pathlib import Path
from types import ModuleType

import uvicorn
from mcp.server.fastmcp import FastMCP

from bussola_mcp import config
from bussola_mcp.dominio.interfaces import BuscadorContexto, RepositorioFinanceiro
from bussola_mcp.ferramentas import register_all
from bussola_mcp.ferramentas.computations import build_computations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.ports import ToolDependencies
from bussola_mcp.logging_json import configurar_logging

logger = logging.getLogger("bussola_mcp.server")

SERVICO = "bussola-mcp"
CAMINHO_MCP = "/mcp"
PORTA_PADRAO = config.PORTA_PADRAO
"""Porta padrão do MCP. O valor efetivo vem de :func:`bussola_mcp.config.porta_http`."""

REAL_REPOSITORY_MODULE = "bussola_mcp.dominio.repositorio_bq"
REAL_SEARCHER_MODULE = "bussola_mcp.rag"

INSTRUCOES = (
    "Ferramentas financeiras determinísticas e read-only da Bússola. Os números "
    "do cliente vêm com a origem em fonte (tabelas e período). "
    "buscar_contexto_financeiro traz conhecimento geral (normas do BACEN, crédito, "
    "boas práticas e produtos), sem dado do cliente. Todas exigem id_usuario e "
    "ate_anomes."
)


def fakes_enabled() -> bool:
    """``BUSSOLA_FAKES`` ligado (:func:`bussola_mcp.config.fakes_ligados`)."""
    return config.fakes_ligados()


def _optional_module(name: str) -> ModuleType | None:
    """Importa ``name`` ou devolve ``None`` quando o próprio módulo não existe.

    Um ``ModuleNotFoundError`` de outra dependência (ex.: pacote do Google
    ausente dentro do módulo) propaga: é falha de startup, não fallback.
    """
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name is not None and (name == exc.name or name.startswith(f"{exc.name}.")):
            logger.warning(
                "dependência ausente, usando fixtures",
                extra={"evento": "dependencia_ausente"},
            )
            return None
        raise


def _real_repository(fixtures_dir: Path | None) -> RepositorioFinanceiro:
    module = _optional_module(REAL_REPOSITORY_MODULE)
    if module is None:
        return FixtureRepository(fixtures_dir)
    return module.RepositorioBigQuery(modo=config.modo_leitura_bq())


def _real_searcher(fixtures_dir: Path | None) -> BuscadorContexto:
    module = _optional_module(REAL_SEARCHER_MODULE)
    if module is None:
        return FixtureSearcher(fixtures_dir)
    return module.criar_buscador(config.backend_rag())


def build_dependencies(fixtures_dir: Path | str | None = None) -> ToolDependencies:
    """Adaptadores das portas conforme o modo (fixtures ou real)."""
    diretorio = Path(fixtures_dir) if fixtures_dir is not None else None
    if diretorio is not None or fakes_enabled():
        repository: RepositorioFinanceiro = FixtureRepository(diretorio)
        searcher: BuscadorContexto = FixtureSearcher(diretorio)
    else:
        repository = _real_repository(diretorio)
        searcher = _real_searcher(diretorio)
    return ToolDependencies(
        repository=repository,
        searcher=searcher,
        computations=build_computations(repository, diretorio),
    )


def create_server(
    deps: ToolDependencies | None = None,
    *,
    fixtures_dir: Path | str | None = None,
    host: str = "127.0.0.1",
    port: int = PORTA_PADRAO,
) -> FastMCP:
    """FastMCP com as 9 ferramentas de ``contratos.FERRAMENTAS``.

    As assinaturas usam tipos simples com os padrões de §5; faixas e UUID são
    validados dentro da ferramenta (research R-05 do 000). Com ``host`` de
    loopback, o SDK liga a proteção contra DNS rebinding.
    """
    servidor = FastMCP(
        SERVICO,
        instructions=INSTRUCOES,
        host=host,
        port=port,
        streamable_http_path=CAMINHO_MCP,
    )
    register_all(servidor, deps if deps is not None else build_dependencies(fixtures_dir))
    return servidor


def criar_servidor(
    dir_fixtures: Path | str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = PORTA_PADRAO,
) -> FastMCP:
    """Compatibilidade com a API do mock do 000 (mesma assinatura).

    Equivale a ``create_server(fixtures_dir=dir_fixtures, ...)``: com
    ``dir_fixtures`` serve as fixtures; sem ele, segue a fábrica de dependências.
    """
    return create_server(fixtures_dir=dir_fixtures, host=host, port=port)


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m bussola_mcp.server",
        description="MCP server da Bússola (streamable HTTP em /mcp).",
    )
    parser.add_argument("--host", default="0.0.0.0", help="padrão: 0.0.0.0")
    parser.add_argument(
        "--port",
        type=int,
        default=config.porta_http(),
        help=f"padrão: ${config.VAR_PORTA} ou {config.PORTA_PADRAO}",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="diretório de fixtures; força o modo fake (padrão: contracts/fixtures)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _argumentos(argv)
    configurar_logging(SERVICO)
    servidor = create_server(fixtures_dir=args.fixtures, host=args.host, port=args.port)
    logger.info(
        f"MCP server em {args.host}:{args.port}{CAMINHO_MCP}",
        extra={"evento": "servidor_iniciado"},
    )
    # uvicorn sem dictConfig próprio: os logs dele passam pelo JsonFormatter da raiz.
    uvicorn.run(
        servidor.streamable_http_app(),
        host=args.host,
        port=args.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
