"""Chaves e helpers de ``session.state`` (contratos §6; FR-012)."""

import pytest
from google.adk.sessions.state import State

from bussola_agent import estado
from bussola_agent.estado import (
    CHAVES,
    EstadoJornada,
    adicionar_fonte,
    definir_estado_jornada,
    estado_inicial,
    obter_ate_anomes,
    obter_estado_jornada,
    obter_id_usuario,
)

ANCORA = "36a21505-d6d4-42d3-b319-d51a133c7269"


def test_chaves_do_contrato() -> None:
    assert CHAVES == (
        "id_usuario",
        "ate_anomes",
        "estado_jornada",
        "objetivo",
        "cenarios",
        "cenario_escolhido",
        "ultimas_fontes",
        "consentimentos",
        "plano_id",
        "acompanhamento",
        "marcos",
    )
    assert estado.CHAVE_ID_USUARIO == "id_usuario"
    assert estado.CHAVE_ATE_ANOMES == "ate_anomes"
    assert estado.CHAVE_ULTIMAS_FONTES == "ultimas_fontes"


def test_estados_da_jornada() -> None:
    assert [e.value for e in EstadoJornada] == [
        "OBJETIVO",
        "ENTENDER",
        "ANTECIPAR",
        "ORIENTAR",
        "AGIR",
        "ACOMPANHAR",
    ]


def test_estado_inicial() -> None:
    inicial = estado_inicial(ANCORA.upper(), 202506)
    assert set(inicial) == set(CHAVES)
    assert inicial["id_usuario"] == ANCORA
    assert inicial["ate_anomes"] == 202506
    assert inicial["estado_jornada"] == "OBJETIVO"
    assert type(inicial["estado_jornada"]) is str
    assert inicial["ultimas_fontes"] == []
    assert inicial["consentimentos"] == {}
    assert inicial["acompanhamento"] == []
    for chave in ("objetivo", "cenarios", "cenario_escolhido", "plano_id", "marcos"):
        assert inicial[chave] is None


def test_estado_inicial_devolve_listas_novas() -> None:
    a = estado_inicial(ANCORA, 202506)
    b = estado_inicial(ANCORA, 202506)
    a["ultimas_fontes"].append({"x": 1})
    assert b["ultimas_fontes"] == []


@pytest.mark.parametrize(
    ("id_usuario", "ate_anomes"),
    [
        ("nao-e-uuid", 202506),
        ("36a21505-d6d4-12d3-b319-d51a133c7269", 202506),  # versão 1
        (ANCORA, 202413),
        (ANCORA, 202601),
        (ANCORA, True),
        (ANCORA, "202506"),
        (None, 202506),
    ],
)
def test_estado_inicial_rejeita_sem_eco(id_usuario: object, ate_anomes: object) -> None:
    with pytest.raises(ValueError) as erro:
        estado_inicial(id_usuario, ate_anomes)  # type: ignore[arg-type]
    assert "nao-e-uuid" not in str(erro.value)
    assert "202413" not in str(erro.value) and "202601" not in str(erro.value)


def test_obter_escopo() -> None:
    state = estado_inicial(ANCORA, 202512)
    assert obter_id_usuario(state) == ANCORA
    assert obter_ate_anomes(state) == 202512


@pytest.mark.parametrize("state", [{}, {"id_usuario": "x", "ate_anomes": 1}])
def test_obter_escopo_ausente_ou_invalido(state: dict) -> None:
    with pytest.raises(ValueError):
        obter_id_usuario(state)
    with pytest.raises(ValueError):
        obter_ate_anomes(state)


def test_estado_jornada_padrao_e_definicao() -> None:
    state: dict = {}
    assert obter_estado_jornada(state) is EstadoJornada.OBJETIVO
    definir_estado_jornada(state, EstadoJornada.ANTECIPAR)
    assert state["estado_jornada"] == "ANTECIPAR"
    assert type(state["estado_jornada"]) is str
    definir_estado_jornada(state, "AGIR")
    assert obter_estado_jornada(state) is EstadoJornada.AGIR


def test_estado_jornada_invalido() -> None:
    with pytest.raises(ValueError):
        definir_estado_jornada({}, "QUALQUER")
    with pytest.raises(ValueError):
        obter_estado_jornada({"estado_jornada": "QUALQUER"})


def test_adicionar_fonte_reatribui_e_limita() -> None:
    state = estado_inicial(ANCORA, 202506)
    original = state["ultimas_fontes"]
    fonte = {"ferramenta": "perfil_financeiro", "tabelas": [], "periodo": {}}
    adicionar_fonte(state, fonte)
    assert state["ultimas_fontes"] == [fonte]
    assert state["ultimas_fontes"] is not original
    assert original == []
    for i in range(30):
        adicionar_fonte(state, {"ferramenta": f"f{i}"}, limite=5)
    assert [f["ferramenta"] for f in state["ultimas_fontes"]] == [f"f{i}" for i in range(25, 30)]


def test_adicionar_fonte_sem_lista_previa() -> None:
    state: dict = {}
    adicionar_fonte(state, {"ferramenta": "resumo_mes"})
    assert state["ultimas_fontes"] == [{"ferramenta": "resumo_mes"}]
    with pytest.raises(TypeError):
        adicionar_fonte(state, ["nao", "e", "dict"])  # type: ignore[arg-type]


def test_helpers_com_state_do_adk_registram_delta() -> None:
    """Com o ``State`` do ADK, as escritas aparecem no delta da sessão."""
    delta: dict = {}
    state = State(value=estado_inicial(ANCORA, 202506), delta=delta)
    assert obter_id_usuario(state) == ANCORA
    assert obter_ate_anomes(state) == 202506
    definir_estado_jornada(state, EstadoJornada.ENTENDER)
    adicionar_fonte(state, {"ferramenta": "perfil_financeiro"})
    assert delta["estado_jornada"] == "ENTENDER"
    assert delta["ultimas_fontes"] == [{"ferramenta": "perfil_financeiro"}]
