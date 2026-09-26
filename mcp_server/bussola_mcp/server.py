"""MCP mock do ciclo 000: 7 ferramentas P0 + ``resumo_mes`` (contratos §5 e §8).

Serve respostas determinísticas a partir de ``contracts/fixtures/`` para o agente
(004) e o canal (007) trabalharem antes das ferramentas reais do 003
(FR-017, FR-018). Regras (``specs/000-fundacao-contratos/contracts/mcp-ferramentas.md``):

1. valida a entrada com ``Entrada*`` → ``ENTRADA_INVALIDA`` citando só nomes de campos;
2. ``id_usuario`` fora de ``usuarios.json`` → ``USUARIO_INEXISTENTE``;
3. usuário que não é o âncora → ``DADOS_INSUFICIENTES`` (nunca o golden de outro cliente);
4. golden por ferramenta e corte (``< 202512`` → ``__ate_202506`` com aviso de mock),
   ``resumo_mes__<anomes>``, truncamento em ``top_n``/``k`` e aviso da entrada
   canônica nas simulações;
5. fixture ausente ou inválida → ``INDISPONIVEL`` ("Dados de exemplo indisponíveis.").

Todo resultado é um envelope JSON (``structuredContent`` + ``TextContent``). Erro de
negócio é resultado, não ``isError``. Cada chamada gera uma linha de log JSON com
ferramenta, latência e código de erro, sem valores de entrada.

Uso::

    python -m bussola_mcp.server [--host 0.0.0.0] [--port $PORT|8080] [--fixtures DIR]
"""

import argparse
import copy
import logging
import os
import time
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ValidationError

from bussola_mcp.contratos import (
    CORTES_GOLDEN,
    ENTRADA_CANONICA_SIMULACAO,
    FERRAMENTAS,
    FERRAMENTAS_P0,
    CodigoErro,
    EntradaBuscarContexto,
    EntradaComum,
    EntradaOportunidadesCorte,
    EntradaResumoMes,
    Resposta,
    UsuarioFixture,
    arquivo_golden,
    arquivo_resumo_mes,
    envelope_erro,
    mensagem_entrada_invalida,
)
from bussola_mcp.dominio.fakes import carregar_usuarios, ler_json, resolver_dir_fixtures
from bussola_mcp.logging_json import configurar_logging

logger = logging.getLogger("bussola_mcp.server")

SERVICO = "bussola-mcp"
CAMINHO_MCP = "/mcp"
PORTA_PADRAO = 8080
DIR_GOLDEN = "ferramentas"

CORTE_PARCIAL, CORTE_FINAL = CORTES_GOLDEN
FERRAMENTAS_SIMULACAO = ("simular_objetivo", "comparar_cenarios")


def _numero(valor: Any) -> str:
    return f"{valor:g}" if isinstance(valor, float) else str(valor)


AVISO_CORTE = f"Resposta de exemplo do mock (corte {CORTE_PARCIAL})."
AVISO_SIMULACAO = (
    "Resposta de exemplo do mock, calculada para "
    + " e ".join(f"{campo}={_numero(v)}" for campo, v in ENTRADA_CANONICA_SIMULACAO.items())
    + "."
)
MENSAGEM_SO_ANCORA = "O mock só tem respostas do cliente âncora."
MENSAGEM_SEM_FIXTURES = "Dados de exemplo indisponíveis."

INSTRUCOES = (
    "MCP mock da Bússola (ciclo 000). Ferramentas financeiras determinísticas com "
    "respostas de exemplo do cliente âncora. Todas exigem id_usuario e ate_anomes."
)

_ANOTACOES = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)


class _FixtureIndisponivel(Exception):
    """Arquivo de fixture ausente ou fora do contrato."""


