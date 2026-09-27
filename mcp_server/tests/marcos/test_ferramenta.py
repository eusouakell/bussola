"""Ferramenta ``planejar_marcos`` (ciclo 009, AC-10 a AC-12).

Tudo com ``RepositorioFake`` sobre ``contracts/fixtures/``: sem rede, sem GCP.
"""

import json
import logging
from typing import Any

import pytest

from bussola_mcp.contratos import (
    ID_ANCORA,
    ID_CONTROLE,
    CodigoErro,
    DadosPlanejarMarcos,
    PerfilMes,
    RegrasMarco,
    Resposta,
)
from bussola_mcp.dominio.fakes import RepositorioFake
from bussola_mcp.ferramentas.planejar_marcos import planejar_marcos

ENTRADA = {"id_usuario": ID_ANCORA, "ate_anomes": 202512, "valor_alvo": 300000.0, "prazo_meses": 24}
UUID_INEXISTENTE = "11111111-1111-4111-8111-111111111111"

# Segredos e detalhes de infraestrutura que nunca podem sair numa resposta.
MARCADORES_PROIBIDOS = ("SELECT", "batalha-time-07", "googleapis", "Bearer", "@id_usuario")


class RepositorioSemMeses(RepositorioFake):
    """Usuário conhecido, mas sem nenhum mês no período."""

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        return []


class RepositorioQuebrado(RepositorioFake):
    """Falha de leitura (equivalente a BigQuery indisponível)."""

    def perfil_mensal(self, id_usuario: str, ate_anomes: int) -> list[PerfilMes]:
        raise OSError("falha simulada de leitura")


def chamar(**mudancas: Any) -> dict[str, Any]:
    return planejar_marcos({**ENTRADA, **mudancas}, repositorio=RepositorioFake())


# ---------------------------------------------------------------------------
# Sucesso: envelope, fonte e avisos (AC-10)
# ---------------------------------------------------------------------------


def test_envelope_de_sucesso() -> None:
    envelope = chamar()
    assert set(envelope) == {"dados", "fonte", "avisos"}
    assert envelope["fonte"]["ferramenta"] == "planejar_marcos"
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


def test_resposta_nao_vaza_sql_projeto_nem_credencial() -> None:
    texto = json.dumps(chamar(), ensure_ascii=False)
    for marcador in MARCADORES_PROIBIDOS:
        assert marcador not in texto


# ---------------------------------------------------------------------------
# Erros (AC-11, AC-12)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mudancas", "campo"),
    [
        ({"id_usuario": "nao-e-uuid"}, "id_usuario"),
        ({"ate_anomes": 202601}, "ate_anomes"),
        ({"valor_alvo": 0}, "valor_alvo"),
        ({"valor_alvo": -1}, "valor_alvo"),
        ({"prazo_meses": 0}, "prazo_meses"),
        ({"prazo_meses": 400}, "prazo_meses"),
        ({"prioridade": "x" * 101}, "prioridade"),
    ],
)
def test_entrada_invalida_cita_so_o_campo(mudancas: dict[str, Any], campo: str) -> None:
    envelope = chamar(**mudancas)
    assert envelope["erro"]["codigo"] == CodigoErro.ENTRADA_INVALIDA
    assert campo in envelope["erro"]["mensagem"]
    for valor in mudancas.values():
        assert str(valor) not in envelope["erro"]["mensagem"]


def test_parametro_extra_nao_ecoa_o_nome() -> None:
    envelope = chamar(campo_malicioso="x")
    assert envelope["erro"]["codigo"] == CodigoErro.ENTRADA_INVALIDA
    assert "campo_malicioso" not in envelope["erro"]["mensagem"]


def test_usuario_inexistente() -> None:
    envelope = chamar(id_usuario=UUID_INEXISTENTE)
    assert envelope["erro"]["codigo"] == CodigoErro.USUARIO_INEXISTENTE


def test_dados_insuficientes_quando_nao_ha_mes_no_periodo() -> None:
    envelope = planejar_marcos(ENTRADA, repositorio=RepositorioSemMeses())
    assert envelope["erro"]["codigo"] == CodigoErro.DADOS_INSUFICIENTES


def test_indisponivel_sem_stack_nem_detalhe(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        envelope = planejar_marcos(ENTRADA, repositorio=RepositorioQuebrado())
    assert envelope["erro"]["codigo"] == CodigoErro.INDISPONIVEL
    assert "falha simulada" not in json.dumps(envelope, ensure_ascii=False)
    assert any(getattr(r, "erro_codigo", None) == CodigoErro.INDISPONIVEL for r in caplog.records)


def test_todos_os_codigos_previstos_tem_caso() -> None:
    """PRAZO_IMPLAUSIVEL não é usado por esta ferramenta (research R4)."""
    usados = {
        CodigoErro.ENTRADA_INVALIDA,
        CodigoErro.USUARIO_INEXISTENTE,
        CodigoErro.DADOS_INSUFICIENTES,
        CodigoErro.INDISPONIVEL,
    }
    assert set(CodigoErro) - usados == {CodigoErro.PRAZO_IMPLAUSIVEL}


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


def test_regras_podem_ser_injetadas() -> None:
    envelope = planejar_marcos(
        ENTRADA, repositorio=RepositorioFake(), regras=RegrasMarco(meses_reserva=6)
    )
    assert envelope["dados"]["regras"]["meses_reserva"] == 6
