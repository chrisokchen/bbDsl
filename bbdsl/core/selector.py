"""selection_rules evaluator and bid selection engine.

Supports the Dealer-compatible condition expression language:
    hcp >= 16
    hcp >= 11 && hcp <= 15 && hearts >= 5
    shape in balanced
    longest_suit >= 7 && hcp <= 10
    true

Variables available in conditions:
    hcp, controls, losers
    spades, hearts, diamonds, clubs
    longest_suit, second_suit
    shape   (string: "balanced", "semi_balanced", or None)

Operators: >= <= == != > < && || ! ()
Special: shape in <name>  →  shape == "<name>"
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Condition string transformer → Python expression
# ---------------------------------------------------------------------------

# Pattern to detect "shape in <identifier>" and convert to equality check
_SHAPE_IN_RE = re.compile(r'\bshape\s+in\s+(\w+)')

# Replace BML operators with Python equivalents
_OP_REPLACEMENTS = [
    ('&&', ' and '),
    ('||', ' or '),
]

# Replace bare !expr with not expr (careful: don't touch != )
_NOT_RE = re.compile(r'(?<!=)!(?!=)')


def _transform_condition(condition: str) -> str:
    """Transform a BBDSL condition expression to a valid Python expression."""
    expr = condition.strip()

    # "true" literal
    if expr.lower() == 'true':
        return 'True'
    if expr.lower() == 'false':
        return 'False'

    # shape in <name> → shape == "<name>"
    expr = _SHAPE_IN_RE.sub(lambda m: f'shape == "{m.group(1)}"', expr)

    # Logical operators
    for src, dst in _OP_REPLACEMENTS:
        expr = expr.replace(src, dst)

    # Logical NOT: !expr → not expr  (but not !=)
    expr = _NOT_RE.sub(' not ', expr)

    return expr


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

# Allowed names in eval context — prevents access to builtins
_SAFE_BUILTINS: dict[str, Any] = {}

# The hand variables that are valid in conditions
_HAND_VARS = frozenset({
    'hcp', 'controls', 'losers',
    'spades', 'hearts', 'diamonds', 'clubs',
    'longest_suit', 'second_suit',
    'shape',
    'True', 'False',
})


def evaluate_condition(condition: str, hand: dict[str, Any]) -> bool:
    """Evaluate a BBDSL condition string against a hand dict.

    Args:
        condition: Condition expression (e.g. "hcp >= 16 && hearts >= 5").
        hand: Dict of hand properties (hcp, hearts, spades, etc.).
              Missing variables default to 0 (or None for shape).

    Returns:
        True if the condition is satisfied.

    Raises:
        ValueError: If the condition string is syntactically invalid.
    """
    python_expr = _transform_condition(condition)

    # Build evaluation context with safe defaults
    ctx: dict[str, Any] = {
        'hcp': 0,
        'controls': 0,
        'losers': 13,
        'spades': 0,
        'hearts': 0,
        'diamonds': 0,
        'clubs': 0,
        'longest_suit': 0,
        'second_suit': 0,
        'shape': None,
    }
    ctx.update({k: v for k, v in hand.items() if k in _HAND_VARS or k == 'shape'})

    # Compute derived values
    if 'longest_suit' not in hand:
        suit_lengths = [
            ctx.get('spades', 0),
            ctx.get('hearts', 0),
            ctx.get('diamonds', 0),
            ctx.get('clubs', 0),
        ]
        ctx['longest_suit'] = max(suit_lengths) if suit_lengths else 0
        sorted_lengths = sorted(suit_lengths, reverse=True)
        ctx['second_suit'] = sorted_lengths[1] if len(sorted_lengths) > 1 else 0

    try:
        result = eval(python_expr, {'__builtins__': _SAFE_BUILTINS}, ctx)  # noqa: S307
    except Exception as exc:
        raise ValueError(
            f"Invalid condition expression '{condition}': {exc}"
        ) from exc

    return bool(result)


# ---------------------------------------------------------------------------
# Selection rule model (plain dict parsing)
# ---------------------------------------------------------------------------

def parse_selection_rules(selection_rules: dict) -> list[dict]:
    """Extract the ordered list of rules from a selection_rules dict.

    Handles both formats:
        # Named group:
        selection_rules:
          opening_selection:
            rules: [{id: ..., condition: ..., select: ...}, ...]

        # Direct list (shorthand):
        selection_rules:
          rules: [{...}, ...]
    """
    if not selection_rules:
        return []

    # Look for a 'rules' key at the top level
    if 'rules' in selection_rules:
        return list(selection_rules['rules'])

    # Look for named groups (each has a 'rules' sub-list)
    all_rules: list[dict] = []
    for _group_name, group_value in selection_rules.items():
        if isinstance(group_value, dict) and 'rules' in group_value:
            all_rules.extend(group_value['rules'])
        elif isinstance(group_value, list):
            all_rules.extend(group_value)

    return all_rules


# ---------------------------------------------------------------------------
# Selection engine
# ---------------------------------------------------------------------------

def select_bid(
    hand: dict[str, Any],
    rules: list[dict],
) -> dict | None:
    """Apply selection rules to a hand, returning the first matching rule.

    Rules are evaluated in order; the first matching rule's dict is returned.

    Args:
        hand: Hand properties dict.
        rules: List of rule dicts, each with 'condition' and 'select' fields.

    Returns:
        The first matching rule dict, or None if no rule matches.
    """
    for rule in rules:
        condition = rule.get('condition', 'true')
        try:
            if evaluate_condition(condition, hand):
                return rule
        except ValueError:
            # Skip invalid conditions (they'll be caught by validation)
            continue
    return None


def select_opening(
    hand: dict[str, Any],
    selection_rules: dict,
) -> str | None:
    """Select an opening bid for a hand using selection_rules.

    Returns the 'select' value of the first matching rule, or None.
    """
    rules = parse_selection_rules(selection_rules)
    matched = select_bid(hand, rules)
    return matched.get('select') if matched else None


# ---------------------------------------------------------------------------
# Helper: build a hand dict from BBDSL HandConstraint midpoints
# ---------------------------------------------------------------------------

def hand_from_constraint(hc: Any) -> dict[str, Any]:
    """Build a representative hand dict from a HandConstraint (uses midpoints).

    Useful for testing whether a constraint would match a selection rule.
    """

    def mid(r: Any) -> int:
        if r is None:
            return 0
        mn = r.min if r.min is not None else 0
        mx = r.max if r.max is not None else mn + 4
        return (mn + mx) // 2

    hand: dict[str, Any] = {
        'hcp': mid(getattr(hc, 'hcp', None)),
        'controls': mid(getattr(hc, 'controls', None)),
        'losers': mid(getattr(hc, 'losing_tricks', None)),
        'spades': mid(getattr(hc, 'spades', None)),
        'hearts': mid(getattr(hc, 'hearts', None)),
        'diamonds': mid(getattr(hc, 'diamonds', None)),
        'clubs': mid(getattr(hc, 'clubs', None)),
    }
    shape = getattr(hc, 'shape', None)
    if isinstance(shape, dict) and 'ref' in shape:
        hand['shape'] = shape['ref']
    elif isinstance(shape, str):
        hand['shape'] = shape
    else:
        hand['shape'] = None

    suit_lengths = [hand['spades'], hand['hearts'], hand['diamonds'], hand['clubs']]
    hand['longest_suit'] = max(suit_lengths)
    sorted_lengths = sorted(suit_lengths, reverse=True)
    hand['second_suit'] = sorted_lengths[1] if len(sorted_lengths) > 1 else 0
    return hand
