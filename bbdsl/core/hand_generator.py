"""Random bridge hand generator.

Generates 13-card hands that satisfy BBDSL HandConstraint specifications.

Algorithm (two-phase):
  Phase 1 — Suit lengths:
    Determine how many cards per suit using the constraint's min/max bounds.
    For shape constraints (balanced / semi_balanced), pick a valid pattern first.
  Phase 2 — Card selection:
    Shuffle each suit's 13 cards and pick the required count.
    Rejection-sample until the overall HCP range is satisfied.

Example::

    from bbdsl.core.hand_generator import generate_hand, BridgeHand
    from bbdsl.models.bid import HandConstraint
    from bbdsl.models.common import Range

    hc = HandConstraint(hcp=Range(min=15, max=17), shape={"ref": "balanced"})
    hand = generate_hand(hc, seed=42)
    print(hand)               # ♠ A K 7 4  ♥ K J 3  ♦ Q 7 2  ♣ 9 6 3
    print(hand.hcp)           # 16
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Card ranks from highest to lowest
RANKS: list[str] = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"]

_RANK_IDX: dict[str, int] = {r: i for i, r in enumerate(RANKS)}

#: HCP values for honour cards
HCP_VALUES: dict[str, int] = {"A": 4, "K": 3, "Q": 2, "J": 1}

SUITS: list[str] = ["spades", "hearts", "diamonds", "clubs"]

#: Valid sorted (descending) patterns for each shape category
_BALANCED_PATTERNS: set[tuple[int, ...]] = {(4, 3, 3, 3), (4, 4, 3, 2), (5, 3, 3, 2)}
_SEMI_BAL_PATTERNS: set[tuple[int, ...]] = {(5, 4, 2, 2), (6, 3, 2, 2)}

_BUILTIN_GENERIC_SHAPE_PATTERNS: dict[str, set[tuple[int, ...]]] = {
    "balanced": _BALANCED_PATTERNS,
    "semi_balanced": _SEMI_BAL_PATTERNS,
    "semi-balanced": _SEMI_BAL_PATTERNS,
}

_BUILTIN_EXACT_SHAPE_PATTERNS: dict[str, set[tuple[int, ...]]] = {
    "precision_2d": {(4, 4, 1, 4), (4, 4, 0, 5)},
}

# Per-suit card pools (rank, suit_name), sorted high-to-low
_SUIT_POOL: dict[str, list[str]] = {s: list(RANKS) for s in SUITS}


# ---------------------------------------------------------------------------
# BridgeHand
# ---------------------------------------------------------------------------

@dataclass
class BridgeHand:
    """A 13-card bridge hand organised by suit (cards in high-to-low order)."""

    spades:   list[str] = field(default_factory=list)
    hearts:   list[str] = field(default_factory=list)
    diamonds: list[str] = field(default_factory=list)
    clubs:    list[str] = field(default_factory=list)
    hcp:      int = 0

    # ---------- Derived properties ----------

    @property
    def suit_lengths(self) -> dict[str, int]:
        return {
            "spades":   len(self.spades),
            "hearts":   len(self.hearts),
            "diamonds": len(self.diamonds),
            "clubs":    len(self.clubs),
        }

    @property
    def shape_pattern(self) -> tuple[int, ...]:
        """Lengths sorted high-to-low, e.g. (5, 4, 3, 1)."""
        return tuple(sorted(self.suit_lengths.values(), reverse=True))

    @property
    def is_balanced(self) -> bool:
        return self.shape_pattern in _BALANCED_PATTERNS

    @property
    def is_semi_balanced(self) -> bool:
        return self.shape_pattern in _SEMI_BAL_PATTERNS

    # ---------- Display ----------

    def _suit_str(self, cards: list[str]) -> str:
        return " ".join(cards) if cards else "—"

    def __str__(self) -> str:
        return (
            f"♠ {self._suit_str(self.spades)}\n"
            f"♥ {self._suit_str(self.hearts)}\n"
            f"♦ {self._suit_str(self.diamonds)}\n"
            f"♣ {self._suit_str(self.clubs)}\n"
            f"HCP: {self.hcp}"
        )

    def to_dict(self) -> dict:
        return {
            "spades":   self.spades,
            "hearts":   self.hearts,
            "diamonds": self.diamonds,
            "clubs":    self.clubs,
            "hcp":      self.hcp,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _calc_hcp(by_suit: dict[str, list[str]]) -> int:
    return sum(HCP_VALUES.get(card, 0) for cards in by_suit.values() for card in cards)


def _check_hcp(hcp: int, constraint: Any) -> bool:
    if constraint is None:
        return True
    hc = getattr(constraint, "hcp", None)
    if hc is None:
        return True
    lo = hc.min if hc.min is not None else 0
    hi = hc.max if hc.max is not None else 37
    return lo <= hcp <= hi


def _count_hcp(by_suit: dict[str, list[str]]) -> int:
    return _calc_hcp(by_suit)


def _count_distribution_points(by_suit: dict[str, list[str]]) -> int:
    """Very small heuristic for total_points = hcp + distribution."""
    return sum(max(0, len(cards) - 4) for cards in by_suit.values())


def _count_losing_tricks(by_suit: dict[str, list[str]]) -> int:
    """Approximate losing trick count for a single hand."""
    losers = 0
    for cards in by_suit.values():
        n = len(cards)
        if n == 0:
            losers += 3
            continue
        if n == 1:
            losers += 2 - (1 if "A" in cards else 0)
            continue
        if n == 2:
            losers += 1 - (1 if "A" in cards else 0) - (1 if "K" in cards else 0)
            continue
        suit_losers = 3
        for honour in ("A", "K", "Q"):
            if honour in cards:
                suit_losers -= 1
        losers += max(0, suit_losers)
    return losers


def _specific_cards(constraint: Any) -> list[str]:
    cards = getattr(constraint, "specific_cards", None)
    if not cards:
        return []
    return [str(card).upper() for card in cards]


def _card_components(card: str) -> tuple[str, str]:
    match = re.fullmatch(r"([AKQJT98765432])([SHDC])", card.upper())
    if not match:
        raise ValueError(f"Invalid specific card code: {card!r}")
    rank, suit_code = match.groups()
    suit_map = {"S": "spades", "H": "hearts", "D": "diamonds", "C": "clubs"}
    return rank, suit_map[suit_code]


def _parse_shape_tuple(value: str, *, exact: bool) -> tuple[int, ...] | None:
    parts = re.split(r"[-=]", str(value).strip())
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return None
    numbers = tuple(int(part) for part in parts)
    return numbers if exact else tuple(sorted(numbers, reverse=True))


def _shape_patterns_from_catalog(
    shape_patterns: dict[str, Any] | None,
) -> dict[str, dict[str, set[tuple[int, ...]]]]:
    """Resolve shape pattern definitions into generic and exact tuple sets."""
    resolved: dict[str, dict[str, set[tuple[int, ...]]]] = {
        ref: {"generic": set(patterns), "exact": set()}
        for ref, patterns in _BUILTIN_GENERIC_SHAPE_PATTERNS.items()
    }
    for ref, patterns in _BUILTIN_EXACT_SHAPE_PATTERNS.items():
        bucket = resolved.setdefault(str(ref), {"generic": set(), "exact": set()})
        bucket["exact"].update(patterns)
    if not shape_patterns:
        return resolved

    for ref, definition in shape_patterns.items():
        bucket = resolved.setdefault(str(ref), {"generic": set(), "exact": set()})
        shapes = getattr(definition, "shapes", None)
        if shapes:
            for shape in shapes:
                pattern = _parse_shape_tuple(shape, exact=False)
                if pattern is not None:
                    bucket["generic"].add(pattern)
        shapes_exact = getattr(definition, "shapes_exact", None)
        if shapes_exact:
            for shape in shapes_exact:
                pattern = _parse_shape_tuple(shape, exact=True)
                if pattern is not None:
                    bucket["exact"].add(pattern)
    return resolved


def _constraint_shape_patterns(
    constraint: Any,
    shape_patterns: dict[str, Any] | None = None,
) -> dict[str, set[tuple[int, ...]]] | None:
    shape = getattr(constraint, "shape", None)
    if shape is None:
        return None

    ref: str | None = None
    if isinstance(shape, dict):
        ref = shape.get("ref")
    elif isinstance(shape, str):
        ref = shape

    if not ref or ref in ("any", ""):
        return None

    catalog = _shape_patterns_from_catalog(shape_patterns)
    return catalog.get(ref)


def _check_suit(cards: list[str], r: Any) -> bool:
    if r is None:
        return True
    n = len(cards)
    if r.min is not None and n < r.min:
        return False
    if r.max is not None and n > r.max:
        return False
    if r.exactly is not None and n != r.exactly:
        return False
    return True


def _check_shape(
    by_suit: dict[str, list[str]],
    constraint: Any,
    shape_patterns: dict[str, Any] | None = None,
) -> bool:
    if constraint is None:
        return True
    shape = getattr(constraint, "shape", None)
    if shape is None:
        return True
    ref: str | None = None
    if isinstance(shape, dict):
        ref = shape.get("ref")
    elif isinstance(shape, str):
        ref = shape
    if not ref or ref in ("any", ""):
        return True

    pattern = tuple(len(by_suit[suit]) for suit in SUITS)
    allowed = _constraint_shape_patterns(constraint, shape_patterns)
    if allowed is None:
        return pattern in _BUILTIN_EXACT_SHAPE_PATTERNS.get(ref, set()) or (
            tuple(sorted(pattern, reverse=True))
            in _BUILTIN_GENERIC_SHAPE_PATTERNS.get(ref, set())
        )
    if pattern in allowed.get("exact", set()):
        return True
    return tuple(sorted(pattern, reverse=True)) in allowed.get("generic", set())


def _gen_suit_lengths(
    constraint: Any,
    rng: random.Random,
    shape_patterns: dict[str, Any] | None = None,
) -> dict[str, int] | None:
    """Choose suit lengths summing to 13 that satisfy constraint.

    Returns a dict {suit: length} or None if infeasible.
    """
    # Retrieve bounds
    bounds: dict[str, tuple[int, int]] = {}
    for suit in SUITS:
        r = getattr(constraint, suit, None) if constraint else None
        lo = r.min if r and r.min is not None else 0
        hi = r.max if r and r.max is not None else 13
        # Also honour exactly
        if r and r.exactly is not None:
            lo = hi = r.exactly
        bounds[suit] = (lo, min(hi, 13))

    # Determine required shape pattern (if any)
    shape_ref: str | None = None
    shape = getattr(constraint, "shape", None) if constraint else None
    if shape and isinstance(shape, dict):
        shape_ref = shape.get("ref")
    elif isinstance(shape, str):
        shape_ref = shape

    allowed_patterns = _constraint_shape_patterns(constraint, shape_patterns)
    if shape_ref and allowed_patterns is None:
        allowed_patterns = {
            "generic": _BUILTIN_GENERIC_SHAPE_PATTERNS.get(shape_ref, set()),
            "exact": _BUILTIN_EXACT_SHAPE_PATTERNS.get(shape_ref, set()),
        }

    exact_candidates = list(allowed_patterns.get("exact", set())) if allowed_patterns else []
    generic_candidates = (
        list(allowed_patterns.get("generic", set())) if allowed_patterns else []
    )

    for _attempt in range(400):
        if exact_candidates:
            pattern = rng.choice(exact_candidates)
            proposed = dict(zip(SUITS, pattern))
            if all(
                bounds[s][0] <= proposed[s] <= bounds[s][1]
                for s in SUITS
            ):
                return proposed
            continue
        if generic_candidates:
            # Pick a random valid pattern and assign to suits randomly.
            pattern = rng.choice(generic_candidates)
            lengths_list = list(pattern)
            rng.shuffle(lengths_list)
            proposed = dict(zip(SUITS, lengths_list))
            # Verify suit-specific bounds
            if all(
                bounds[s][0] <= proposed[s] <= bounds[s][1]
                for s in SUITS
            ):
                return proposed
            continue

        # No shape constraint: random allocation with constraint propagation
        proposed: dict[str, int] = {}
        remaining = 13
        shuffled_suits = list(SUITS)
        rng.shuffle(shuffled_suits)
        ok = True
        for i, suit in enumerate(shuffled_suits):
            lo, hi = bounds[suit]
            others = shuffled_suits[i + 1:]
            other_min = sum(bounds[s][0] for s in others)
            other_max = sum(bounds[s][1] for s in others)
            my_lo = max(lo, remaining - other_max)
            my_hi = min(hi, remaining - other_min)
            if my_lo > my_hi:
                ok = False
                break
            proposed[suit] = rng.randint(my_lo, my_hi)
            remaining -= proposed[suit]
        if ok and remaining == 0:
            return proposed

    return None  # infeasible or very unlucky


def _deal_cards(
    lengths: dict[str, int],
    rng: random.Random,
    constraint: Any = None,
) -> dict[str, list[str]]:
    """Deal cards according to suit lengths (random within each suit)."""
    required_by_suit: dict[str, list[str]] = {s: [] for s in SUITS}
    for card in _specific_cards(constraint):
        rank, suit = _card_components(card)
        required_by_suit[suit].append(rank)

    by_suit: dict[str, list[str]] = {}
    for suit in SUITS:
        pool = list(_SUIT_POOL[suit])
        rng.shuffle(pool)
        required = required_by_suit[suit]
        if len(required) > lengths[suit]:
            raise ValueError(
                f"Constraint requires {len(required)} specific card(s) in {suit}, "
                f"but only {lengths[suit]} card(s) allowed"
            )
        remaining_pool = [card for card in pool if card not in required]
        chosen = required + remaining_pool[: max(0, lengths[suit] - len(required))]
        chosen = sorted(chosen, key=lambda r: _RANK_IDX[r])
        by_suit[suit] = chosen
    return by_suit


def _check_controls(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    if constraint is None:
        return True
    ctrl_r = getattr(constraint, "controls", None)
    if ctrl_r is None:
        return True
    aces = sum(1 for cards in by_suit.values() for c in cards if c == "A")
    kings = sum(1 for cards in by_suit.values() for c in cards if c == "K")
    controls = aces * 2 + kings
    lo = ctrl_r.min if ctrl_r.min is not None else 0
    hi = ctrl_r.max if ctrl_r.max is not None else 12
    return lo <= controls <= hi


def _check_specific_cards(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    cards = _specific_cards(constraint)
    if not cards:
        return True
    present: set[str] = set()
    for suit_code, suit_name in (
        ("S", "spades"),
        ("H", "hearts"),
        ("D", "diamonds"),
        ("C", "clubs"),
    ):
        for rank in by_suit[suit_name]:
            present.add(f"{rank}{suit_code}")
    return all(card in present for card in cards)


def _check_stopper_in(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    suit_name = getattr(constraint, "stopper_in", None)
    if not suit_name:
        return True
    suit_map = {
        "s": "spades",
        "spades": "spades",
        "h": "hearts",
        "hearts": "hearts",
        "d": "diamonds",
        "diamonds": "diamonds",
        "c": "clubs",
        "clubs": "clubs",
    }
    suit = suit_map.get(str(suit_name).strip().lower())
    if suit is None:
        raise ValueError(f"Unsupported stopper_in value: {suit_name!r}")
    cards = by_suit[suit]
    if "A" in cards:
        return True
    if "K" in cards and len(cards) >= 2:
        return True
    if "Q" in cards and len(cards) >= 3:
        return True
    return False


def _check_losing_tricks(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    lt = getattr(constraint, "losing_tricks", None)
    if lt is None:
        return True
    count = _count_losing_tricks(by_suit)
    lo = lt.min if lt.min is not None else 0
    hi = lt.max if lt.max is not None else 12
    return lo <= count <= hi


def _check_total_points(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    tp = getattr(constraint, "total_points", None)
    if tp is None:
        return True
    total = _count_hcp(by_suit) + _count_distribution_points(by_suit)
    lo = tp.min if tp.min is not None else 0
    hi = tp.max if tp.max is not None else 40
    return lo <= total <= hi


def _check_four_card_major(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    if getattr(constraint, "four_card_major", None) is None:
        return True
    if not constraint.four_card_major:
        return not (len(by_suit["hearts"]) >= 4 or len(by_suit["spades"]) >= 4)
    return len(by_suit["hearts"]) >= 4 or len(by_suit["spades"]) >= 4


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_hand(
    constraint: Any = None,
    seed: int | None = None,
    max_attempts: int = 5000,
    shape_patterns: dict[str, Any] | None = None,
) -> BridgeHand:
    """Generate a random 13-card bridge hand satisfying *constraint*.

    Args:
        constraint: A ``HandConstraint`` instance (or None for unconstrained).
        seed: Random seed for reproducibility.
        max_attempts: Maximum rejection-sampling attempts before raising.

    Returns:
        A :class:`BridgeHand` instance.

    Raises:
        ValueError: If no satisfying hand is found within *max_attempts*.
    """
    rng = random.Random(seed)

    for attempt in range(max_attempts):
        # Phase 1: suit lengths
        lengths = _gen_suit_lengths(constraint, rng, shape_patterns=shape_patterns)
        if lengths is None:
            continue

        # Phase 2: card selection (inner loop for HCP adjustment)
        for _ in range(20):
            try:
                by_suit = _deal_cards(lengths, rng, constraint=constraint)
            except ValueError:
                continue
            hcp = _calc_hcp(by_suit)

            if (
                _check_hcp(hcp, constraint)
                and _check_shape(by_suit, constraint, shape_patterns=shape_patterns)
                and _check_controls(by_suit, constraint)
                and _check_losing_tricks(by_suit, constraint)
                and _check_total_points(by_suit, constraint)
                and _check_specific_cards(by_suit, constraint)
                and _check_stopper_in(by_suit, constraint)
                and _check_four_card_major(by_suit, constraint)
                and all(
                    _check_suit(by_suit[suit], getattr(constraint, suit, None))
                    for suit in SUITS
                )
            ):
                return BridgeHand(
                    spades=by_suit["spades"],
                    hearts=by_suit["hearts"],
                    diamonds=by_suit["diamonds"],
                    clubs=by_suit["clubs"],
                    hcp=hcp,
                )

    raise ValueError(
        f"Could not generate a hand satisfying the constraint after {max_attempts} attempts. "
        "The constraint may be infeasible or extremely rare."
    )


def generate_unconstrained_hand(seed: int | None = None) -> BridgeHand:
    """Generate a fully random 13-card hand (no constraints)."""
    return generate_hand(constraint=None, seed=seed)
