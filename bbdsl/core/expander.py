"""foreach_suit expansion engine."""

from __future__ import annotations

import copy
import re
from typing import Any

from bbdsl.models.system import BBDSLDocument

SUIT_META: dict[str, dict[str, Any]] = {
    "C": {
        "lower": "c", "zh-TW": "梅花", "en": "clubs", "symbol": "♣",
        "rank": 0, "color": "black", "group": "minor",
        "other": "D", "transfer_from": None,
    },
    "D": {
        "lower": "d", "zh-TW": "方塊", "en": "diamonds", "symbol": "♦",
        "rank": 1, "color": "red", "group": "minor",
        "other": "C", "transfer_from": "C",
    },
    "H": {
        "lower": "h", "zh-TW": "紅心", "en": "hearts", "symbol": "♥",
        "rank": 2, "color": "red", "group": "major",
        "other": "S", "transfer_from": "D",
    },
    "S": {
        "lower": "s", "zh-TW": "黑桃", "en": "spades", "symbol": "♠",
        "rank": 3, "color": "black", "group": "major",
        "other": "H", "transfer_from": "H",
    },
}

DEFAULT_SUIT_GROUPS: dict[str, list[str]] = {
    "majors": ["H", "S"],
    "minors": ["C", "D"],
    "reds": ["H", "D"],
    "blacks": ["S", "C"],
    "all": ["C", "D", "H", "S"],
}

MAX_NESTING = 2


def _build_replacements(variable: str, suit: str) -> dict[str, str]:
    """Build all replacement pairs for a variable+suit combination."""
    meta = SUIT_META[suit]
    replacements = {f"${{{variable}}}": suit}
    for prop, value in meta.items():
        if value is not None:
            replacements[f"${{{variable}.{prop}}}"] = str(value)
    return replacements


def _replace_in_string(s: str, replacements: dict[str, str]) -> str:
    """Apply all variable replacements to a string."""
    for pattern, value in replacements.items():
        s = s.replace(pattern, value)
    return s


def _replace_in_obj(obj: Any, replacements: dict[str, str]) -> Any:
    """Recursively replace variables in dicts, lists, and strings."""
    if isinstance(obj, str):
        return _replace_in_string(obj, replacements)
    if isinstance(obj, dict):
        return {
            _replace_in_string(k, replacements) if isinstance(k, str) else k:
            _replace_in_obj(v, replacements)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_replace_in_obj(item, replacements) for item in obj]
    return obj


def _expand_node(
    node: dict,
    suit_groups: dict[str, list[str]],
    depth: int = 0,
) -> list[dict]:
    """Expand a single node's foreach_suit into multiple concrete nodes."""
    fs = node.get("foreach_suit")
    if not fs:
        # No expansion needed, but still recurse into children
        result = copy.deepcopy(node)
        for key in ("responses", "continuations"):
            children = result.get(key)
            if children:
                result[key] = _expand_children(children, suit_groups, depth)
        return [result]

    if depth >= MAX_NESTING:
        raise ValueError(
            f"foreach_suit nesting exceeds maximum depth of {MAX_NESTING}"
        )

    variable = fs["variable"]
    group_name = fs["over"]
    suits = suit_groups.get(group_name, DEFAULT_SUIT_GROUPS.get(group_name, []))

    expanded = []
    for suit in suits:
        replacements = _build_replacements(variable, suit)
        new_node = copy.deepcopy(node)
        del new_node["foreach_suit"]
        new_node = _replace_in_obj(new_node, replacements)
        new_node["_expanded_from"] = {"foreach_suit": variable, "value": suit}
        # Recurse into children
        for key in ("responses", "continuations"):
            children = new_node.get(key)
            if children:
                new_node[key] = _expand_children(children, suit_groups, depth + 1)
        expanded.append(new_node)

    return expanded


def _expand_children(
    nodes: list[dict],
    suit_groups: dict[str, list[str]],
    depth: int = 0,
) -> list[dict]:
    """Expand a list of child nodes."""
    result = []
    for node in nodes:
        result.extend(_expand_node(node, suit_groups, depth))
    return result


def expand_document(doc: BBDSLDocument) -> dict:
    """Expand all foreach_suit directives in a document.

    Works on dict representation to avoid Pydantic model constraints
    during expansion (e.g., _expanded_from metadata).

    Returns the expanded document as a dict.
    """
    data = doc.model_dump(by_alias=True, exclude_none=True)

    # Resolve suit_groups from definitions or use defaults
    suit_groups = DEFAULT_SUIT_GROUPS.copy()
    defs = data.get("definitions") or {}
    if defs.get("suit_groups"):
        suit_groups.update(defs["suit_groups"])

    # Expand openings
    if "openings" in data:
        data["openings"] = _expand_children(data["openings"], suit_groups)

    # Expand defensive entries
    if "defensive" in data:
        for entry in data["defensive"]:
            if "actions" in entry and isinstance(entry["actions"], list):
                entry["actions"] = _expand_children(entry["actions"], suit_groups)

    return data


def count_expanded(data: dict) -> int:
    """Count nodes that were expanded from foreach_suit."""
    count = 0

    def _walk(nodes: list[dict] | None) -> None:
        nonlocal count
        if not nodes:
            return
        for node in nodes:
            if "_expanded_from" in node:
                count += 1
            _walk(node.get("responses"))
            _walk(node.get("continuations"))

    _walk(data.get("openings"))
    return count
