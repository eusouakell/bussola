"""Ferramenta ``planejar_marcos``: rota de marcos intermediários (ciclo 009).

Contrato completo em
``specs/009-marcos-financeiros/contracts/planejar_marcos.md``. Read-only: valida
a entrada, lê ``perfil_mensal`` e ``parcelas`` pelo ``RepositorioFinanceiro``,
chama :mod:`bussola_mcp.dominio.marcos` e monta o envelope
``dados``/``fonte``/``avisos``.

Erros são envelope, nunca exceção:

- entrada fora das regras → ``ENTRADA_INVALIDA`` (só nomes de campo);
- UUID válido inexistente → ``USUARIO_INEXISTENTE``;
- nenhum mês até ``ate_anomes`` → ``DADOS_INSUFICIENTES``;
- falha do repositório → ``INDISPONIVEL`` (detalhe só no log).

``PRAZO_IMPLAUSIVEL`` **não** é usado: prazo calculado acima de
``RegrasMarco.prazo_maximo_marco`` vira ``trajetoria_incerta``, porque devolver
erro seria justamente o "não é viável" que a feature elimina (FR-010, SC-008).
"""

import logging
import time
from typing import Any

from pydantic import ValidationError

from bussola_mcp.contratos import (
    TABELAS_FERRAMENTA,
    CodigoErro,
    DadosPlanejarMarcos,
    EntradaPlanejarMarcos,
    Fonte,
    Periodo,
    RegrasMarco,
    Resposta,
    envelope_erro,
    mensagem_entrada_invalida,
)
from bussola_mcp.dominio import marcos
from bussola_mcp.dominio.interfaces import RepositorioFinanceiro

FERRAMENTA = "planejar_marcos"

logger = logging.getLogger("bussola_mcp.ferramentas.planejar_marcos")


def _envelope(
    dados: DadosPlanejarMarcos,
    entrada: EntradaPlanejarMarcos,
    inicio_periodo: int,
    avisos: list[str],
) -> dict[str, Any]:
    fonte = Fonte(
        ferramenta=FERRAMENTA,
        tabelas=list(TABELAS_FERRAMENTA[FERRAMENTA]),
        periodo=Periodo(inicio=inicio_periodo, fim=entrada.ate_anomes),
    )
    resposta = Resposta[DadosPlanejarMarcos](dados=dados, fonte=fonte, avisos=avisos)
    return resposta.model_dump(mode="json")


def planejar_marcos(
    argumentos: dict[str, Any],
    repositorio: RepositorioFinanceiro,
    regras: RegrasMarco | None = None,
) -> dict[str, Any]:
    """Envelope de ``planejar_marcos`` para ``argumentos``, com uma linha de log."""
    inicio = time.perf_counter()
    try:
        envelope = _responder(argumentos, repositorio, regras)
    except Exception:
        logger.exception(
            "falha inesperada na ferramenta",
            extra={"evento": "ferramenta_falhou", "ferramenta": FERRAMENTA},
        )
        envelope = envelope_erro(CodigoErro.INDISPONIVEL)
    erro = envelope.get("erro")
    codigo = erro["codigo"] if isinstance(erro, dict) else None
    logger.log(
        logging.WARNING if codigo == CodigoErro.INDISPONIVEL else logging.INFO,
        "ferramenta chamada",
        extra={
            "evento": "ferramenta_chamada",
            "ferramenta": FERRAMENTA,
            "latencia_ms": round((time.perf_counter() - inicio) * 1000, 2),
            "erro_codigo": codigo,
            "ate_anomes": argumentos.get("ate_anomes") if isinstance(argumentos, dict) else None,
        },
    )
    return envelope


def _responder(
    argumentos: dict[str, Any],
    repositorio: RepositorioFinanceiro,
    regras: RegrasMarco | None,
) -> dict[str, Any]:
    try:
        entrada = EntradaPlanejarMarcos.model_validate(argumentos)
    except ValidationError as exc:
        return envelope_erro(CodigoErro.ENTRADA_INVALIDA, mensagem_entrada_invalida(exc))

    if not repositorio.usuario_existe(entrada.id_usuario):
        return envelope_erro(CodigoErro.USUARIO_INEXISTENTE)

    perfil = repositorio.perfil_mensal(entrada.id_usuario, entrada.ate_anomes)
    if not perfil:
        return envelope_erro(CodigoErro.DADOS_INSUFICIENTES)
    parcelas = repositorio.parcelas(entrada.id_usuario, entrada.ate_anomes)

    regras_usadas = regras or RegrasMarco(usar_saldo_atual=entrada.usar_saldo_atual)
    contexto = marcos.contexto_de_perfil(perfil, parcelas, regras_usadas)
    dados = marcos.planejar(
        valor_alvo=entrada.valor_alvo,
        prazo_meses=entrada.prazo_meses,
        contexto=contexto,
        regras=regras_usadas,
        prioridade=entrada.prioridade,
    )
    avisos = marcos.avisos_do_plano(contexto, regras_usadas, dados)
    return _envelope(dados, entrada, min(linha.anomes for linha in perfil), avisos)
