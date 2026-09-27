"""Fixtures of the cycle 005 tests (no network, no GCP, no real LLM).

- ``governance`` (autouse): after the common cleanup, the services get a
  :class:`RegistroEmMemoria`, a :class:`FixedClock` and the rule screener, the
  in-process caches are reset and :func:`register` runs again.
"""

from collections.abc import Iterator

import pytest

from bussola_agent import persistencia_bq
from bussola_agent.governanca import audit, consent, guardrails, register, services
from bussola_agent.governanca.clock import FixedClock
from bussola_agent.governanca.guardrails import RuleScreener
from bussola_agent.persistencia import RegistroEmMemoria


@pytest.fixture(autouse=True)
def governance(registros_limpos: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("MODEL_ARMOR_TEMPLATE", raising=False)
    services.configure(registry=RegistroEmMemoria(), clock=FixedClock(), screener=RuleScreener())
    consent.reset_used_ids()
    audit.reset()
    guardrails.reset()
    register()
    yield
    services.reset()
    persistencia_bq.set_default_registry(None)
    consent.reset_used_ids()
    audit.reset()
    guardrails.reset()


@pytest.fixture
def registry() -> RegistroEmMemoria:
    current = services.get_registry()
    assert isinstance(current, RegistroEmMemoria)
    return current


@pytest.fixture
def clock() -> FixedClock:
    current = services.get_clock()
    assert isinstance(current, FixedClock)
    return current