class MockBussola:
    """Regras do mock sobre um diretório de fixtures, com leitura sob demanda.

    Só leituras bem-sucedidas ficam em cache: um arquivo criado depois do início
    (ex.: ``make fixtures`` com o servidor no ar) passa a ser servido.
    """

    def __init__(self, dir_fixtures: Path | str | None = None) -> None:
        self.dir_fixtures = resolver_dir_fixtures(dir_fixtures)
        self._usuarios: dict[str, UsuarioFixture] | None = None
        self._golden: dict[str, dict[str, Any]] = {}

    # -- fixtures ------------------------------------------------------------

    def _carregar_usuarios(self) -> dict[str, UsuarioFixture]:
        if self._usuarios is None:
            try:
                usuarios = carregar_usuarios(self.dir_fixtures)
            except (OSError, ValueError) as exc:
                raise _FixtureIndisponivel from exc
            if usuarios is None:
                raise _FixtureIndisponivel
            self._usuarios = usuarios
        return self._usuarios

    def _carregar_golden(self, nome_arquivo: str, dados: type[BaseModel]) -> dict[str, Any]:
        if nome_arquivo not in self._golden:
            try:
                conteudo = ler_json(self.dir_fixtures / DIR_GOLDEN / nome_arquivo)
                if conteudo is None:
                    raise _FixtureIndisponivel
                envelope = Resposta[dados].model_validate(conteudo)
            except (OSError, ValueError) as exc:
                raise _FixtureIndisponivel from exc
            self._golden[nome_arquivo] = envelope.model_dump(mode="json")
        return copy.deepcopy(self._golden[nome_arquivo])

    # -- regras ---------------------------------------------------------------

    def responder(self, ferramenta: str, argumentos: dict[str, Any]) -> dict[str, Any]:
        """Envelope de sucesso ou de erro da ferramenta, com uma linha de log."""
        inicio = time.perf_counter()
        try:
            envelope = self._responder(ferramenta, argumentos)
        except _FixtureIndisponivel as exc:
            causa = exc.__cause__
            logger.warning(
                "fixture indisponível",
                exc_info=(type(causa), causa, causa.__traceback__) if causa else None,
                extra={"evento": "fixture_indisponivel", "ferramenta": ferramenta},
            )
            envelope = envelope_erro(CodigoErro.INDISPONIVEL, MENSAGEM_SEM_FIXTURES)
        except Exception:
            logger.exception(
                "falha inesperada na ferramenta",
                extra={"evento": "ferramenta_falhou", "ferramenta": ferramenta},
            )
            envelope = envelope_erro(CodigoErro.INDISPONIVEL)
        erro = envelope.get("erro")
        codigo = erro["codigo"] if isinstance(erro, dict) else None
        logger.log(
            logging.WARNING if codigo == CodigoErro.INDISPONIVEL else logging.INFO,
            "ferramenta chamada",
            extra={
                "evento": "ferramenta_chamada",
                "ferramenta": ferramenta,
                "latencia_ms": round((time.perf_counter() - inicio) * 1000, 2),
                "erro_codigo": codigo,
            },
        )
        return envelope

    def _responder(self, ferramenta: str, argumentos: dict[str, Any]) -> dict[str, Any]:
        classe_entrada, classe_dados = FERRAMENTAS[ferramenta]
        try:
            entrada = classe_entrada.model_validate(argumentos)
        except ValidationError as exc:
            return envelope_erro(CodigoErro.ENTRADA_INVALIDA, mensagem_entrada_invalida(exc))

        usuario = self._carregar_usuarios().get(entrada.id_usuario)
        if usuario is None:
            return envelope_erro(CodigoErro.USUARIO_INEXISTENTE)
        if usuario.papel != "ancora":
            return envelope_erro(CodigoErro.DADOS_INSUFICIENTES, MENSAGEM_SO_ANCORA)

        nome_arquivo, avisos = self._escolher_golden(ferramenta, entrada)
        envelope = self._carregar_golden(nome_arquivo, classe_dados)

        if isinstance(entrada, EntradaOportunidadesCorte):
            envelope["dados"]["categorias"] = envelope["dados"]["categorias"][: entrada.top_n]
        elif isinstance(entrada, EntradaBuscarContexto):
            envelope["dados"]["trechos"] = envelope["dados"]["trechos"][: entrada.k]

        for aviso in avisos:
            if aviso not in envelope["avisos"]:
                envelope["avisos"].append(aviso)
        return envelope

    @staticmethod
    def _escolher_golden(ferramenta: str, entrada: EntradaComum) -> tuple[str, list[str]]:
        if isinstance(entrada, EntradaResumoMes):
            return arquivo_resumo_mes(entrada.anomes), []
        if ferramenta not in FERRAMENTAS_P0:
            raise _FixtureIndisponivel
        avisos: list[str] = []
        if entrada.ate_anomes < CORTE_FINAL:
            corte = CORTE_PARCIAL
            avisos.append(AVISO_CORTE)
        else:
            corte = CORTE_FINAL
        if ferramenta in FERRAMENTAS_SIMULACAO:
            avisos.append(AVISO_SIMULACAO)
        return arquivo_golden(ferramenta, corte), avisos


