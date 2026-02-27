"""Tests for bbdsl.core.dealer_bridge."""

import pytest

from bbdsl.core.dealer_bridge import (
    constraint_to_dealer,
    dealer_to_constraint,
    openings_to_dealer_script,
)
from bbdsl.core.loader import load_document
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
# constraint_to_dealer
# ---------------------------------------------------------------------------

class TestConstraintToDealer:
    def test_none_constraint(self):
        assert constraint_to_dealer(None) == ""

    def test_empty_constraint(self):
        assert constraint_to_dealer(HandConstraint()) == ""

    def test_hcp_min(self):
        hc = HandConstraint(hcp=Range(min=16))
        out = constraint_to_dealer(hc)
        assert "hcp(south) >= 16" in out

    def test_hcp_max(self):
        hc = HandConstraint(hcp=Range(max=7))
        out = constraint_to_dealer(hc)
        assert "hcp(south) <= 7" in out

    def test_hcp_range(self):
        hc = HandConstraint(hcp=Range(min=15, max=17))
        out = constraint_to_dealer(hc)
        assert "hcp(south) >= 15" in out
        assert "hcp(south) <= 17" in out

    def test_hcp_exactly(self):
        hc = HandConstraint(hcp=Range(exactly=15))
        out = constraint_to_dealer(hc)
        assert "hcp(south) == 15" in out

    def test_suit_min(self):
        hc = HandConstraint(hearts=Range(min=5))
        out = constraint_to_dealer(hc)
        assert "hearts(south) >= 5" in out

    def test_suit_max(self):
        hc = HandConstraint(spades=Range(max=3))
        out = constraint_to_dealer(hc)
        assert "spades(south) <= 3" in out

    def test_suit_exactly(self):
        hc = HandConstraint(clubs=Range(exactly=4))
        out = constraint_to_dealer(hc)
        assert "clubs(south) == 4" in out

    def test_suit_range(self):
        hc = HandConstraint(diamonds=Range(min=3, max=5))
        out = constraint_to_dealer(hc)
        assert "diamonds(south) >= 3" in out
        assert "diamonds(south) <= 5" in out

    def test_shape_balanced(self):
        hc = HandConstraint(shape={"ref": "balanced"})
        out = constraint_to_dealer(hc)
        assert "shape(south" in out
        assert "4333" in out
        assert "4432" in out

    def test_shape_semi_balanced(self):
        hc = HandConstraint(shape={"ref": "semi_balanced"})
        out = constraint_to_dealer(hc)
        assert "shape(south" in out
        assert "5422" in out

    def test_shape_semi_balanced_hyphen(self):
        hc = HandConstraint(shape={"ref": "semi-balanced"})
        out = constraint_to_dealer(hc)
        assert "shape(south" in out
        assert "5422" in out

    def test_controls_min(self):
        hc = HandConstraint(controls=Range(min=4))
        out = constraint_to_dealer(hc)
        assert "aces(south)" in out
        assert "kings(south)" in out
        assert ">= 4" in out

    def test_controls_range(self):
        hc = HandConstraint(controls=Range(min=2, max=6))
        out = constraint_to_dealer(hc)
        assert ">= 2" in out
        assert "<= 6" in out

    def test_losing_tricks_max(self):
        hc = HandConstraint(losing_tricks=Range(max=7))
        out = constraint_to_dealer(hc)
        assert "loser(south) <= 7" in out

    def test_losing_tricks_range(self):
        hc = HandConstraint(losing_tricks=Range(min=4, max=8))
        out = constraint_to_dealer(hc)
        assert "loser(south) >= 4" in out
        assert "loser(south) <= 8" in out

    def test_multiple_conditions_joined_by_and(self):
        hc = HandConstraint(hcp=Range(min=15, max=17), hearts=Range(min=5))
        out = constraint_to_dealer(hc)
        assert " && " in out

    def test_custom_seat(self):
        hc = HandConstraint(hcp=Range(min=16))
        out = constraint_to_dealer(hc, seat="north")
        assert "hcp(north) >= 16" in out
        assert "south" not in out

    def test_combined_precision_1c(self):
        hc = HandConstraint(hcp=Range(min=16))
        out = constraint_to_dealer(hc)
        assert "hcp(south) >= 16" in out

    def test_combined_precision_1nt(self):
        hc = HandConstraint(hcp=Range(min=15, max=17), shape={"ref": "balanced"})
        out = constraint_to_dealer(hc)
        assert "hcp(south) >= 15" in out
        assert "hcp(south) <= 17" in out
        assert "shape(south" in out


# ---------------------------------------------------------------------------
# dealer_to_constraint
# ---------------------------------------------------------------------------

