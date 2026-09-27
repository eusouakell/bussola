"""Simulated actions: ``criar_plano``, ``ativar_lembretes``, ``simular_contratacao``."""

import pytest
from governance_support import (
    ANCHOR,
    ATE_ANOMES,
    function_response_event,
    journey_state,
    tool_ctx,
)

from bussola_agent.governanca import acoes, services
from bussola_agent.governanca.envelope import (
    INVALID_INPUT,
    NOT_ALLOWED,
    PRODUCT_NOT_IN_CATALOG,
    UNAVAILABLE,
)
from bussola_agent.persistencia import RegistroEmMemoria, TipoEvento


def _types(registry: RegistroEmMemoria) -> list[str]:
    return [e.tipo_evento for e in registry.eventos]


# ---------------------------------------------------------------------------
# criar_plano
# ---------------------------------------------------------------------------


async def test_create_plan_with_a_named_scenario(registry: RegistroEmMemoria) -> None:
    ctx = tool_ctx(session_id="sess-9")
    result = await acoes.criar_plano("Caminho Equilibrado", ctx)

    data = result["dados"]
    assert {k: data[k] for k in ("cenario", "valor_alvo", "aporte_mensal", "prazo_meses")} == {
        "cenario": "equilibrado",
        "valor_alvo": 30000.0,
        "aporte_mensal": 1250.0,
        "prazo_meses": 24,
    }
    assert data["criado_em_anomes"] == ATE_ANOMES
    assert data["proximos_passos"][2] == {
        "texto": "Ativar lembretes mensais",
        "acao": "ativar_lembretes",
    }
    assert data["proximos_passos"][3]["acao"] == "simular_contratacao"
    assert result["fonte"] == {
        "ferramenta": "criar_plano",
        "tabelas": ["bussola_app.planos"],
        "periodo": {"inicio": ATE_ANOMES, "fim": ATE_ANOMES},
    }
    plan = registry.planos[0]
    assert plan.plano_id == data["plano_id"] == ctx.state["plano_id"]
    assert (plan.id_usuario, plan.session_id, plan.objetivo) == (
        ANCHOR,
        "sess-9",
        "Reserva de emergência",
    )
    assert _types(registry) == [TipoEvento.PLANO_CRIADO]
    assert registry.eventos[0].resumo["cenario"] == "equilibrado"


async def test_create_plan_ignores_numbers_in_the_arguments(registry: RegistroEmMemoria) -> None:
    result = await acoes.criar_plano("acelerado", tool_ctx())
    assert result["dados"]["aporte_mensal"] == 1666.67
    assert result["dados"]["prazo_meses"] == 18


async def test_create_plan_uses_the_comparison_period() -> None:
    state = journey_state(
        ultimas_fontes=[
            {"ferramenta": "comparar_cenarios", "periodo": {"inicio": 202501, "fim": 202506}}
        ]
    )
    result = await acoes.criar_plano("equilibrado", tool_ctx(state))
    assert result["fonte"]["periodo"] == {"inicio": 202501, "fim": 202506}


async def test_create_plan_other_path_from_the_session_events() -> None:
    chosen = function_response_event(
        "escolher_cenario",
        {
            "dados": {
                "cenario": "outro",
                "detalhes": {"valor_alvo": 30000.0, "aporte_mensal": 1000.0, "prazo_meses": 30},
            }
        },
    )
    result = await acoes.criar_plano("outro caminho", tool_ctx(events=[chosen]))
    assert result["dados"]["cenario"] == "outro"
    assert result["dados"]["aporte_mensal"] == 1000.0
    assert result["dados"]["prazo_meses"] == 30


async def test_create_plan_other_path_falls_back_to_the_simulation() -> None:
    simulated = function_response_event(
        "simular_objetivo",
        {
            "content": [
                {
                    "type": "text",
                    "text": '{"dados": {"valor_alvo": 20000.0, "aporte_mensal": 900.0, '
                    '"prazo_meses": 23}}',
                }
            ]
        },
    )
    failed = function_response_event("simular_objetivo", {"erro": {"codigo": "X", "mensagem": ""}})
    result = await acoes.criar_plano("outro", tool_ctx(events=[simulated, failed]))
    assert result["dados"]["valor_alvo"] == 20000.0
    assert result["dados"]["aporte_mensal"] == 900.0


async def test_create_plan_defaults_to_the_chosen_scenario() -> None:
    result = await acoes.criar_plano("", tool_ctx(journey_state(cenario_escolhido="conservador")))
    assert result["dados"]["cenario"] == "conservador"


