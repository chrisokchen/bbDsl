"""BBDSL HandConstraint ↔ Dealer script conditions bridge.

The Dealer program (Hans van Staveren) uses a C-like condition language to
specify hand constraints for deal generation.  This module provides:

  constraint_to_dealer(constraint, seat="south") -> str
      Convert a BBDSL HandConstraint to a Dealer condition string.

  dealer_to_constraint(condition, seat="south") -> HandConstraint
      Parse a Dealer condition string back to a BBDSL HandConstraint.

  openings_to_dealer_script(doc, seat="south", locale="en") -> str
      Generate a complete Dealer script template for all system openings.

Supported Dealer functions:
  hcp(seat)           — high-card points
  spades/hearts/diamonds/clubs(seat)  — suit length
  shape(seat, ...)    — shape pattern
  loser(seat)         — losing trick count
  aces(seat), kings(seat)  — specific honour counts (for controls)

Example::

    from bbdsl.core.dealer_bridge import constraint_to_dealer, dealer_to_constraint
    from bbdsl.models.bid import HandConstraint
    from bbdsl.models.common import Range

    hc = HandConstraint(hcp=Range(min=15, max=17), shape={"ref": "balanced"})
    print(constraint_to_dealer(hc))
    # hcp(south) >= 15 && hcp(south) <= 17 && shape(south, any 4333 + any 4432 + any 5332)

    hc2 = dealer_to_constraint("hcp(south) >= 16 && spades(south) >= 5")
    print(hc2.hcp)    # Range(min=16)
    print(hc2.spades) # Range(min=5)
"""

from __future__ import annotations

import re
from typing import Any

from bbdsl.models.bid import HandConstraint
from bbdsl.models.common import Range
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# Shape pattern mapping
# ---------------------------------------------------------------------------

_BALANCED_DEALER = "any 4333 + any 4432 + any 5332"
_SEMI_BALANCED_DEALER = "any 5422 + any 6322"

# Also accept the alternative spellings on input
_SHAPE_TO_REF: dict[str, str] = {
    _BALANCED_DEALER: "balanced",
    _SEMI_BALANCED_DEALER: "semi_balanced",
    # Compact variants
    "any4333+any4432+any5332": "balanced",
    "any5422+any6322": "semi_balanced",
}

_REF_TO_DEALER: dict[str, str] = {
    "balanced": _BALANCED_DEALER,
    "semi_balanced": _SEMI_BALANCED_DEALER,
    "semi-balanced": _SEMI_BALANCED_DEALER,
}


# ---------------------------------------------------------------------------
# constraint_to_dealer
# ---------------------------------------------------------------------------

def _range_clauses(attr: str, r: Range | None, seat: str) -> list[str]:
    """Return Dealer condition clauses for a Range field."""
    if r is None:
        return []
    clauses: list[str] = []
    if r.exactly is not None:
        clauses.append(f"{attr}({seat}) == {r.exactly}")
        return clauses
    if r.min is not None:
        clauses.append(f"{attr}({seat}) >= {r.min}")
    if r.max is not None:
        clauses.append(f"{attr}({seat}) <= {r.max}")
    return clauses


def constraint_to_dealer(constraint: Any, seat: str = "south") -> str:
    """Convert a BBDSL HandConstraint to a Dealer script condition string.

    Args:
        constraint: A ``HandConstraint`` instance (or None).
        seat: The Dealer seat name (default ``"south"``).

    Returns:
        Dealer condition string, or ``""`` if constraint is None / empty.
    """
    if constraint is None:
        return ""

    parts: list[str] = []

    # HCP
    parts.extend(_range_clauses("hcp", getattr(constraint, "hcp", None), seat))

    # Suit lengths
    for suit in ("spades", "hearts", "diamonds", "clubs"):
        parts.extend(_range_clauses(suit, getattr(constraint, suit, None), seat))

    # Shape
    shape = getattr(constraint, "shape", None)
    if shape is not None:
        ref: str | None = None
        if isinstance(shape, dict):
            ref = shape.get("ref")
        elif isinstance(shape, str) and shape not in ("any", ""):
            ref = shape
        if ref is not None:
            dealer_shape = _REF_TO_DEALER.get(ref)
            if dealer_shape:
                parts.append(f"shape({seat}, {dealer_shape})")

    # Controls: (aces*2 + kings) >= N
    controls = getattr(constraint, "controls", None)
    if controls is not None:
        if controls.exactly is not None:
            parts.append(
                f"(aces({seat})*2 + kings({seat})) == {controls.exactly}"
            )
        else:
            if controls.min is not None:
                parts.append(
                    f"(aces({seat})*2 + kings({seat})) >= {controls.min}"
                )
            if controls.max is not None:
                parts.append(
                    f"(aces({seat})*2 + kings({seat})) <= {controls.max}"
                )

    # Losing tricks
    lt = getattr(constraint, "losing_tricks", None)
    if lt is not None:
        if lt.exactly is not None:
            parts.append(f"loser({seat}) == {lt.exactly}")
        else:
            if lt.min is not None:
                parts.append(f"loser({seat}) >= {lt.min}")
            if lt.max is not None:
                parts.append(f"loser({seat}) <= {lt.max}")

    # Total points — approximate as hcp + dist (Dealer has no native total_points)
    tp = getattr(constraint, "total_points", None)
    if tp is not None:
        if tp.min is not None:
            parts.append(f"(hcp({seat}) + dist({seat})) >= {tp.min}")
        if tp.max is not None:
            parts.append(f"(hcp({seat}) + dist({seat})) <= {tp.max}")

    return " && ".join(parts)


# ---------------------------------------------------------------------------
# dealer_to_constraint
# ---------------------------------------------------------------------------

