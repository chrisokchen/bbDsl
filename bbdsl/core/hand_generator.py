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


def _check_shape(by_suit: dict[str, list[str]], constraint: Any) -> bool:
    if constraint is None:
        return True
    shape = getattr(constraint, "shape", None)
    if shape is None:
        return True
    if isinstance(shape, dict):
        ref = shape.get("ref", "")
        pattern = tuple(sorted([len(v) for v in by_suit.values()], reverse=True))
        if ref == "balanced":
            return pattern in _BALANCED_PATTERNS
        if ref in ("semi_balanced", "semi-balanced"):
            return pattern in _SEMI_BAL_PATTERNS
    return True


def _gen_suit_lengths(constraint: Any, rng: random.Random) -> dict[str, int] | None:
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

    # Candidate patterns for shape-constrained hands
    if shape_ref == "balanced":
        candidates = list(_BALANCED_PATTERNS)
    elif shape_ref in ("semi_balanced", "semi-balanced"):
        candidates = list(_SEMI_BAL_PATTERNS)
    else:
        candidates = None

    for _attempt in range(400):
        if candidates:
            # Pick a random valid pattern and assign to suits randomly
            pattern = rng.choice(candidates)
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


def _deal_cards(lengths: dict[str, int], rng: random.Random) -> dict[str, list[str]]:
    """Deal cards according to suit lengths (random within each suit)."""
    by_suit: dict[str, list[str]] = {}
    for suit in SUITS:
        pool = list(_SUIT_POOL[suit])
        rng.shuffle(pool)
        chosen = sorted(pool[: lengths[suit]], key=lambda r: _RANK_IDX[r])
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_hand(
    constraint: Any = None,
    seed: int | None = None,
    max_attempts: int = 5000,
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
        lengths = _gen_suit_lengths(constraint, rng)
        if lengths is None:
            continue

        # Phase 2: card selection (inner loop for HCP adjustment)
        for _ in range(20):
            by_suit = _deal_cards(lengths, rng)
            hcp = _calc_hcp(by_suit)

            if (
                _check_hcp(hcp, constraint)
                and _check_shape(by_suit, constraint)
                and _check_controls(by_suit, constraint)
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