@pytest.mark.parametrize(
    ("state", "scenario", "message"),
    [
        (journey_state(id_usuario="nao-uuid"), "equilibrado", acoes.MSG_NO_SCOPE),
        (journey_state(ate_anomes=202601), "equilibrado", acoes.MSG_NO_SCOPE),
        (journey_state(plano_id="p-1"), "equilibrado", acoes.MSG_PLAN_ACTIVE),
        (journey_state(objetivo=None), "equilibrado", acoes.MSG_NO_GOAL),
        (journey_state(cenario_escolhido=None), "turbo", acoes.MSG_UNKNOWN_SCENARIO),
        (journey_state(cenarios=None), "equilibrado", acoes.MSG_NO_NUMBERS),
        (journey_state(), "outro", acoes.MSG_NO_NUMBERS),
    ],
)
async def test_create_plan_rejects(
    state: dict, scenario: str, message: str, registry: RegistroEmMemoria
) -> None:
    result = await acoes.criar_plano(scenario, tool_ctx(state))
    assert result == {"erro": {"codigo": INVALID_INPUT, "mensagem": message}}
    assert registry.planos == [] and registry.eventos == []


class _FailingRegistry(RegistroEmMemoria):
    def registrar_plano(self, plano):  # noqa: ANN001, ANN201
        raise RuntimeError("bq fora")


async def test_create_plan_registry_failure() -> None:
    services.configure(registry=_FailingRegistry())
    ctx = tool_ctx()
    result = await acoes.criar_plano("equilibrado", ctx)
    assert result["erro"] == {"codigo": UNAVAILABLE, "mensagem": acoes.MSG_SAVE_FAILED}
    assert "plano_id" not in ctx.state or ctx.state["plano_id"] is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Caminho Acelerado", "acelerado"),
        ("o conservador", "conservador"),
        ("cenário equilibrado.", "equilibrado"),
        ("personalizado", "outro"),
        ("turbo", None),
        (3, None),
    ],
)
def test_normalize_scenario(value: object, expected: str | None) -> None:
    assert acoes.normalize_scenario(value) == expected


# ---------------------------------------------------------------------------
# ativar_lembretes / simular_contratacao / compartilhar_dados
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "expected"), [("", "mensal"), ("Semanal", "semanal")])
async def test_activate_reminders(value: str, expected: str, registry: RegistroEmMemoria) -> None:
    result = await acoes.ativar_lembretes(value, tool_ctx())
    assert result["dados"]["acao"] == "ativar_lembretes"
    assert result["dados"]["status"] == "ok"
    assert result["dados"]["frequencia"] == expected
    assert result["dados"]["mensagem"]
    assert result["avisos"]
    assert _types(registry) == [TipoEvento.ACAO_EXECUTADA]


async def test_activate_reminders_bad_frequency(registry: RegistroEmMemoria) -> None:
    result = await acoes.ativar_lembretes("de hora em hora", tool_ctx())
    assert result["erro"]["codigo"] == INVALID_INPUT
    assert registry.eventos == []


async def test_simulate_a_catalog_product(registry: RegistroEmMemoria) -> None:
    result = await acoes.simular_contratacao("credito_imobiliario", tool_ctx())
    data = result["dados"]
    assert (data["acao"], data["status"], data["produto_id"]) == (
        "simular_contratacao",
        "ok",
        "credito_imobiliario",
    )
    assert data["mensagem"] == acoes.MSG_SIMULATION_OK
    assert data["fonte_oficial"].startswith("https://")
    assert result["avisos"] == [acoes.SIMULATION_WARNING]
    assert registry.eventos[0].resumo == {
        "acao": "simular_contratacao",
        "produto_id": "credito_imobiliario",
        "simulada": True,
    }


@pytest.mark.parametrize("product", ["emprestimo_pessoal", "cdb_renda_fixa", ""])
async def test_simulate_outside_the_catalog(product: str, registry: RegistroEmMemoria) -> None:
    result = await acoes.simular_contratacao(product, tool_ctx())
    assert result == {
        "erro": {"codigo": PRODUCT_NOT_IN_CATALOG, "mensagem": acoes.MSG_NOT_IN_CATALOG}
    }
    assert TipoEvento.ACAO_EXECUTADA not in _types(registry)


async def test_share_data_is_never_executed(registry: RegistroEmMemoria) -> None:
    result = await acoes.compartilhar_dados("banco_x", tool_ctx())
    assert result["erro"]["codigo"] == NOT_ALLOWED
    assert _types(registry) == [TipoEvento.GUARDRAIL_BLOQUEIO]
