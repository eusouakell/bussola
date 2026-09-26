"""Encadeador de callbacks (contratos §6; TS-04, AC-08, FR-013)."""

import inspect
from typing import Any

import pytest

from bussola_agent import callbacks
from bussola_agent.callbacks import FASES, registrar

# Argumentos de cada agregado, como o ADK 2.10 passa (por palavra-chave).
ARGS_POR_FASE: dict[str, dict[str, Any]] = {
    "before_model": {"callback_context": "ctx", "llm_request": "req"},
    "after_model": {"callback_context": "ctx", "llm_response": "resp"},
    "before_tool": {"tool": "ferramenta", "args": {"a": 1}, "tool_context": "tctx"},
    "after_tool": {
        "tool": "ferramenta",
        "args": {"a": 1},
        "tool_context": "tctx",
        "tool_response": {"dados": {}},
    },
}


def _agregado(fase: str):
    return getattr(callbacks, fase)


def test_fases_do_contrato() -> None:
    assert FASES == ("before_model", "after_model", "before_tool", "after_tool")


@pytest.mark.parametrize("fase", FASES)
def test_agregados_sao_async_com_assinatura_do_adk(fase: str) -> None:
    agregado = _agregado(fase)
    assert inspect.iscoroutinefunction(agregado)
    assert list(inspect.signature(agregado).parameters) == list(ARGS_POR_FASE[fase])


@pytest.mark.parametrize("fase", FASES)
async def test_cadeia_vazia_devolve_none(fase: str) -> None:
    assert await _agregado(fase)(**ARGS_POR_FASE[fase]) is None


@pytest.mark.parametrize("fase", FASES)
async def test_curto_circuito_ordem_10_antes_da_20(fase: str) -> None:
    """TS-04 / AC-08: a de ordem 10 devolve valor; a de ordem 20 não roda."""
    chamadas: list[int] = []

    def ordem_20(**_: Any) -> str:
        chamadas.append(20)
        return "vinte"

    def ordem_10(**_: Any) -> str:
        chamadas.append(10)
        return "dez"

    registrar(fase, ordem_20, 20)  # registrada primeiro, roda depois
    registrar(fase, ordem_10, 10)
    assert await _agregado(fase)(**ARGS_POR_FASE[fase]) == "dez"
    assert chamadas == [10]


@pytest.mark.parametrize("fase", FASES)
async def test_none_segue_a_cadeia_e_recebe_kwargs(fase: str) -> None:
    recebidos: list[dict[str, Any]] = []

    def observa(**kwargs: Any) -> None:
        recebidos.append(kwargs)

    async def responde(**_: Any) -> dict:
        return {"ok": True}

    registrar(fase, observa, 5)
    registrar(fase, responde, 50)
    assert await _agregado(fase)(**ARGS_POR_FASE[fase]) == {"ok": True}
    assert recebidos == [ARGS_POR_FASE[fase]]


async def test_sync_e_async_misturados_em_ordem() -> None:
    ordem: list[str] = []

    async def a(**_: Any) -> None:
        ordem.append("a30")

    def b(**_: Any) -> None:
        ordem.append("b10")

    async def c(**_: Any) -> str:
        ordem.append("c90")
        return "fim"

    registrar("before_tool", c, 90)
    registrar("before_tool", a, 30)
    registrar("before_tool", b, 10)
    assert await callbacks.before_tool(**ARGS_POR_FASE["before_tool"]) == "fim"
    assert ordem == ["b10", "a30", "c90"]


async def test_empate_segue_ordem_de_registro() -> None:
    ordem: list[str] = []
    for nome in ("primeira", "segunda", "terceira"):
        registrar("after_tool", lambda nome=nome, **_: ordem.append(nome), 10)
    assert await callbacks.after_tool(**ARGS_POR_FASE["after_tool"]) is None
    assert ordem == ["primeira", "segunda", "terceira"]


async def test_valor_falso_nao_nulo_interrompe() -> None:
    """O critério é ``is not None``: ``{}`` também interrompe a cadeia."""
    registrar("before_tool", lambda **_: {}, 10)
    registrar("before_tool", lambda **_: {"nao": "roda"}, 20)
    assert await callbacks.before_tool(**ARGS_POR_FASE["before_tool"]) == {}


async def test_fases_sao_independentes() -> None:
    registrar("before_model", lambda **_: "so_before_model", 10)
    assert await callbacks.after_model(**ARGS_POR_FASE["after_model"]) is None
    assert await callbacks.before_model(**ARGS_POR_FASE["before_model"]) == "so_before_model"


def test_fase_invalida_gera_value_error() -> None:
    with pytest.raises(ValueError):
        registrar("before_agent", lambda **_: None, 10)
    with pytest.raises(ValueError):
        callbacks.registrados("qualquer")


def test_funcao_e_ordem_invalidas() -> None:
    with pytest.raises(TypeError):
        registrar("before_tool", "nao_chamavel", 10)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registrar("before_tool", lambda **_: None, "10")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        registrar("before_tool", lambda **_: None, True)


async def test_excecao_propaga() -> None:
    def falha(**_: Any) -> None:
        raise RuntimeError("falha no callback")

    registrar("after_model", falha, 10)
    with pytest.raises(RuntimeError):
        await callbacks.after_model(**ARGS_POR_FASE["after_model"])


def test_limpar_esvazia_todas_as_fases() -> None:
    for fase in FASES:
        registrar(fase, lambda **_: None, 1)
    callbacks.limpar()
    assert all(callbacks.registrados(fase) == [] for fase in FASES)


def test_ordens_negativas_e_registrados() -> None:
    def x(**_: Any) -> None: ...

    def y(**_: Any) -> None: ...

    registrar("after_tool", x, 90)
    registrar("after_tool", y, -1)
    assert callbacks.registrados("after_tool") == [y, x]
