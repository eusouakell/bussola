"""Clock port for the governance package.

Governance code reads wall-clock and monotonic time only through a
:class:`Clock`, so tests can pin timestamps and latencies.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant, timezone-aware (UTC)."""
        ...

    def monotonic(self) -> float:
        """Monotonic seconds, only for measuring durations."""
        ...


class SystemClock:
    """Real clock (default)."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class FixedClock:
    """Test clock: returns a fixed instant until :meth:`advance` is called."""

    def __init__(self, instant: datetime | None = None) -> None:
        self._instant = instant or datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._instant

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, seconds: float) -> None:
        self._instant += timedelta(seconds=seconds)
        self._monotonic += seconds


def iso(instant: datetime) -> str:
    """ISO 8601 in UTC with a ``Z`` suffix (format used in ``session.state``)."""
    return instant.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
