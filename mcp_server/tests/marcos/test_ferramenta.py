"""Ferramenta ``planejar_marcos`` no protocolo do ciclo 003 (009, AC-10 a AC-12).

A ferramenta só expõe ``NAME``, ``compute`` e ``register``: validação,
``USUARIO_INEXISTENTE``, ``PRAZO_IMPLAUSIVEL``, envelope, mapeamento de erro e
linha de log são do ``ToolRunner`` (``ferramentas/base.py``), e o cálculo é de
``DomainComputations.planejar_marcos``. Os testes aqui exercitam esse caminho
inteiro chamando o runner real com as portas de fixtures, como faz
``tests/ferramentas/test_runner_ferramentas.py``; a camada MCP (catálogo,
escopo, logs e varredura de saídas) é coberta, para as dez ferramentas do
contrato, em ``tests/ferramentas/``.

Tudo sobre ``contracts/fixtures/``: sem rede, sem GCP.
"""

import json
import logging
from collections.abc import Callable
from typing import Any

import pytest

from bussola_mcp.contratos import (
    ID_ANCORA,
    ID_CONTROLE,
    MENSAGENS_ERRO,
    TABELAS_FERRAMENTA,
    CodigoErro,
    DadosPlanejarMarcos,
    PerfilMes,
    RegrasMarco,
    Resposta,
)
from bussola_mcp.dominio.interfaces import RepositorioFinanceiro
from bussola_mcp.dominio.repositorio_bq import RepositoryUnavailableError
from bussola_mcp.ferramentas import planejar_marcos as ferramenta
from bussola_mcp.ferramentas.base import ToolRunner
from bussola_mcp.ferramentas.computations import DomainComputations
from bussola_mcp.ferramentas.fixture_backends import FixtureRepository, FixtureSearcher
from bussola_mcp.ferramentas.ports import ToolDependencies

ENTRADA = {"id_usuario": ID_ANCORA, "ate_anomes": 202512, "valor_alvo": 300000.0, "prazo_meses": 24}
UUID_INEXISTENTE = "11111111-1111-4111-8111-111111111111"

# Segredos e detalhes de infraestrutura que nunca podem sair numa resposta.
MARCADORES_PROIBIDOS = ("SELECT", "batalha-time-07", "googleapis", "Bearer", "@id_usuario")


class RepositorioSemMeses(FixtureRepository):
    """Usuário conhecido, mas sem nenhum mês no período."""

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        return []


class RepositorioQuebrado(FixtureRepository):
    """Falha de leitura (equivalente a BigQuery indisponível)."""

    def __init__(self, erro: BaseException) -> None:
        super().__init__(None)
        self.erro = erro

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        raise self.erro


def runner(repositorio: RepositorioFinanceiro | None = None) -> ToolRunner:
    """Runner real com as portas de fixtures (``None`` = ``contracts/fixtures/``)."""
    repositorio = repositorio if repositorio is not None else FixtureRepository(None)
    return ToolRunner(
        ToolDependencies(
            repository=repositorio,
            # Nenhuma busca nesta ferramenta; a porta é exigida pelo contrato de deps.
            searcher=FixtureSearcher(None),
            computations=DomainComputations(repositorio),
        )
    )


def executar(alvo: ToolRunner, **mudancas: Any) -> dict[str, Any]:
    return alvo.run(ferramenta.NAME, {**ENTRADA, **mudancas}, ferramenta.compute)


def chamar(**mudancas: Any) -> dict[str, Any]:
    return executar(runner(), **mudancas)


# ---------------------------------------------------------------------------
# Sucesso: envelope, fonte e avisos (AC-10)
# ---------------------------------------------------------------------------


def test_envelope_de_sucesso() -> None:
    envelope = chamar()
    assert set(envelope) == {"dados", "fonte", "avisos"}
    assert envelope["fonte"]["ferramenta"] == "planejar_marcos"
    assert envelope["fonte"]["tabelas"] == TABELAS_FERRAMENTA["planejar_marcos"]
    assert envelope["fonte"]["tabelas"] == [
        "bussola_dados.perfil_mensal",
        "bussola_dados.parcelas",
    ]
    assert envelope["fonte"]["periodo"] == {"inicio": 202501, "fim": 202512}
    assert envelope["avisos"]
    # Revalida contra o modelo do contrato.
    Resposta[DadosPlanejarMarcos].model_validate(envelope)


def test_fonte_respeita_o_corte_do_periodo() -> None:
    envelope = chamar(ate_anomes=202506)
    assert envelope["fonte"]["periodo"]["fim"] == 202506


def test_ancora_com_objetivo_grande_tem_motivo_e_proximo_marco() -> None:
    dados = chamar()["dados"]
    assert dados["motivos"]
    assert dados["proximo"] is not None
    assert dados["proximo"]["ordem"] == 1
    assert dados["capacidade_sustentavel"] > 0
    assert dados["aporte_necessario"] > dados["capacidade_sustentavel"]
    assert dados["regras"]["meses_reserva"] == 3


