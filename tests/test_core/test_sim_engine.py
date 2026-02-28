"""Tests for bbdsl.core.sim_engine."""

import json

import pytest

from bbdsl.core.hand_generator import BridgeHand
from bbdsl.core.loader import load_document
from bbdsl.core.sim_engine import (
    AuctionStep,
    Deal,
    SimulationResult,
    _final_contract,
    _get_candidates,
    _matches_constraint,
    _navigate_tree,
    _select_bid,
    generate_deal,
    simulate,
    simulate_deal,
)
from bbdsl.models.bid import HandConstraint
from bbdsl.models.common import Range

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


# ---------------------------------------------------------------------------
# TestGenerateDeal
# ---------------------------------------------------------------------------

class TestGenerateDeal:
    def test_returns_deal(self):
        d = generate_deal()
        assert isinstance(d, Deal)

    def test_four_hands_each_13_cards(self):
        d = generate_deal(seed=1)
        for hand in (d.north, d.south, d.east, d.west):
            total = len(hand.spades) + len(hand.hearts) + len(hand.diamonds) + len(hand.clubs)
            assert total == 13

    def test_52_total_cards_no_duplicates(self):
        d = generate_deal(seed=2)
        all_cards: list[tuple[str, str]] = []
        for hand in (d.north, d.south, d.east, d.west):
            all_cards += [(r, "S") for r in hand.spades]
            all_cards += [(r, "H") for r in hand.hearts]
            all_cards += [(r, "D") for r in hand.diamonds]
            all_cards += [(r, "C") for r in hand.clubs]
        assert len(all_cards) == 52
        assert len(set(all_cards)) == 52, "Duplicate cards across hands"

    def test_total_hcp_equals_40(self):
        d = generate_deal(seed=3)
        total_hcp = d.north.hcp + d.south.hcp + d.east.hcp + d.west.hcp
        assert total_hcp == 40

    def test_seed_reproducible(self):
        d1 = generate_deal(seed=42)
        d2 = generate_deal(seed=42)
        assert d1.north.spades == d2.north.spades
        assert d1.south.hcp == d2.south.hcp
        assert d1.east.clubs == d2.east.clubs

    def test_different_seeds_give_different_deals(self):
        d1 = generate_deal(seed=10)
        d2 = generate_deal(seed=99)
        # Very unlikely to be identical
        assert d1.north.spades != d2.north.spades or d1.south.hearts != d2.south.hearts

    def test_seed_stored(self):
        d = generate_deal(seed=7)
        assert d.seed == 7

    def test_none_seed_stored(self):
        d = generate_deal(seed=None)
        assert d.seed is None

    def test_hands_are_bridge_hands(self):
        d = generate_deal(seed=5)
        for hand in (d.north, d.south, d.east, d.west):
            assert isinstance(hand, BridgeHand)


# ---------------------------------------------------------------------------
# TestMatchesConstraint
# ---------------------------------------------------------------------------