def dealer_to_constraint(condition: str, seat: str = "south") -> HandConstraint:
    """Parse a Dealer condition string into a BBDSL HandConstraint.

    Handles the subset of Dealer syntax produced by ``constraint_to_dealer``.
    Unrecognised clauses are silently ignored.

    Args:
        condition: Dealer condition string (may contain ``&&``-joined clauses).
        seat: The seat name to expect in the condition (default ``"south"``).

    Returns:
        A :class:`HandConstraint` instance.
    """
    # Escape seat for regex
    seat_re = re.escape(seat)

    kwargs: dict[str, Any] = {}

    # HCP
    for m in re.finditer(rf"hcp\({seat_re}\)\s*(>=|<=|==)\s*(\d+)", condition):
        op, val = m.group(1), int(m.group(2))
        r: dict[str, int] = kwargs.get("hcp") or {}
        if op == ">=":
            r["min"] = val
        elif op == "<=":
            r["max"] = val
        else:  # ==
            r["min"] = val
            r["max"] = val
        kwargs["hcp"] = r

    # Suit lengths
    for suit in ("spades", "hearts", "diamonds", "clubs"):
        for m in re.finditer(
            rf"{suit}\({seat_re}\)\s*(>=|<=|==)\s*(\d+)", condition
        ):
            op, val = m.group(1), int(m.group(2))
            r = kwargs.get(suit) or {}
            if op == ">=":
                r["min"] = val
            elif op == "<=":
                r["max"] = val
            else:
                r["min"] = val
                r["max"] = val
            kwargs[suit] = r

    # Shape — try known patterns
    for dealer_pat, ref in _SHAPE_TO_REF.items():
        normalised = re.sub(r"\s+", " ", condition)
        if dealer_pat.lower() in normalised.lower():
            kwargs["shape"] = {"ref": ref}
            break
    # Also match shape(seat, <pattern>) generically
    sm = re.search(rf"shape\({seat_re},\s*([^)]+)\)", condition)
    if sm and "shape" not in kwargs:
        inner = re.sub(r"\s+", "", sm.group(1)).lower()
        if "shape" not in kwargs:
            for dealer_pat, ref in _SHAPE_TO_REF.items():
                if re.sub(r"\s+", "", dealer_pat).lower() == inner:
                    kwargs["shape"] = {"ref": ref}
                    break

    # Controls: (aces*2 + kings) op N
    for m in re.finditer(
        rf"\(aces\({seat_re}\)\*2\s*\+\s*kings\({seat_re}\)\)\s*(>=|<=|==)\s*(\d+)",
        condition,
    ):
        op, val = m.group(1), int(m.group(2))
        r = kwargs.get("controls") or {}
        if op == ">=":
            r["min"] = val
        elif op == "<=":
            r["max"] = val
        else:
            r["min"] = val
            r["max"] = val
        kwargs["controls"] = r

    # Losing tricks: loser(seat) op N
    for m in re.finditer(rf"loser\({seat_re}\)\s*(>=|<=|==)\s*(\d+)", condition):
        op, val = m.group(1), int(m.group(2))
        r = kwargs.get("losing_tricks") or {}
        if op == ">=":
            r["min"] = val
        elif op == "<=":
            r["max"] = val
        else:
            r["min"] = val
            r["max"] = val
        kwargs["losing_tricks"] = r

    # Convert sub-dicts to Range objects
    range_fields = (
        "hcp", "controls", "losing_tricks",
        "spades", "hearts", "diamonds", "clubs",
    )
    for field in range_fields:
        if field in kwargs and isinstance(kwargs[field], dict):
            kwargs[field] = Range(**kwargs[field])

    return HandConstraint(**kwargs)


# ---------------------------------------------------------------------------
# openings_to_dealer_script
# ---------------------------------------------------------------------------

def _system_name(doc: BBDSLDocument, locale: str) -> str:
    name = doc.system.name
    if isinstance(name, dict):
        return name.get(locale) or name.get("en") or next(iter(name.values()), "System")
    return str(name)


def openings_to_dealer_script(
    doc: BBDSLDocument,
    seat: str = "south",
    locale: str = "en",
) -> str:
    """Generate a Dealer script template for all opening bids in *doc*.

    Each opening that has a hand constraint gets its own ``generate`` block.
    Blocks without a constraint get an empty condition (comment only).

    Args:
        doc: The BBDSL document.
        seat: Dealer seat name (default ``"south"``).
        locale: Language for the system name header.

    Returns:
        A Dealer-format script string.
    """
    system_name = _system_name(doc, locale)
    lines: list[str] = [
        f"# BBDSL → Dealer script",
        f"# System: {system_name}",
        f"# Seat: {seat}",
        f"# Generated by bbdsl export dealer",
        "",
    ]

    for opening in doc.openings or []:
        bid = getattr(opening, "bid", None)
        if not bid:
            continue
        meaning = getattr(opening, "meaning", None)
        hand = getattr(meaning, "hand", None) if meaning else None
        condition = constraint_to_dealer(hand, seat=seat) if hand else ""

        # Description comment
        desc = None
        if meaning:
            desc_val = getattr(meaning, "description", None)
            if desc_val:
                if isinstance(desc_val, dict):
                    desc = desc_val.get(locale) or desc_val.get("en") or ""
                else:
                    desc = str(desc_val)

        lines.append(f"# --- Opening {bid}" + (f": {desc}" if desc else "") + " ---")
        lines.append("generate")
        lines.append("")
        lines.append("condition")
        if condition:
            lines.append(f"  {condition}")
        else:
            lines.append("  # (no constraint specified)")
        lines.append("")
        lines.append("action")
        lines.append("  printall")
        lines.append("")

    return "\n".join(lines)
