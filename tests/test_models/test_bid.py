"""Tests for bbdsl.models.bid."""

import pytest
from pydantic import ValidationError

from bbdsl.models.bid import BidMeaning, BidNode, ForeachSuit, HandConstraint
from bbdsl.models.common import ForcingLevel, Range


class TestHandConstraint:
    def test_basic_hcp(self):
        hc = HandConstraint(hcp=Range(min=16))
        assert hc.hcp.min == 16
        assert hc.hcp.max is None

    def test_suit_lengths(self):
        hc = HandConstraint(hearts=Range(min=5), spades=Range(max=3))
        assert hc.hearts.min == 5
        assert hc.spades.max == 3

    def test_shape_ref(self):
        hc = HandConstraint(shape={"ref": "balanced"})
        assert hc.shape == {"ref": "balanced"}

    def test_specific_cards(self):
        hc = HandConstraint(specific_cards=["AS", "KH"])
        assert len(hc.specific_cards) == 2

    def test_empty_constraint(self):
        hc = HandConstraint()
        assert hc.hcp is None


class TestBidMeaning:
    def test_with_forcing(self):
        bm = BidMeaning(
            description="Test bid",
            forcing=ForcingLevel.GAME,
            artificial=True,
            alertable=True,
        )
        assert bm.forcing == ForcingLevel.GAME
        assert bm.artificial is True

    def test_transfer(self):
        bm = BidMeaning(transfer_to="H", artificial=True)
        assert bm.transfer_to == "H"


class TestBidNode:
    def test_simple_bid(self):
        node = BidNode(bid="1C", id="open-1c")
        assert node.bid == "1C"
        assert node.responses is None

    def test_recursive_responses(self):
        child = BidNode(bid="1D", meaning=BidMeaning(description="Negative"))
        parent = BidNode(bid="1C", responses=[child])
        assert len(parent.responses) == 1
        assert parent.responses[0].bid == "1D"

    def test_priority_bounds(self):
        node = BidNode(bid="1C", priority=500)
        assert node.priority == 500

    def test_priority_out_of_range(self):
        with pytest.raises(ValidationError):
            BidNode(bid="1C", priority=1001)

    def test_foreach_suit(self):
        node = BidNode(
            foreach_suit=ForeachSuit(variable="M", over="majors"),
            bid="1${M}",
        )
        assert node.foreach_suit.variable == "M"
        assert node.foreach_suit.over == "majors"


class TestForeachSuit:
    def test_valid_groups(self):
        for group in ("majors", "minors", "reds", "blacks", "all"):
            fs = ForeachSuit(variable="X", over=group)
            assert fs.over == group

    def test_invalid_group(self):
        with pytest.raises(ValidationError):
            ForeachSuit(variable="X", over="invalid")