class TestMatchesConstraint:
    def _hand(self, hcp=10, spades=3, hearts=4, diamonds=3, clubs=3):
        return BridgeHand(
            spades=["A", "K", "Q"][: spades] if spades <= 3 else ["A"] * spades,
            hearts=["K", "Q", "J", "T"][: hearts],
            diamonds=["Q", "J", "T"][: diamonds],
            clubs=["J", "T", "9"][: clubs],
            hcp=hcp,
        )

    def test_none_constraint_always_true(self):
        hand = self._hand()
        assert _matches_constraint(hand, None) is True

    def test_hcp_min_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=16)
        hc = HandConstraint(hcp=Range(min=16))
        assert _matches_constraint(hand, hc) is True

    def test_hcp_min_no_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=15)
        hc = HandConstraint(hcp=Range(min=16))
        assert _matches_constraint(hand, hc) is False

    def test_hcp_max_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=7)
        hc = HandConstraint(hcp=Range(max=7))
        assert _matches_constraint(hand, hc) is True

    def test_hcp_max_no_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=8)
        hc = HandConstraint(hcp=Range(max=7))
        assert _matches_constraint(hand, hc) is False

    def test_hcp_range_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=16)
        hc = HandConstraint(hcp=Range(min=15, max=17))
        assert _matches_constraint(hand, hc) is True

    def test_suit_min_match(self):
        hand = BridgeHand(
            spades=[], hearts=["A", "K", "Q", "J", "T"], diamonds=[], clubs=[], hcp=0
        )
        hc = HandConstraint(hearts=Range(min=5))
        assert _matches_constraint(hand, hc) is True

    def test_suit_min_no_match(self):
        hand = BridgeHand(
            spades=[], hearts=["A", "K", "Q", "J"], diamonds=[], clubs=[], hcp=0
        )
        hc = HandConstraint(hearts=Range(min=5))
        assert _matches_constraint(hand, hc) is False

    def test_suit_max_match(self):
        hand = BridgeHand(spades=["A", "K", "Q"], hearts=[], diamonds=[], clubs=[], hcp=0)
        hc = HandConstraint(spades=Range(max=3))
        assert _matches_constraint(hand, hc) is True

    def test_suit_max_no_match(self):
        hand = BridgeHand(spades=["A", "K", "Q", "J"], hearts=[], diamonds=[], clubs=[], hcp=0)
        hc = HandConstraint(spades=Range(max=3))
        assert _matches_constraint(hand, hc) is False

    def test_shape_balanced_match(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J"],
            hearts=["A", "K", "Q"],
            diamonds=["A", "K", "Q"],
            clubs=["A", "K", "Q"],
            hcp=20,
        )
        hc = HandConstraint(shape={"ref": "balanced"})
        assert _matches_constraint(hand, hc) is True

    def test_shape_balanced_no_match(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J", "T"],
            hearts=["A", "K", "Q", "J"],
            diamonds=["A", "K"],
            clubs=["A", "K"],
            hcp=20,
        )
        hc = HandConstraint(shape={"ref": "balanced"})
        assert _matches_constraint(hand, hc) is False

    def test_controls_match(self):
        hand = BridgeHand(
            spades=["A"],
            hearts=["K"],
            diamonds=["A"],
            clubs=["K"],
            hcp=14,
        )
        # 2 aces × 2 + 2 kings × 1 = 6
        hc = HandConstraint(controls=Range(min=4))
        assert _matches_constraint(hand, hc) is True

    def test_controls_no_match(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=0)
        hc = HandConstraint(controls=Range(min=4))
        assert _matches_constraint(hand, hc) is False

    def test_multiple_constraints_all_pass(self):
        hand = BridgeHand(
            spades=["A", "K", "Q", "J", "T"],
            hearts=["A", "K"],
            diamonds=["A", "K"],
            clubs=["A", "K", "Q"],
            hcp=20,
        )
        hc = HandConstraint(hcp=Range(min=15), spades=Range(min=5))
        assert _matches_constraint(hand, hc) is True

    def test_multiple_constraints_one_fails(self):
        hand = BridgeHand(
            spades=["A", "K", "Q"],
            hearts=["A", "K"],
            diamonds=["A", "K"],
            clubs=["A", "K", "Q"],
            hcp=20,
        )
        hc = HandConstraint(hcp=Range(min=15), spades=Range(min=5))
        assert _matches_constraint(hand, hc) is False


# ---------------------------------------------------------------------------
# TestNavigateTree
# ---------------------------------------------------------------------------

