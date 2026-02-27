"""Tests for bbdsl.core.selector."""

import pytest

from bbdsl.core.selector import (
    evaluate_condition,
    hand_from_constraint,
    parse_selection_rules,
    select_bid,
    select_opening,
)
from bbdsl.models.bid import HandConstraint
from bbdsl.models.common import Range


# ---------------------------------------------------------------------------
# TestEvaluateCondition
# ---------------------------------------------------------------------------

class TestEvaluateCondition:
    def test_true_literal(self):
        assert evaluate_condition("true", {}) is True

    def test_false_literal(self):
        assert evaluate_condition("false", {}) is False

    def test_hcp_gte(self):
        assert evaluate_condition("hcp >= 16", {"hcp": 16}) is True
        assert evaluate_condition("hcp >= 16", {"hcp": 15}) is False

    def test_hcp_range(self):
        assert evaluate_condition("hcp >= 12 && hcp <= 14", {"hcp": 13}) is True
        assert evaluate_condition("hcp >= 12 && hcp <= 14", {"hcp": 11}) is False
        assert evaluate_condition("hcp >= 12 && hcp <= 14", {"hcp": 15}) is False

    def test_suit_length(self):
        assert evaluate_condition("hearts >= 5", {"hearts": 5}) is True
        assert evaluate_condition("hearts >= 5", {"hearts": 4}) is False

    def test_or_condition(self):
        assert evaluate_condition("hearts >= 5 || spades >= 5", {"hearts": 5, "spades": 3}) is True
        assert evaluate_condition("hearts >= 5 || spades >= 5", {"hearts": 3, "spades": 5}) is True
        assert evaluate_condition("hearts >= 5 || spades >= 5", {"hearts": 3, "spades": 3}) is False

    def test_shape_in_balanced(self):
        assert evaluate_condition("shape in balanced", {"shape": "balanced"}) is True
        assert evaluate_condition("shape in balanced", {"shape": "semi_balanced"}) is False
        assert evaluate_condition("shape in balanced", {"shape": None}) is False

    def test_not_operator(self):
        assert evaluate_condition("!hcp >= 20", {"hcp": 15}) is True
        assert evaluate_condition("!hcp >= 20", {"hcp": 21}) is False

    def test_logical_and_or_combined(self):
        hand = {"hcp": 18, "hearts": 5}
        assert evaluate_condition("hcp >= 16 && hearts >= 5", hand) is True
        assert evaluate_condition("hcp >= 20 || hearts >= 5", hand) is True

    def test_missing_variable_defaults_to_zero(self):
        assert evaluate_condition("hearts >= 1", {}) is False
        assert evaluate_condition("hearts >= 0", {}) is True

    def test_invalid_condition_raises(self):
        with pytest.raises(ValueError):
            evaluate_condition("hcp === 16", {"hcp": 16})

    def test_longest_suit_auto_computed(self):
        hand = {"spades": 6, "hearts": 4, "diamonds": 2, "clubs": 1}
        assert evaluate_condition("longest_suit >= 6", hand) is True
        assert evaluate_condition("longest_suit >= 7", hand) is False

    def test_second_suit_auto_computed(self):
        hand = {"spades": 6, "hearts": 4, "diamonds": 2, "clubs": 1}
        assert evaluate_condition("second_suit >= 4", hand) is True

    def test_compound_strong_hand(self):
        hand = {"hcp": 20, "controls": 5, "longest_suit": 7}
        assert evaluate_condition("hcp >= 16 && longest_suit >= 7", hand) is True


# ---------------------------------------------------------------------------
# TestParseSelectionRules
# ---------------------------------------------------------------------------

class TestParseSelectionRules:
    def test_empty_returns_empty(self):
        assert parse_selection_rules({}) == []
        assert parse_selection_rules(None) == []

    def test_flat_rules_key(self):
        sr = {"rules": [{"id": "r1", "condition": "hcp >= 16", "select": "1C"}]}
        rules = parse_selection_rules(sr)
        assert len(rules) == 1
        assert rules[0]["id"] == "r1"

    def test_named_group_format(self):
        sr = {
            "opening_selection": {
                "rules": [
                    {"id": "r1", "condition": "hcp >= 16", "select": "1C"},
                    {"id": "r2", "condition": "true", "select": "1D"},
                ]
            }
        }
        rules = parse_selection_rules(sr)
        assert len(rules) == 2

    def test_multiple_named_groups(self):
        sr = {
            "group_a": {"rules": [{"condition": "hcp >= 20", "select": "2C"}]},
            "group_b": {"rules": [{"condition": "true", "select": "1NT"}]},
        }
        rules = parse_selection_rules(sr)
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# TestSelectBid
# ---------------------------------------------------------------------------

