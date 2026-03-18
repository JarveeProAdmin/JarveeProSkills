"""Reusable TaskParameter blueprints for JarveePro payloads."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Iterable, List, Optional


PARAMETER_LIBRARY: Dict[str, Dict[str, Any]] = {
    "Url": {
        "Parameters": [],
        "SingleUseData": {"Min": 1, "Max": 1},
        "UseNoData": False,
        "AccountUseNum": 1,
        "UnitUseNum": {"Min": 1, "Max": 1},
        "UseNum": 100,
        "RandomUse": False,
        "AiSetting": None,
    },
    "CommentText": {
        "Parameters": [],
        "SingleUseData": {"Min": 1, "Max": 1},
        "UseNoData": False,
        "AccountUseNum": 1,
        "UnitUseNum": {"Min": 1, "Max": 1},
        "UseNum": 100,
        "RandomUse": True,
        "AiSetting": None,
    },
    "Search": {
        "Parameters": [],
        "SingleUseData": {"Min": 1, "Max": 1},
        "UseNoData": False,
        "AccountUseNum": 1,
        "UnitUseNum": {"Min": 1, "Max": 1},
        "UseNum": 100,
        "RandomUse": True,
        "AiSetting": None,
    },
}


def deep_update(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def build_parameter_block(name: str, values: Iterable[str], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if name not in PARAMETER_LIBRARY:
        raise ValueError(f"Unknown parameter template '{name}'")
    block = deepcopy(PARAMETER_LIBRARY[name])
    block["Parameters"] = list(values)
    if overrides:
        deep_update(block, deepcopy(overrides))
    return block


__all__ = ["build_parameter_block", "PARAMETER_LIBRARY"]
