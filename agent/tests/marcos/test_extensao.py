"""Extensão de marcos no agente (ciclo 009, AC-14 e AC-15).

Sem LLM e sem rede: o callback é chamado direto e pela cadeia agregada de
:mod:`bussola_agent.callbacks`.
"""

import asyncio
import importlib
import sys
from typing import Any

import pytest

from bussola_agent import callbacks, extensoes
from bussola_agent.estado import CHAVE_MARCOS, estado_inicial
from bussola_agent.marcos import instrucao
from bussola_agent.marcos.registro import ORDEM, gravar_marcos

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"

ENVELOPE = {
    "dados": {
        "objetivo": {"valor_alvo": 300000.0, "prazo_meses": 24, "prioridade": None},
        "motivos": [{"codigo": "PRAZO_NAO_CABE", "observado": 10516.76, "limite": 1493.66}],
        "marcos": [{"ordem": 1, "nivel": 3, "tipo": "ACUMULAR_PARTE_DA_META"}],
        "proximo": {"ordem": 1, "tipo": "ACUMULAR_PARTE_DA_META"},
        "trajetoria_incerta": True,
    },
    "fonte": {"ferramenta": "planejar_marcos", "tabelas": [], "periodo": {"inicio": 1, "fim": 2}},
    "avisos": [],
}


class FerramentaFake:
    def __init__(self, nome: str) -> None:
        self.name = nome


class ContextoFake:
    """Só o que o callback usa do ``ToolContext`` do ADK."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = estado_inicial(ANCORA, 202506)


def chamar(nome: str, resposta: Any) -> ContextoFake:
    contexto = ContextoFake()
    assert (
        gravar_marcos(
            tool=FerramentaFake(nome), args={}, tool_context=contexto, tool_response=resposta
        )
        is None
    )
    return contexto


# ---------------------------------------------------------------------------
# Registro (AC-14)
# ---------------------------------------------------------------------------


def test_pacote_registra_instrucao_e_callback_sem_ferramenta_local() -> None:
    # Import único: a fixture autouse já esvaziou os registros.
    sys.modules.pop("bussola_agent.marcos", None)
    importlib.import_module("bussola_agent.marcos")
    assert extensoes.ferramentas() == []
    assert instrucao.INSTRUCAO.strip() in extensoes.instrucoes()  # registrar_instrucao faz strip
    assert callbacks.registrados("after_tool") == [gravar_marcos]


def test_ordens_ficam_na_faixa_do_ciclo() -> None:
    assert 90 <= instrucao.ORDEM <= 99  # contratos §6: 90–99 é do 009
    assert ORDEM == 30  # after_tool 10 é do 004; 20 e 90 são do 005


def test_instrucao_tem_os_cinco_blocos_e_as_proibicoes() -> None:
    texto = instrucao.INSTRUCAO.lower()
    for bloco in ("diagnóstico", "simulação", "recomendação", "situação atual", "próximo marco"):
        assert bloco in texto
    for proibicao in (
        "não vai conseguir",
        "impossível",
        "ridicularizar",
        "promet",
        "aumento de renda",
        "dívida nova",
        "mais barato",
        "cortar da vida",
    ):
        assert proibicao in texto
    assert "planejar_marcos" in instrucao.INSTRUCAO
    assert "trajetoria_incerta" in instrucao.INSTRUCAO


# ---------------------------------------------------------------------------
# Gravação do state (AC-15)
# ---------------------------------------------------------------------------


def test_envelope_de_sucesso_grava_os_dados() -> None:
    contexto = chamar("planejar_marcos", ENVELOPE)
    assert contexto.state[CHAVE_MARCOS] == ENVELOPE["dados"]


def test_state_guarda_copia_do_envelope() -> None:
    contexto = chamar("planejar_marcos", ENVELOPE)
    contexto.state[CHAVE_MARCOS]["novo"] = 1
    assert "novo" not in ENVELOPE["dados"]


def test_envelope_de_erro_nao_grava() -> None:
    contexto = chamar("planejar_marcos", {"erro": {"codigo": "INDISPONIVEL", "mensagem": "x"}})
    assert contexto.state[CHAVE_MARCOS] is None


@pytest.mark.parametrize("resposta", [None, {}, {"dados": "texto"}, "texto", []])
def test_resposta_fora_do_contrato_nao_grava(resposta: Any) -> None:
    contexto = chamar("planejar_marcos", resposta)
    assert contexto.state[CHAVE_MARCOS] is None


def test_outra_ferramenta_nao_grava() -> None:
    contexto = chamar("comparar_cenarios", ENVELOPE)
    assert contexto.state[CHAVE_MARCOS] is None


def test_sem_contexto_nao_falha() -> None:
    tool = FerramentaFake("planejar_marcos")
    assert gravar_marcos(tool=tool, args={}, tool_context=None, tool_response=ENVELOPE) is None


def test_cadeia_agregada_grava_e_nao_substitui_o_resultado() -> None:
    callbacks.registrar("after_tool", gravar_marcos, ORDEM)
    contexto = ContextoFake()
    resultado = asyncio.run(
        callbacks.after_tool(
            tool=FerramentaFake("planejar_marcos"),
            args={},
            tool_context=contexto,
            tool_response=ENVELOPE,
        )
    )
    assert resultado is None  # nada substitui o resultado da ferramenta
    assert contexto.state[CHAVE_MARCOS] == ENVELOPE["dados"]