class TestNavigateTree:
    def test_empty_path_returns_none(self, precision_doc):
        result = _navigate_tree(precision_doc, [])
        assert result is None

    def test_finds_opening_bid(self, precision_doc):
        # Precision has 1C opening
        first_opening = precision_doc.openings[0]
        bid = first_opening.bid
        result = _navigate_tree(precision_doc, [bid])
        assert result is not None
        assert result.bid == bid

    def test_not_found_returns_none(self, precision_doc):
        result = _navigate_tree(precision_doc, ["7NT"])
        assert result is None

    def test_finds_response(self, precision_doc):
        # Navigate to first opening, then find a response if it has any
        opening = precision_doc.openings[0]
        if not opening.responses:
            pytest.skip("First opening has no responses")
        first_response = opening.responses[0]
        result = _navigate_tree(precision_doc, [opening.bid, first_response.bid])
        assert result is not None
        assert result.bid == first_response.bid

    def test_invalid_response_returns_none(self, precision_doc):
        opening = precision_doc.openings[0]
        result = _navigate_tree(precision_doc, [opening.bid, "7NT"])
        assert result is None

    def test_path_length_one_returns_opening_node(self, precision_doc):
        node = _navigate_tree(precision_doc, [precision_doc.openings[0].bid])
        assert node is precision_doc.openings[0]


# ---------------------------------------------------------------------------
# TestGetCandidates
# ---------------------------------------------------------------------------

class TestGetCandidates:
    def test_none_returns_openings(self, precision_doc):
        candidates = _get_candidates(None, precision_doc)
        assert candidates == (precision_doc.openings or [])

    def test_node_returns_responses_and_continuations(self, precision_doc):
        opening = precision_doc.openings[0]
        candidates = _get_candidates(opening, precision_doc)
        expected = (opening.responses or []) + (opening.continuations or [])
        assert candidates == expected

    def test_node_without_responses_returns_empty(self, precision_doc):
        # Create a minimal node with no children
        from bbdsl.models.bid import BidNode
        node = BidNode(bid="1C")
        candidates = _get_candidates(node, precision_doc)
        assert candidates == []


# ---------------------------------------------------------------------------
# TestSelectBid
# ---------------------------------------------------------------------------

class TestSelectBid:
    def _make_node(self, bid: str, hcp_min: int | None = None, hcp_max: int | None = None):
        from bbdsl.models.bid import BidNode, BidMeaning, HandConstraint
        from bbdsl.models.common import Range
        hc = HandConstraint(hcp=Range(min=hcp_min, max=hcp_max)) if hcp_min or hcp_max else None
        meaning = BidMeaning(hand=hc) if hc else None
        return BidNode(bid=bid, meaning=meaning)

    def test_matches_first_valid_candidate(self):
        candidates = [
            self._make_node("1C", hcp_min=16),
            self._make_node("1NT", hcp_min=15, hcp_max=17),
        ]
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=16)
        bid, reasoning = _select_bid(hand, candidates)
        assert bid == "1C"

    def test_skips_non_matching_returns_next(self):
        candidates = [
            self._make_node("1C", hcp_min=16),
            self._make_node("1D", hcp_min=11, hcp_max=15),
        ]
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=12)
        bid, _ = _select_bid(hand, candidates)
        assert bid == "1D"

    def test_no_match_returns_pass(self):
        candidates = [
            self._make_node("1C", hcp_min=16),
        ]
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=10)
        bid, reasoning = _select_bid(hand, candidates)
        assert bid == "Pass"
        assert "No matching" in reasoning

    def test_no_constraint_matches_any(self):
        from bbdsl.models.bid import BidNode
        node = BidNode(bid="Pass")  # no meaning, no hand constraint
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=0)
        bid, reasoning = _select_bid(hand, [node])
        assert bid == "Pass"

    def test_empty_candidates_returns_pass(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=10)
        bid, _ = _select_bid(hand, [])
        assert bid == "Pass"

    def test_reasoning_contains_bid(self):
        candidates = [self._make_node("1C", hcp_min=16)]
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=18)
        bid, reasoning = _select_bid(hand, candidates)
        assert bid == "1C"
        assert "1C" in reasoning


# ---------------------------------------------------------------------------
# TestFinalContract
# ---------------------------------------------------------------------------

