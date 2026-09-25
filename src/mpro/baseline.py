"""Single source of truth for the MPRO Configuration 2 design baseline.

Every twin (software, chemical, web pages via tests) reads its numbers from
``baseline.json`` so that one change reaches all of them.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from types import MappingProxyType
from typing import Any


@lru_cache(maxsize=1)
def load() -> MappingProxyType:
    text = resources.files("mpro").joinpath("baseline.json").read_text(encoding="utf-8")
    return MappingProxyType(json.loads(text))


def value(section: str, key: str) -> Any:
    return load()[section][key]


def midpoint(section: str, key: str) -> float:
    """Return a scalar or the midpoint of a ``[low, high]`` design range."""
    raw = value(section, key)
    return sum(raw) / len(raw) if isinstance(raw, list) else float(raw)