class TestDealerToConstraint:
    def test_empty_string(self):
        hc = dealer_to_constraint("")
        assert hc.hcp is None
        assert hc.hearts is None

    def test_hcp_min(self):
        hc = dealer_to_constraint("hcp(south) >= 16")
        assert hc.hcp is not None
        assert hc.hcp.min == 16

    def test_hcp_max(self):
        hc = dealer_to_constraint("hcp(south) <= 7")
        assert hc.hcp is not None
        assert hc.hcp.max == 7

    def test_hcp_range(self):
        hc = dealer_to_constraint("hcp(south) >= 15 && hcp(south) <= 17")
        assert hc.hcp.min == 15
        assert hc.hcp.max == 17

    def test_hcp_exact(self):
        hc = dealer_to_constraint("hcp(south) == 14")
        assert hc.hcp.min == 14
        assert hc.hcp.max == 14

    def test_suit_min(self):
        hc = dealer_to_constraint("hearts(south) >= 5")
        assert hc.hearts is not None
        assert hc.hearts.min == 5

    def test_suit_max(self):
        hc = dealer_to_constraint("spades(south) <= 3")
        assert hc.spades is not None
        assert hc.spades.max == 3

    def test_clubs(self):
        hc = dealer_to_constraint("clubs(south) >= 4")
        assert hc.clubs is not None
        assert hc.clubs.min == 4

    def test_diamonds(self):
        hc = dealer_to_constraint("diamonds(south) <= 2")
        assert hc.diamonds is not None
        assert hc.diamonds.max == 2

    def test_shape_balanced(self):
        hc = dealer_to_constraint("shape(south, any 4333 + any 4432 + any 5332)")
        assert hc.shape is not None
        assert isinstance(hc.shape, dict)
        assert hc.shape.get("ref") == "balanced"

    def test_shape_semi_balanced(self):
        hc = dealer_to_constraint("shape(south, any 5422 + any 6322)")
        assert hc.shape is not None
        assert hc.shape.get("ref") == "semi_balanced"

    def test_controls_min(self):
        hc = dealer_to_constraint("(aces(south)*2 + kings(south)) >= 4")
        assert hc.controls is not None
        assert hc.controls.min == 4

    def test_losing_tricks_max(self):
        hc = dealer_to_constraint("loser(south) <= 7")
        assert hc.losing_tricks is not None
        assert hc.losing_tricks.max == 7

    def test_mixed_conditions(self):
        hc = dealer_to_constraint(
            "hcp(south) >= 15 && hcp(south) <= 17 && shape(south, any 4333 + any 4432 + any 5332)"
        )
        assert hc.hcp.min == 15
        assert hc.hcp.max == 17
        assert hc.shape is not None

    def test_custom_seat(self):
        hc = dealer_to_constraint("hcp(north) >= 12 && hearts(north) >= 5", seat="north")
        assert hc.hcp.min == 12
        assert hc.hearts.min == 5

    def test_unrecognised_clause_ignored(self):
        hc = dealer_to_constraint("unknown_func(south) >= 10")
        assert hc.hcp is None
        assert hc.hearts is None

    def test_returns_handconstraint(self):
        hc = dealer_to_constraint("hcp(south) >= 12")
        assert isinstance(hc, HandConstraint)


# ---------------------------------------------------------------------------
# Round-trip: constraint → dealer → constraint
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def _roundtrip(self, hc: HandConstraint) -> HandConstraint:
        dealer_str = constraint_to_dealer(hc)
        return dealer_to_constraint(dealer_str)

    def test_hcp_range_roundtrip(self):
        hc = HandConstraint(hcp=Range(min=15, max=17))
        rt = self._roundtrip(hc)
        assert rt.hcp is not None
        assert rt.hcp.min == 15
        assert rt.hcp.max == 17

    def test_hcp_min_only_roundtrip(self):
        hc = HandConstraint(hcp=Range(min=16))
        rt = self._roundtrip(hc)
        assert rt.hcp.min == 16
        assert rt.hcp.max is None

    def test_suit_length_roundtrip(self):
        hc = HandConstraint(hearts=Range(min=5), spades=Range(max=3))
        rt = self._roundtrip(hc)
        assert rt.hearts.min == 5
        assert rt.spades.max == 3

    def test_shape_balanced_roundtrip(self):
        hc = HandConstraint(shape={"ref": "balanced"})
        rt = self._roundtrip(hc)
        assert rt.shape is not None
        assert rt.shape.get("ref") == "balanced"

    def test_shape_semi_balanced_roundtrip(self):
        hc = HandConstraint(shape={"ref": "semi_balanced"})
        rt = self._roundtrip(hc)
        assert rt.shape is not None
        assert rt.shape.get("ref") == "semi_balanced"

    def test_losing_tricks_roundtrip(self):
        hc = HandConstraint(losing_tricks=Range(max=7))
        rt = self._roundtrip(hc)
        assert rt.losing_tricks is not None
        assert rt.losing_tricks.max == 7

    def test_controls_roundtrip(self):
        hc = HandConstraint(controls=Range(min=4))
        rt = self._roundtrip(hc)
        assert rt.controls is not None
        assert rt.controls.min == 4


# ---------------------------------------------------------------------------
# openings_to_dealer_script
# ---------------------------------------------------------------------------

class TestOpeningsToDealerScript:
    def test_returns_string(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert isinstance(script, str)

    def test_system_name_in_script(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "Precision Club" in script

    def test_each_opening_has_block(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        for opening in precision_doc.openings:
            if opening.bid:
                assert f"Opening {opening.bid}" in script

    def test_generate_keyword_present(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "generate" in script

    def test_condition_keyword_present(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "condition" in script

    def test_action_keyword_present(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "action" in script

    def test_seat_in_conditions(self, precision_doc):
        script = openings_to_dealer_script(precision_doc, seat="west")
        assert "west" in script
        assert "south" not in script.split("# System:")[1]  # Not in condition clauses

    def test_hcp_conditions_present(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "hcp(south) >= 16" in script

    def test_sayc_no_crash(self, sayc_doc):
        script = openings_to_dealer_script(sayc_doc)
        assert isinstance(script, str)
        assert len(script) > 0

    def test_locale_header(self, precision_doc):
        script = openings_to_dealer_script(precision_doc, locale="en")
        assert "System:" in script

    def test_printall_in_script(self, precision_doc):
        script = openings_to_dealer_script(precision_doc)
        assert "printall" in script
