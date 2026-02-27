"""BBDSL → AI Knowledge Base exporter.

Produces a flat list of bidding rules in JSON or JSONL format suitable for
loading into LLM / RAG systems.

Each rule contains:
  - id:              full sequence path (e.g. "1C-1D")
  - sequence:        list of preceding bids (e.g. ["1C"])
  - bid:             this bid (e.g. "1D")
  - by:              seat role ("opener" / "responder" / ...)
  - system:          bidding system name
  - description:     free-text description
  - hand_constraint: dict of relevant constraint fields (non-None only)
  - artificial:      bool
  - alertable:       bool
  - forcing:         forcing level string or null
  - transfer_to:     transfer target or null
  - preemptive:      bool
  - context_text:    single natural-language string for RAG embedding

Output formats:
  json   — {"metadata": {...}, "rules": [...]}
  jsonl  — one JSON object per line (for streaming / chunked ingestion)

Example::

    from bbdsl.core.loader import load_document
    from bbdsl.exporters.ai_kb_exporter import export_ai_kb

    doc = load_document("examples/precision.bbdsl.yaml")
    rules = export_ai_kb(doc, fmt="jsonl", output_path="precision.jsonl")
    print(f"{len(rules)} rules exported")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# Forcing labels
# ---------------------------------------------------------------------------

_FORCING_EN = {
    "game": "GF",
    "invitational": "INV",
    "one_round": "F1",
    "signoff": "S/O",
    "none": "NF",
}
_FORCING_ZH = {
    "game": "成局強迫",
    "invitational": "邀請",
    "one_round": "一輪強迫",
    "signoff": "到叫",
    "none": "非強迫",
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hand_constraint_dict(hand: Any) -> dict:
    """Serialize a HandConstraint to a plain dict (non-None fields only)."""
    if hand is None:
        return {}
    result: dict = {}
    for field_name in (
        "hcp", "controls", "losing_tricks", "total_points",
        "clubs", "diamonds", "hearts", "spades",
        "bid_suit", "longest_suit", "second_suit",
    ):
        val = getattr(hand, field_name, None)
        if val is None:
            continue
        # Range-like objects
        if hasattr(val, "model_dump"):
            d = {k: v for k, v in val.model_dump().items() if v is not None}
            if d:
                result[field_name] = d
        else:
            result[field_name] = val

    # Shape
    shape = getattr(hand, "shape", None)
    if shape is not None:
        result["shape"] = shape

    # bool special
    for bf in ("four_card_major",):
        bv = getattr(hand, bf, None)
        if bv is not None:
            result[bf] = bv

    return result


def _flags(meaning: Any, locale: str) -> list[str]:
    """Collect human-readable flags from a BidMeaning."""
    if meaning is None:
        return []
    flags: list[str] = []
    if getattr(meaning, "artificial", False):
        flags.append("Alert" if locale != "zh-TW" else "人工")
    forcing_val = getattr(meaning, "forcing", None)
    if forcing_val is not None:
        fv = forcing_val.value if hasattr(forcing_val, "value") else str(forcing_val)
        label = (_FORCING_ZH if locale == "zh-TW" else _FORCING_EN).get(fv, fv)
        flags.append(label)
    if getattr(meaning, "preemptive", False):
        flags.append("先制" if locale == "zh-TW" else "Preemptive")
    transfer_to = getattr(meaning, "transfer_to", None)
    if transfer_to:
        flags.append(f"→{transfer_to}")
    return flags


def _build_context_text(
    path: list[str],
    bid: str,
    by: str | None,
    system_name: str,
    meaning: Any,
    locale: str,
) -> str:
    """Build a single natural-language context string for RAG embedding."""
    desc = _t(getattr(meaning, "description", None) if meaning else None, locale)
    flags = _flags(meaning, locale)
    flags_str = f" [{', '.join(flags)}]" if flags else ""
    by_str = by or "player"

    if not path:
        # Opening bid
        if locale == "zh-TW":
            base = f"在{system_name}制度中，{by_str}以{bid}開叫"
            show = f"表示：{desc}{flags_str}" if desc else flags_str
        else:
            base = f"In {system_name}, opening {bid} by {by_str}"
            show = f" shows: {desc}{flags_str}" if desc else flags_str
    else:
        seq_str = "-".join(path)
        if locale == "zh-TW":
            base = f"在{system_name}制度中，叫牌序列{seq_str}之後，{by_str}叫{bid}"
            show = f"表示：{desc}{flags_str}" if desc else flags_str
        else:
            base = f"In {system_name}, after {seq_str}, {by_str} bids {bid}"
            show = f" showing: {desc}{flags_str}" if desc else flags_str

    return base + show


def _rule_from_node(
    node: Any,
    path: list[str],
    system_name: str,
    locale: str,
) -> dict | None:
    """Build one rule dict from a BidNode. Returns None if no bid."""
    bid = getattr(node, "bid", None)
    if not bid:
        return None

    meaning = getattr(node, "meaning", None)
    by = getattr(node, "by", None) or ("opener" if not path else "responder")

    # Description
    desc = _t(getattr(meaning, "description", None) if meaning else None, locale)

    # Forcing
    forcing_val = getattr(meaning, "forcing", None) if meaning else None
    forcing_str = None
    if forcing_val is not None:
        forcing_str = forcing_val.value if hasattr(forcing_val, "value") else str(forcing_val)

    rule: dict = {
        "id": "-".join(path + [bid]) if path else bid,
        "sequence": list(path),
        "bid": bid,
        "by": by,
        "system": system_name,
        "description": desc,
        "hand_constraint": _hand_constraint_dict(getattr(meaning, "hand", None) if meaning else None),
        "artificial": bool(getattr(meaning, "artificial", False)) if meaning else False,
        "alertable": bool(getattr(meaning, "alertable", False)) if meaning else False,
        "forcing": forcing_str,
        "transfer_to": getattr(meaning, "transfer_to", None) if meaning else None,
        "preemptive": bool(getattr(meaning, "preemptive", False)) if meaning else False,
        "context_text": _build_context_text(path, bid, by, system_name, meaning, locale),
    }
    return rule


def _flatten_to_rules(
    nodes: list[Any],
    path: list[str],
    system_name: str,
    locale: str,
    result: list[dict],
) -> None:
    """Recursively walk BidNodes, appending one rule dict per bid."""
    for node in nodes:
        rule = _rule_from_node(node, path, system_name, locale)
        if rule is None:
            continue
        result.append(rule)

        bid = rule["bid"]
        current_path = path + [bid]

        for child in (getattr(node, "responses", None) or []):
            _flatten_to_rules([child], current_path, system_name, locale, result)
        for child in (getattr(node, "continuations", None) or []):
            _flatten_to_rules([child], current_path, system_name, locale, result)


def _convention_rules(
    doc: BBDSLDocument,
    system_name: str,
    locale: str,
) -> list[dict]:
    """Extract rules from doc.conventions (with conv-key prefix in id)."""
    rules: list[dict] = []
    for conv_key, conv in (doc.conventions or {}).items():
        for attr in ("responses", "bids"):
            nodes = getattr(conv, attr, None) or []
            sub: list[dict] = []
            _flatten_to_rules(nodes, [], system_name, locale, sub)
            # Prefix ids with convention key
            for r in sub:
                r["id"] = f"{conv_key}/{r['id']}"
                r["convention"] = conv_key
            rules.extend(sub)
    return rules


def _system_name(doc: BBDSLDocument, locale: str) -> str:
    name = doc.system.name
    if isinstance(name, dict):
        return name.get(locale) or name.get("en") or next(iter(name.values()), "System")
    return str(name)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _to_jsonl(rules: list[dict]) -> str:
    lines: list[str] = []
    for rule in rules:
        lines.append(json.dumps(rule, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


def _to_json(rules: list[dict], system_name: str, locale: str) -> str:
    payload = {
        "metadata": {
            "system": system_name,
            "locale": locale,
            "count": len(rules),
        },
        "rules": rules,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_ai_kb(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    fmt: str = "jsonl",
    locale: str = "en",
    suit_symbols: bool = False,  # reserved for future use
    include_conventions: bool = True,
) -> list[dict]:
    """Export a BBDSLDocument as an AI knowledge base.

    Args:
        doc: The BBDSL document.
        output_path: If given, write output to this file.
        fmt: Output format — ``"jsonl"`` (one record per line) or ``"json"``.
        locale: Language for descriptions (``"en"`` or ``"zh-TW"``).
        suit_symbols: (reserved) use ♠♥♦♣ in text.
        include_conventions: Whether to include rules from ``doc.conventions``.

    Returns:
        List of rule dicts.
    """
    system_name = _system_name(doc, locale)

    rules: list[dict] = []
    _flatten_to_rules(doc.openings or [], [], system_name, locale, rules)

    if include_conventions:
        rules.extend(_convention_rules(doc, system_name, locale))

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "jsonl":
            content = _to_jsonl(rules)
        else:
            content = _to_json(rules, system_name, locale)
        output_path.write_text(content, encoding="utf-8")

    return rules
