"""Tests for bbdsl.core.hand_generator."""

import pytest

from bbdsl.core.hand_generator import (
    BridgeHand,
    RANKS,
    SUITS,
    HCP_VALUES,
    generate_hand,
    generate_unconstrained_hand,
    _calc_hcp,
    _check_hcp,
    _check_shape,
)
from bbdsl.models.bid import HandConstraint
from bbdsl.models.common import Range


# ---------------------------------------------------------------------------
# BridgeHand dataclass
# ---------------------------------------------------------------------------

class TestBridgeHand:
    def _hand(self, s=None, h=None, d=None, c=None, hcp=10):
        return BridgeHand(
            spades=s or ["A", "K"],
            hearts=h or ["Q", "J", "T"],
            diamonds=d or ["9", "8", "7", "6"],
            clubs=c or ["5", "4", "3", "2"],
            hcp=hcp,
        )

    def test_total_cards(self):
        hand = generate_unconstrained_hand(seed=1)
        total = sum(len(cards) for cards in [
            hand.spades, hand.hearts, hand.diamonds, hand.clubs
        ])
        assert total == 13

    def test_suit_lengths_property(self):
        hand = self._hand(s=["A", "K", "Q"], h=["J", "T"], d=["9", "8", "7", "6", "5"], c=["4", "3"])
        assert hand.suit_lengths["spades"] == 3
        assert hand.suit_lengths["hearts"] == 2
        assert hand.suit_lengths["diamonds"] == 5
        assert hand.suit_lengths["clubs"] == 2

    def test_shape_pattern_sorted(self):
        hand = self._hand(s=["A", "K", "Q"], h=["J", "T"], d=["9", "8", "7", "6", "5"], c=["4", "3"])
        assert hand.shape_pattern == (5, 3, 2, 2) or hand.shape_pattern[0] >= hand.shape_pattern[-1]
        assert sorted(hand.shape_pattern, reverse=True) == list(hand.shape_pattern)

    def test_is_balanced_4432(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J"],
            hearts=["T", "9", "8", "7"],
            diamonds=["6", "5", "4"],
            clubs=["3", "2"],
            hcp=10,
        )
        assert hand.is_balanced

    def test_is_balanced_4333(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J"],
            hearts=["T", "9", "8"],
            diamonds=["7", "6", "5"],
            clubs=["4", "3", "2"],
            hcp=10,
        )
        assert hand.is_balanced

    def test_not_balanced(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J", "T", "9"],
            hearts=["8", "7", "6"],
            diamonds=["5", "4"],
            clubs=["3", "2"],
            hcp=10,
        )
        assert not hand.is_balanced

    def test_str_representation(self):
        hand = generate_unconstrained_hand(seed=2)
        s = str(hand)
        assert "♠" in s
        assert "♥" in s
        assert "♦" in s
        assert "♣" in s
        assert "HCP" in s

    def test_to_dict(self):
        hand = generate_unconstrained_hand(seed=3)
        d = hand.to_dict()
        assert "spades" in d
        assert "hearts" in d
        assert "diamonds" in d
        assert "clubs" in d
        assert "hcp" in d
        assert isinstance(d["hcp"], int)

    def test_cards_are_valid_ranks(self):
        hand = generate_unconstrained_hand(seed=4)
        for suit in [hand.spades, hand.hearts, hand.diamonds, hand.clubs]:
            for card in suit:
                assert card in RANKS, f"Invalid card: {card}"

    def test_no_duplicate_cards(self):
        hand = generate_unconstrained_hand(seed=5)
        all_pairs = (
            [(c, "S") for c in hand.spades] +
            [(c, "H") for c in hand.hearts] +
            [(c, "D") for c in hand.diamonds] +
            [(c, "C") for c in hand.clubs]
        )
        assert len(all_pairs) == len(set(all_pairs))


# ---------------------------------------------------------------------------
# _calc_hcp
# ---------------------------------------------------------------------------

class TestCalcHcp:
    def test_all_aces(self):
        by_suit = {
            "spades": ["A"],
            "hearts": ["A"],
            "diamonds": ["A"],
            "clubs": ["A"],
        }
        assert _calc_hcp(by_suit) == 16

    def test_mixed_honors(self):
        by_suit = {
            "spades": ["A", "K"],   # 7
            "hearts": ["Q"],        # 2
            "diamonds": ["J"],      # 1
            "clubs": ["2", "3"],    # 0
        }
        assert _calc_hcp(by_suit) == 10

    def test_no_honors(self):
        by_suit = {
            "spades": ["2", "3"],
            "hearts": ["4", "5"],
            "diamonds": ["6"],
            "clubs": ["7", "8", "9", "T"],
        }
        assert _calc_hcp(by_suit) == 0


# ---------------------------------------------------------------------------
# generate_hand: unconstrained
# ---------------------------------------------------------------------------

