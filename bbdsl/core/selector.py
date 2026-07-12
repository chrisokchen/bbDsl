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

import ast
import operator
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

    # A leading '!' leaves a leading space, which Python parses as an indent.
    return expr.strip()


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

# The hand variables that are valid in conditions
_HAND_VARS = frozenset({
    'hcp', 'controls', 'losers',
    'spades', 'hearts', 'diamonds', 'clubs',
    'longest_suit', 'second_suit',
    'shape',
    'True', 'False',
})

# ---------------------------------------------------------------------------
# Safe expression evaluation
#
# Conditions are evaluated with an AST whitelist rather than eval(). Emptying
# __builtins__ is not a sandbox — an attacker can still reach the interpreter
# through attribute chains like ().__class__.__mro__. That did not matter while
# conditions only came from local files, but the platform accepts uploaded
# documents, which makes this input untrusted.
# ---------------------------------------------------------------------------

_COMPARE_OPS: dict[type, Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _eval_node(node: ast.AST, ctx: dict[str, Any]) -> Any:
    """Evaluate a whitelisted AST node against *ctx*."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str)) or node.value is None:
            return node.value
        raise ValueError(f"unsupported constant: {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise ValueError(f"unknown variable '{node.id}'")
        return ctx[node.id]

    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, ctx) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("unsupported boolean operator")

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, ctx)
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, ctx)
        if isinstance(node.op, ast.UAdd):
            return +_eval_node(node.operand, ctx)
        raise ValueError("unsupported unary operator")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            fn = _COMPARE_OPS.get(type(op))
            if fn is None:
                raise ValueError(f"unsupported comparison: {type(op).__name__}")
            right = _eval_node(comparator, ctx)
            if not fn(left, right):
                return False
            left = right
        return True

    raise ValueError(f"unsupported expression element: {type(node).__name__}")


def _safe_eval(expr: str, ctx: dict[str, Any]) -> Any:
    """Parse and evaluate *expr* using only whitelisted AST nodes."""
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree, ctx)


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
        result = _safe_eval(python_expr, ctx)
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