def test_ancora_com_objetivo_que_cabe_nao_devolve_marco() -> None:
    """Entrada da demo (R$ 60 mil em 24 meses) cabe na capacidade do âncora."""
    dados = chamar(valor_alvo=60000.0)["dados"]
    assert dados["motivos"] == []
    assert dados["marcos"] == []
    assert dados["proximo"] is None


def test_prioridade_e_ecoada_sem_entrar_no_calculo() -> None:
    com = chamar(prioridade="casa própria")["dados"]
    sem = chamar()["dados"]
    assert com["objetivo"]["prioridade"] == "casa própria"
    assert com["marcos"] == sem["marcos"]


def test_usar_saldo_atual_falso_muda_os_recursos() -> None:
    com_saldo = chamar()["dados"]["situacao"]
    sem_saldo = chamar(usar_saldo_atual=False)["dados"]["situacao"]
    assert com_saldo["recursos_disponiveis"] > 0
    assert sem_saldo["recursos_disponiveis"] == 0.0
    assert "RESERVA" in sem_saldo["dados_ausentes"]


def test_regras_versionadas_voltam_no_envelope_e_seguem_usar_saldo_atual() -> None:
    """Sucessor de ``test_regras_podem_ser_injetadas``.

    A ferramenta não recebe mais ``regras``: ``DomainComputations.planejar_marcos``
    deriva a :class:`RegrasMarco` de ``entrada.usar_saldo_atual``. A garantia que
    resta no nível da ferramenta é que as regras usadas voltam versionadas em
    ``dados.regras`` e que a única premissa que o cliente controla muda o plano.
    A injeção de regras continua coberta no domínio puro
    (``tests/marcos/test_engine.py`` sobre ``bussola_mcp.dominio.marcos``).
    """
    com_saldo = chamar()["dados"]
    sem_saldo = chamar(usar_saldo_atual=False)["dados"]
    assert com_saldo["regras"] == RegrasMarco().model_dump(mode="json")
    assert com_saldo["regras"]["usar_saldo_atual"] is True
    assert sem_saldo["regras"] == RegrasMarco(usar_saldo_atual=False).model_dump(mode="json")
    assert sem_saldo["marcos"] != com_saldo["marcos"]


def test_resposta_nao_vaza_sql_projeto_nem_credencial() -> None:
    saidas = [
        chamar(),
        chamar(prioridade="casa própria"),
        chamar(id_usuario="'; SELECT 1 --"),
        chamar(prazo_meses=400),
        executar(runner(RepositorioQuebrado(RuntimeError("SELECT * FROM batalha-time-07")))),
    ]
    texto = json.dumps(saidas, ensure_ascii=False)
    for marcador in MARCADORES_PROIBIDOS:
        assert marcador not in texto


# ---------------------------------------------------------------------------
# Erros (AC-11, AC-12): tudo pelo ``ToolRunner``
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mudancas", "campo"),
    [
        ({"id_usuario": "nao-e-uuid"}, "id_usuario"),
        ({"ate_anomes": 202601}, "ate_anomes"),
        ({"valor_alvo": 0}, "valor_alvo"),
        ({"valor_alvo": -1}, "valor_alvo"),
        ({"prioridade": "x" * 101}, "prioridade"),
    ],
)
def test_entrada_invalida_cita_so_o_campo(mudancas: dict[str, Any], campo: str) -> None:
    envelope = chamar(**mudancas)
    assert envelope["erro"]["codigo"] == CodigoErro.ENTRADA_INVALIDA
    assert campo in envelope["erro"]["mensagem"]
    for valor in mudancas.values():
        assert str(valor) not in envelope["erro"]["mensagem"]


@pytest.mark.parametrize("prazo", [0, -3, 361, 400])
def test_prazo_fora_de_1_a_360_vira_prazo_implausivel(prazo: int) -> None:
    """Parte de ``test_entrada_invalida_cita_so_o_campo`` no desenho antigo.

    ``EntradaPlanejarMarcos.prazo_meses`` é ``ge=1, le=360`` e não tem
    ``aporte_mensal``, então ``base.is_implausible_term`` classifica o prazo
    fora da faixa como ``PRAZO_IMPLAUSIVEL``, e não ``ENTRADA_INVALIDA``.
    """
    envelope = chamar(prazo_meses=prazo)
    assert envelope["erro"] == {
        "codigo": CodigoErro.PRAZO_IMPLAUSIVEL,
        "mensagem": MENSAGENS_ERRO[CodigoErro.PRAZO_IMPLAUSIVEL],
    }