class TestFinalContract:
    def test_all_pass_returns_none_and_passed_out(self):
        steps = [
            AuctionStep("N", "Pass", "opener", ""),
            AuctionStep("E", "Pass", "opponent", ""),
            AuctionStep("S", "Pass", "responder", ""),
            AuctionStep("W", "Pass", "opponent", ""),
        ]
        contract, passed_out = _final_contract(steps)
        assert contract is None
        assert passed_out is True

    def test_last_non_pass_is_contract(self):
        steps = [
            AuctionStep("N", "1C", "opener", ""),
            AuctionStep("E", "Pass", "opponent", ""),
            AuctionStep("S", "1D", "responder", ""),
            AuctionStep("W", "Pass", "opponent", ""),
            AuctionStep("N", "3NT", "opener", ""),
            AuctionStep("E", "Pass", "opponent", ""),
            AuctionStep("S", "Pass", "responder", ""),
            AuctionStep("W", "Pass", "opponent", ""),
        ]
        contract, passed_out = _final_contract(steps)
        assert contract == "3NT by North"
        assert passed_out is False

    def test_empty_auction_returns_none(self):
        contract, passed_out = _final_contract([])
        assert contract is None
        assert passed_out is True

    def test_south_last_bid(self):
        steps = [
            AuctionStep("S", "4H", "opener", ""),
            AuctionStep("W", "Pass", "opponent", ""),
            AuctionStep("N", "Pass", "responder", ""),
            AuctionStep("E", "Pass", "opponent", ""),
        ]
        contract, _ = _final_contract(steps)
        assert "South" in contract
        assert "4H" in contract


# ---------------------------------------------------------------------------
# TestSimulateDeal
# ---------------------------------------------------------------------------

class TestSimulateDeal:
    def test_returns_simulation_result(self, precision_doc):
        result = simulate_deal(precision_doc, seed=42)
        assert isinstance(result, SimulationResult)

    def test_auction_is_non_empty(self, precision_doc):
        result = simulate_deal(precision_doc, seed=1)
        assert len(result.auction) > 0

    def test_ew_all_pass_without_ew_doc(self, precision_doc):
        result = simulate_deal(precision_doc, seed=5)
        ew_steps = [s for s in result.auction if s.seat in ("E", "W")]
        assert all(s.bid == "Pass" for s in ew_steps)

    def test_ew_are_opponents(self, precision_doc):
        result = simulate_deal(precision_doc, seed=5)
        ew_steps = [s for s in result.auction if s.seat in ("E", "W")]
        assert all(s.by == "opponent" for s in ew_steps)

    def test_deal_is_deal_instance(self, precision_doc):
        result = simulate_deal(precision_doc, seed=3)
        assert isinstance(result.deal, Deal)

    def test_final_contract_is_str_or_none(self, precision_doc):
        result = simulate_deal(precision_doc, seed=7)
        assert result.final_contract is None or isinstance(result.final_contract, str)

    def test_passed_out_is_bool(self, precision_doc):
        result = simulate_deal(precision_doc, seed=8)
        assert isinstance(result.passed_out, bool)

    def test_seed_reproducible(self, precision_doc):
        r1 = simulate_deal(precision_doc, seed=42)
        r2 = simulate_deal(precision_doc, seed=42)
        assert r1.final_contract == r2.final_contract
        assert len(r1.auction) == len(r2.auction)
        assert r1.deal.north.hcp == r2.deal.north.hcp

    def test_external_deal_is_used(self, precision_doc):
        deal = generate_deal(seed=99)
        result = simulate_deal(precision_doc, deal=deal)
        assert result.deal is deal

    def test_deal_number_stored(self, precision_doc):
        result = simulate_deal(precision_doc, deal_number=5)
        assert result.deal_number == 5

    def test_auction_terminates(self, precision_doc):
        # Auction should always end (not run forever)
        result = simulate_deal(precision_doc, seed=42)
        assert len(result.auction) <= 40

    def test_auction_ends_with_passes(self, precision_doc):
        result = simulate_deal(precision_doc, seed=10)
        # Last 3+ bids should be Pass (if not passed out from start)
        if not result.passed_out and len(result.auction) >= 3:
            last_three = [s.bid for s in result.auction[-3:]]
            assert all(b == "Pass" for b in last_three)

    def test_sayc_no_crash(self, sayc_doc):
        result = simulate_deal(sayc_doc, seed=42)
        assert isinstance(result, SimulationResult)

    def test_with_ew_doc(self, precision_doc, sayc_doc):
        result = simulate_deal(precision_doc, ew_doc=sayc_doc, seed=42)
        assert isinstance(result, SimulationResult)
        # E/W should still be "opponent"
        ew_steps = [s for s in result.auction if s.seat in ("E", "W")]
        assert all(s.by == "opponent" for s in ew_steps)

    def test_ns_by_values(self, precision_doc):
        result = simulate_deal(precision_doc, seed=1)
        ns_steps = [s for s in result.auction if s.seat in ("N", "S")]
        for s in ns_steps:
            assert s.by in ("opener", "responder")

    def test_dealer_east_order(self, precision_doc):
        result = simulate_deal(precision_doc, dealer="E", seed=42)
        assert result.auction[0].seat == "E"

    def test_dealer_south_order(self, precision_doc):
        result = simulate_deal(precision_doc, dealer="S", seed=42)
        assert result.auction[0].seat == "S"


