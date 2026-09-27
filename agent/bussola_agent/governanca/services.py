"""Service locator of the governance package: registry, clock and screener.

Everything is built on first use, so importing :mod:`bussola_agent.governanca`
never opens the network. Tests swap any of the three with :func:`configure`
and go back to the defaults with :func:`reset`.

- registry: :func:`bussola_agent.persistencia_bq.default_registry` (the
  process-wide one, shared with 006);
- clock: :class:`~bussola_agent.governanca.clock.SystemClock`;
- screener: deterministic rules, layered with Model Armor when
  ``MODEL_ARMOR_TEMPLATE`` is set (see :mod:`bussola_agent.governanca.model_armor`).
"""

import threading
from typing import TYPE_CHECKING

from bussola_agent.governanca.clock import Clock, SystemClock
from bussola_agent.persistencia import RegistroApp
from bussola_agent.persistencia_bq import default_registry

if TYPE_CHECKING:
    from bussola_agent.governanca.guardrails import Screener

_lock = threading.Lock()
_registry: RegistroApp | None = None
_clock: Clock | None = None
_screener: "Screener | None" = None


def get_registry() -> RegistroApp:
    with _lock:
        if _registry is not None:
            return _registry
    return default_registry()


def get_clock() -> Clock:
    global _clock
    with _lock:
        if _clock is None:
            _clock = SystemClock()
        return _clock


def get_screener() -> "Screener":
    global _screener
    with _lock:
        if _screener is None:
            from bussola_agent.governanca.model_armor import build_screener

            _screener = build_screener()
        return _screener


def configure(
    registry: RegistroApp | None = None,
    clock: Clock | None = None,
    screener: "Screener | None" = None,
) -> None:
    """Replaces the given services (the others stay as they are)."""
    global _registry, _clock, _screener
    with _lock:
        if registry is not None:
            _registry = registry
        if clock is not None:
            _clock = clock
        if screener is not None:
            _screener = screener


def reset() -> None:
    """Back to the defaults (built again on next use)."""
    global _registry, _clock, _screener
    with _lock:
        _registry = None
        _clock = None
        _screener = None