def test_prazo_fora_com_outro_erro_continua_entrada_invalida() -> None:
    envelope = chamar(prazo_meses=400, valor_alvo=-1)
    assert envelope["erro"]["codigo"] == CodigoErro.ENTRADA_INVALIDA
    assert "400" not in envelope["erro"]["mensagem"]


def test_parametro_extra_nao_ecoa_o_nome() -> None:
    """A recusa vem do ``extra="forbid"`` de ``EntradaPlanejarMarcos``, no runner.

    O teste bate no runner de propósito: o FastMCP descarta silenciosamente um
    argumento fora da assinatura da ferramenta, então pela sessão MCP este
    caminho nunca seria exercitado.
    """
    envelope = chamar(campo_malicioso="x")
    assert envelope["erro"]["codigo"] == CodigoErro.ENTRADA_INVALIDA
    assert "campo_malicioso" not in envelope["erro"]["mensagem"]


def test_dados_insuficientes_quando_nao_ha_mes_no_periodo() -> None:
    envelope = executar(runner(RepositorioSemMeses(None)))
    assert envelope["erro"]["codigo"] == CodigoErro.DADOS_INSUFICIENTES


@pytest.mark.parametrize(
    "erro",
    [
        OSError("falha simulada de leitura"),
        RepositoryUnavailableError("falha simulada de leitura"),
    ],
)
def test_indisponivel_sem_stack_nem_detalhe(
    erro: BaseException, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        envelope = executar(runner(RepositorioQuebrado(erro)))
    assert envelope == {
        "erro": {
            "codigo": CodigoErro.INDISPONIVEL,
            "mensagem": MENSAGENS_ERRO[CodigoErro.INDISPONIVEL],
        }
    }
    assert "falha simulada" not in json.dumps(envelope, ensure_ascii=False)
    assert any(getattr(r, "erro_codigo", None) == CodigoErro.INDISPONIVEL for r in caplog.records)


# Um cenário desta ferramenta por código de erro do contrato.
CENARIOS_DE_ERRO: dict[CodigoErro, Callable[[], dict[str, Any]]] = {
    CodigoErro.ENTRADA_INVALIDA: lambda: chamar(valor_alvo=0),
    CodigoErro.PRAZO_IMPLAUSIVEL: lambda: chamar(prazo_meses=400),
    CodigoErro.USUARIO_INEXISTENTE: lambda: chamar(id_usuario=UUID_INEXISTENTE),
    CodigoErro.DADOS_INSUFICIENTES: lambda: executar(runner(RepositorioSemMeses(None))),
    CodigoErro.INDISPONIVEL: lambda: executar(runner(RepositorioQuebrado(OSError("falha")))),
}


def test_todos_os_codigos_previstos_tem_caso() -> None:
    """Os cinco códigos de ``CodigoErro`` são alcançáveis por ``planejar_marcos``.

    No desenho antigo ``PRAZO_IMPLAUSIVEL`` ficava de fora (research R4). Com o
    runner do 003 ele passou a valer também aqui, porque ``prazo_meses`` é
    obrigatório e limitado a 1–360; um prazo **calculado** acima de
    ``regras.prazo_maximo_marco`` continua virando ``trajetoria_incerta``, e não
    erro (FR-010, coberto em ``test_engine.py``).
    """
    assert set(CENARIOS_DE_ERRO) == set(CodigoErro)
    for esperado, cenario in CENARIOS_DE_ERRO.items():
        envelope = cenario()
        assert envelope["erro"]["codigo"] == esperado, esperado
        assert envelope["erro"]["mensagem"]


# ---------------------------------------------------------------------------
# Escopo por cliente (constituição III)
# ---------------------------------------------------------------------------


def test_escopo_o_controle_nao_recebe_numeros_do_ancora() -> None:
    ancora = chamar()["dados"]["situacao"]
    controle = chamar(id_usuario=ID_CONTROLE)
    if "erro" in controle:
        assert controle["erro"]["codigo"] in {
            CodigoErro.DADOS_INSUFICIENTES,
            CodigoErro.USUARIO_INEXISTENTE,
        }
        return
    assert controle["dados"]["situacao"]["renda_media"] != ancora["renda_media"]


# ---------------------------------------------------------------------------
# Log (contratos §9)
# ---------------------------------------------------------------------------


def test_log_tem_ferramenta_latencia_e_nao_tem_prioridade(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        chamar(prioridade="comprar apartamento no centro")
    registro = next(r for r in caplog.records if getattr(r, "evento", None) == "ferramenta_chamada")
    assert registro.ferramenta == "planejar_marcos"  # type: ignore[attr-defined]
    assert registro.latencia_ms >= 0  # type: ignore[attr-defined]
    assert registro.ate_anomes == 202512  # type: ignore[attr-defined]
    assert "apartamento" not in caplog.text
    # Nenhum campo extra do registro carrega o texto livre do cliente.
    assert all("apartamento" not in str(valor) for valor in registro.__dict__.values())