class TestSelectBid:
    def test_first_match_wins(self):
        rules = [
            {"id": "r1", "condition": "hcp >= 16", "select": "1C"},
            {"id": "r2", "condition": "hcp >= 12", "select": "1NT"},
            {"id": "r3", "condition": "true", "select": "1D"},
        ]
        result = select_bid({"hcp": 18}, rules)
        assert result is not None
        assert result["select"] == "1C"

    def test_fallthrough_to_second(self):
        rules = [
            {"id": "r1", "condition": "hcp >= 16", "select": "1C"},
            {"id": "r2", "condition": "hcp >= 12", "select": "1NT"},
            {"id": "r3", "condition": "true", "select": "1D"},
        ]
        result = select_bid({"hcp": 13}, rules)
        assert result is not None
        assert result["select"] == "1NT"

    def test_catchall_matches(self):
        rules = [
            {"id": "r1", "condition": "hcp >= 16", "select": "1C"},
            {"id": "r2", "condition": "true", "select": "1D"},
        ]
        result = select_bid({"hcp": 8}, rules)
        assert result is not None
        assert result["select"] == "1D"

    def test_no_match_returns_none(self):
        rules = [{"id": "r1", "condition": "hcp >= 16", "select": "1C"}]
        result = select_bid({"hcp": 10}, rules)
        assert result is None

    def test_empty_rules_returns_none(self):
        assert select_bid({"hcp": 15}, []) is None

    def test_invalid_condition_skipped(self):
        rules = [
            {"id": "bad", "condition": "hcp === invalid", "select": "1C"},
            {"id": "ok", "condition": "true", "select": "1NT"},
        ]
        result = select_bid({"hcp": 10}, rules)
        assert result is not None
        assert result["select"] == "1NT"


# ---------------------------------------------------------------------------
# TestSelectOpening
# ---------------------------------------------------------------------------

class TestSelectOpening:
    def test_select_strong_club(self):
        sr = {
            "rules": [
                {"condition": "hcp >= 16", "select": "1C"},
                {"condition": "true", "select": "1D"},
            ]
        }
        result = select_opening({"hcp": 20}, sr)
        assert result == "1C"

    def test_select_fallback(self):
        sr = {
            "rules": [
                {"condition": "hcp >= 16", "select": "1C"},
                {"condition": "true", "select": "1D"},
            ]
        }
        result = select_opening({"hcp": 10}, sr)
        assert result == "1D"

    def test_no_match_returns_none(self):
        sr = {"rules": [{"condition": "hcp >= 16", "select": "1C"}]}
        result = select_opening({"hcp": 10}, sr)
        assert result is None


# ---------------------------------------------------------------------------
# TestHandFromConstraint
# ---------------------------------------------------------------------------

class TestHandFromConstraint:
    def test_basic_hcp(self):
        hc = HandConstraint(hcp=Range(min=16, max=21))
        hand = hand_from_constraint(hc)
        assert hand["hcp"] == 18  # (16+21)//2

    def test_suit_lengths(self):
        hc = HandConstraint(hearts=Range(min=5, max=5))
        hand = hand_from_constraint(hc)
        assert hand["hearts"] == 5

    def test_longest_suit_computed(self):
        hc = HandConstraint(spades=Range(min=6, max=6))
        hand = hand_from_constraint(hc)
        assert hand["longest_suit"] == 6

    def test_shape_ref(self):
        hc = HandConstraint(shape={"ref": "balanced"})
        hand = hand_from_constraint(hc)
        assert hand["shape"] == "balanced"

    def test_shape_string(self):
        hc = HandConstraint(shape="balanced")
        hand = hand_from_constraint(hc)
        assert hand["shape"] == "balanced"

    def test_missing_fields_default_zero(self):
        hc = HandConstraint()
        hand = hand_from_constraint(hc)
        assert hand["hcp"] == 0
        assert hand["hearts"] == 0