def criar_servidor(
    dir_fixtures: Path | str | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = PORTA_PADRAO,
) -> FastMCP:
    """FastMCP com as 8 ferramentas do mock (``FERRAMENTAS_MOCK``).

    As assinaturas usam tipos simples com os padrões de §5. Faixas e UUID são
    validados dentro da ferramenta, que devolve o envelope de erro (research R-05).
    Com ``host`` de loopback, o SDK liga a proteção contra DNS rebinding.
    """
    mock = MockBussola(dir_fixtures)
    servidor = FastMCP(
        SERVICO,
        instructions=INSTRUCOES,
        host=host,
        port=port,
        streamable_http_path=CAMINHO_MCP,
    )
    ferramenta = servidor.tool(annotations=_ANOTACOES)

    @ferramenta
    def perfil_financeiro(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Renda, gasto e sobra médios, fontes de renda, saldo e série mensal até o corte."""
        return mock.responder(
            "perfil_financeiro", {"id_usuario": id_usuario, "ate_anomes": ate_anomes}
        )

    @ferramenta
    def capacidade_poupanca(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Sobra média e mediana, desvio padrão e meses negativos até o corte."""
        return mock.responder(
            "capacidade_poupanca", {"id_usuario": id_usuario, "ate_anomes": ate_anomes}
        )

    @ferramenta
    def oportunidades_corte(id_usuario: str, ate_anomes: int, top_n: int = 5) -> dict[str, Any]:
        """Categorias com maior economia potencial mensal (até ``top_n``, de 1 a 10)."""
        return mock.responder(
            "oportunidades_corte",
            {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "top_n": top_n},
        )

    @ferramenta
    def dividas_e_parcelas(id_usuario: str, ate_anomes: int) -> dict[str, Any]:
        """Parcelas ativas, juros pagos em média e comprometimento da renda."""
        return mock.responder(
            "dividas_e_parcelas", {"id_usuario": id_usuario, "ate_anomes": ate_anomes}
        )

    @ferramenta
    def simular_objetivo(
        id_usuario: str,
        ate_anomes: int,
        valor_alvo: float,
        prazo_meses: int | None = None,
        aporte_mensal: float | None = None,
        usar_saldo_atual: bool = False,
    ) -> dict[str, Any]:
        """Aporte para um prazo ou prazo para um aporte. Informe exatamente um dos dois."""
        return mock.responder(
            "simular_objetivo",
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "valor_alvo": valor_alvo,
                "prazo_meses": prazo_meses,
                "aporte_mensal": aporte_mensal,
                "usar_saldo_atual": usar_saldo_atual,
            },
        )

    @ferramenta
    def comparar_cenarios(
        id_usuario: str, ate_anomes: int, valor_alvo: float, prazo_meses: int
    ) -> dict[str, Any]:
        """Cenários conservador, equilibrado e acelerado para o objetivo."""
        return mock.responder(
            "comparar_cenarios",
            {
                "id_usuario": id_usuario,
                "ate_anomes": ate_anomes,
                "valor_alvo": valor_alvo,
                "prazo_meses": prazo_meses,
            },
        )

    @ferramenta
    def buscar_contexto_financeiro(
        id_usuario: str, ate_anomes: int, pergunta: str, k: int = 5
    ) -> dict[str, Any]:
        """Trechos do histórico do cliente e da coorte relevantes para a pergunta."""
        return mock.responder(
            "buscar_contexto_financeiro",
            {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "pergunta": pergunta, "k": k},
        )

    @ferramenta
    def resumo_mes(id_usuario: str, ate_anomes: int, anomes: int) -> dict[str, Any]:
        """Renda, gasto, sobra e gastos por macro de um mês (``anomes <= ate_anomes``)."""
        return mock.responder(
            "resumo_mes", {"id_usuario": id_usuario, "ate_anomes": ate_anomes, "anomes": anomes}
        )

    return servidor


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m bussola_mcp.server",
        description="MCP mock da Bússola (streamable HTTP em /mcp).",
    )
    parser.add_argument("--host", default="0.0.0.0", help="padrão: 0.0.0.0")
    parser.add_argument(
        "--port",
        type=int,
        default=os.environ.get("PORT", str(PORTA_PADRAO)),
        help="padrão: $PORT ou 8080",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        default=None,
        help="diretório de fixtures (padrão: <raiz do repositório>/contracts/fixtures)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _argumentos(argv)
    configurar_logging(SERVICO)
    servidor = criar_servidor(args.fixtures, host=args.host, port=args.port)
    logger.info(
        f"MCP mock em {args.host}:{args.port}{CAMINHO_MCP}", extra={"evento": "servidor_iniciado"}
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