# ---------------------------------------------------------------------------
# TestSimulate
# ---------------------------------------------------------------------------

class TestSimulate:
    def test_returns_list(self, precision_doc):
        results = simulate(precision_doc, n_deals=3, seed=42)
        assert isinstance(results, list)

    def test_length_equals_n_deals(self, precision_doc):
        results = simulate(precision_doc, n_deals=5, seed=1)
        assert len(results) == 5

    def test_deal_numbers_sequential(self, precision_doc):
        results = simulate(precision_doc, n_deals=4, seed=2)
        for i, r in enumerate(results, start=1):
            assert r.deal_number == i

    def test_seed_reproducible(self, precision_doc):
        r1 = simulate(precision_doc, n_deals=3, seed=42)
        r2 = simulate(precision_doc, n_deals=3, seed=42)
        for a, b in zip(r1, r2):
            assert a.final_contract == b.final_contract
            assert a.deal.north.hcp == b.deal.north.hcp

    def test_all_results_are_simulation_result(self, precision_doc):
        results = simulate(precision_doc, n_deals=3, seed=5)
        for r in results:
            assert isinstance(r, SimulationResult)

    def test_zero_deals(self, precision_doc):
        results = simulate(precision_doc, n_deals=0)
        assert results == []

    def test_sayc_no_crash(self, sayc_doc):
        results = simulate(sayc_doc, n_deals=3, seed=42)
        assert len(results) == 3


# ---------------------------------------------------------------------------
# TestToDict
# ---------------------------------------------------------------------------

class TestToDict:
    def test_deal_to_dict_has_required_keys(self):
        d = generate_deal(seed=1)
        dd = d.to_dict()
        assert "north" in dd
        assert "south" in dd
        assert "east" in dd
        assert "west" in dd
        assert "seed" in dd

    def test_deal_to_dict_seed_matches(self):
        d = generate_deal(seed=99)
        assert d.to_dict()["seed"] == 99

    def test_auction_step_to_dict(self):
        step = AuctionStep(seat="N", bid="1C", by="opener", reasoning="16+ HCP → 1C")
        d = step.to_dict()
        assert d["seat"] == "N"
        assert d["bid"] == "1C"
        assert d["by"] == "opener"
        assert "reasoning" in d

    def test_simulation_result_to_dict_json_serializable(self, precision_doc):
        result = simulate_deal(precision_doc, seed=42)
        d = result.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        assert len(serialized) > 0

    def test_simulation_result_to_dict_keys(self, precision_doc):
        result = simulate_deal(precision_doc, seed=42)
        d = result.to_dict()
        assert "deal_number" in d
        assert "deal" in d
        assert "auction" in d
        assert "final_contract" in d
        assert "passed_out" in d

    def test_auction_list_in_dict(self, precision_doc):
        result = simulate_deal(precision_doc, seed=42)
        d = result.to_dict()
        assert isinstance(d["auction"], list)
        for step_dict in d["auction"]:
            assert "seat" in step_dict
            assert "bid" in step_dict
            assert "by" in step_dict
            assert "reasoning" in step_dict
