"""``RegistroBigQuery`` against real BigQuery (``make test-bq``, needs ADC).

Writes only to ``bussola_app_dev`` (never ``bussola_app``) and deletes
nothing. Each run uses new ids, so reruns only append rows.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from governance_support import ANCHOR

from bussola_agent.persistencia import Consentimento, EventoAuditoria, Plano
from bussola_agent.persistencia_bq import RegistroBigQuery

pytestmark = pytest.mark.bq

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or "batalha-time-07-lkbv"
DEV_DATASET = "bussola_app_dev"


@pytest.fixture
def registry() -> RegistroBigQuery:
    registry = RegistroBigQuery(project=PROJECT, dataset=DEV_DATASET)
    assert registry.dataset == DEV_DATASET
    return registry


def test_writes_and_reads_a_plan_in_dev(registry: RegistroBigQuery) -> None:
    session_id = f"teste-005-{uuid.uuid4()}"
    now = datetime.now(UTC)
    plan = Plano(
        session_id=session_id,
        id_usuario=ANCHOR,
        objetivo="Reserva de emergência (teste 005)",
        valor_alvo=30000.0,
        prazo_meses=24,
        cenario="equilibrado",
        aporte_mensal=1250.0,
        ate_anomes=202506,
        criado_em=now,
    )
    registry.registrar_plano(plan)
    registry.registrar_consentimento(
        Consentimento(
            session_id=session_id,
            plano_id=plan.plano_id,
            acao="criar_plano",
            decisao="aceito",
            texto_apresentado="Posso criar o seu plano: teste? Responda **sim** ou **não**.",
            ts=now,
        )
    )
    registry.registrar_evento(
        EventoAuditoria(
            session_id=session_id,
            estado="AGIR",
            tipo_evento="plano_criado",
            ferramenta="criar_plano",
            resumo={"plano_id": plan.plano_id, "cenario": "equilibrado"},
            ts=now,
        )
    )

    # A new registry has no local cache: the read goes to BigQuery (parameterized).
    fresh = RegistroBigQuery(project=PROJECT, dataset=DEV_DATASET)
    found = fresh.obter_plano(plan.plano_id)
    assert found is not None
    assert found.plano_id == plan.plano_id
    assert found.aporte_mensal == 1250.0
    assert found.id_usuario == ANCHOR
