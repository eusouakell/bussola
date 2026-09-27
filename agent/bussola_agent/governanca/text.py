"""Text helpers shared by the consent parser and the guardrails."""

import re
import unicodedata

_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lowercase, no accents, single spaces (same as the front simulator)."""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return _SPACES.sub(" ", stripped.lower()).strip()


def collapse_spaces(text: str) -> str:
    return _SPACES.sub(" ", text).strip()