class TestGenerateUnconstrained:
    def test_always_13_cards(self):
        for seed in range(10):
            hand = generate_hand(seed=seed)
            total = sum(len(getattr(hand, s)) for s in SUITS)
            assert total == 13

    def test_hcp_in_range(self):
        for seed in range(20):
            hand = generate_hand(seed=seed)
            assert 0 <= hand.hcp <= 37

    def test_seed_reproducible(self):
        h1 = generate_hand(seed=999)
        h2 = generate_hand(seed=999)
        assert h1.spades == h2.spades
        assert h1.hcp == h2.hcp

    def test_different_seeds_differ(self):
        h1 = generate_hand(seed=1)
        h2 = generate_hand(seed=2)
        # Extremely unlikely to be equal
        assert h1.spades != h2.spades or h1.hcp != h2.hcp


# ---------------------------------------------------------------------------
# generate_hand: HCP constraints
# ---------------------------------------------------------------------------

class TestGenerateWithHcp:
    def test_hcp_range_1520(self):
        for seed in range(10):
            hc = HandConstraint(hcp=Range(min=15, max=20))
            hand = generate_hand(hc, seed=seed)
            assert 15 <= hand.hcp <= 20

    def test_hcp_min_16(self):
        for seed in range(5):
            hc = HandConstraint(hcp=Range(min=16))
            hand = generate_hand(hc, seed=seed * 100)
            assert hand.hcp >= 16

    def test_hcp_max_7(self):
        for seed in range(5):
            hc = HandConstraint(hcp=Range(max=7))
            hand = generate_hand(hc, seed=seed * 200)
            assert hand.hcp <= 7

    def test_hcp_exact_range_1517(self):
        for seed in range(5):
            hc = HandConstraint(hcp=Range(min=15, max=17))
            hand = generate_hand(hc, seed=seed * 50)
            assert 15 <= hand.hcp <= 17


# ---------------------------------------------------------------------------
# generate_hand: suit length constraints
# ---------------------------------------------------------------------------

class TestGenerateWithSuits:
    def test_hearts_min_5(self):
        for seed in range(5):
            hc = HandConstraint(hearts=Range(min=5))
            hand = generate_hand(hc, seed=seed * 30)
            assert len(hand.hearts) >= 5

    def test_spades_max_3(self):
        for seed in range(5):
            hc = HandConstraint(spades=Range(max=3))
            hand = generate_hand(hc, seed=seed * 40)
            assert len(hand.spades) <= 3

    def test_clubs_exactly_5_hearts_min5(self):
        hc = HandConstraint(
            hearts=Range(min=5),
            hcp=Range(min=11, max=15),
        )
        for seed in range(5):
            hand = generate_hand(hc, seed=seed * 70)
            assert len(hand.hearts) >= 5
            assert 11 <= hand.hcp <= 15


# ---------------------------------------------------------------------------
# generate_hand: shape constraints
# ---------------------------------------------------------------------------

class TestGenerateWithShape:
    def test_balanced_shape(self):
        from bbdsl.core.hand_generator import _BALANCED_PATTERNS
        for seed in range(5):
            hc = HandConstraint(
                hcp=Range(min=15, max=17),
                shape={"ref": "balanced"},
            )
            hand = generate_hand(hc, seed=seed * 123)
            assert 15 <= hand.hcp <= 17
            assert hand.is_balanced, f"Pattern {hand.shape_pattern} is not balanced"

    def test_semi_balanced_shape(self):
        from bbdsl.core.hand_generator import _SEMI_BAL_PATTERNS
        for seed in range(5):
            hc = HandConstraint(shape={"ref": "semi_balanced"})
            hand = generate_hand(hc, seed=seed * 456)
            assert hand.is_semi_balanced, f"Pattern {hand.shape_pattern} not semi-balanced"


# ---------------------------------------------------------------------------
# generate_hand: combined constraints
# ---------------------------------------------------------------------------

class TestGenerateCombined:
    def test_precision_1c(self):
        """1C: 16+ HCP artificial strong club."""
        hc = HandConstraint(hcp=Range(min=16))
        for seed in range(5):
            hand = generate_hand(hc, seed=seed * 7)
            assert hand.hcp >= 16

    def test_precision_1nt(self):
        """1NT: 15-17 HCP balanced."""
        hc = HandConstraint(hcp=Range(min=15, max=17), shape={"ref": "balanced"})
        for seed in range(5):
            hand = generate_hand(hc, seed=seed * 11)
            assert 15 <= hand.hcp <= 17
            assert hand.is_balanced

    def test_precision_1h(self):
        """1H: 11-15 HCP, 5+ hearts."""
        hc = HandConstraint(hcp=Range(min=11, max=15), hearts=Range(min=5))
        for seed in range(5):
            hand = generate_hand(hc, seed=seed * 13)
            assert 11 <= hand.hcp <= 15
            assert len(hand.hearts) >= 5


# ---------------------------------------------------------------------------
# generate_unconstrained_hand
# ---------------------------------------------------------------------------

class TestGenerateUnconstrainedHand:
    def test_returns_bridge_hand(self):
        hand = generate_unconstrained_hand(seed=42)
        assert isinstance(hand, BridgeHand)

    def test_13_cards(self):
        hand = generate_unconstrained_hand()
        total = sum(len(getattr(hand, s)) for s in SUITS)
        assert total == 13
