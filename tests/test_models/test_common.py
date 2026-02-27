"""Tests for bbdsl.models.common."""

import pytest
from pydantic import ValidationError

from bbdsl.models.common import (
    Author,
    Completeness,
    CompletenessStatus,
    ForcingLevel,
    Range,
    Seat,
    Vulnerability,
)


class TestEnums:
    def test_forcing_levels(self):
        assert ForcingLevel.GAME == "game"
        assert ForcingLevel("one_round") == ForcingLevel.ONE_ROUND

    def test_seat_values(self):
        assert Seat.FIRST == "1st"
        assert Seat("3rd") == Seat.THIRD

    def test_vulnerability_values(self):
        assert Vulnerability.BOTH == "both"
        assert Vulnerability("us") == Vulnerability.US


class TestRange:
    def test_min_max(self):
        r = Range(min=10, max=20)
        assert r.min == 10
        assert r.max == 20

    def test_min_only(self):
        r = Range(min=5)
        assert r.min == 5
        assert r.max is None

    def test_exactly(self):
        r = Range(exactly=4)
        assert r.exactly == 4

    def test_min_greater_than_max_raises(self):
        with pytest.raises(ValidationError, match="min.*must be <= max"):
            Range(min=20, max=10)

    def test_exactly_with_min_raises(self):
        with pytest.raises(ValidationError, match="exactly.*cannot be combined"):
            Range(exactly=4, min=3)

    def test_empty_range(self):
        r = Range()
        assert r.min is None
        assert r.max is None
        assert r.exactly is None


class TestAuthor:
    def test_basic_author(self):
        a = Author(name="C.C. Wei")
        assert a.name == "C.C. Wei"
        assert a.role is None

    def test_author_with_role(self):
        a = Author(name="Chris", role="maintainer", contact="chris@example.com")
        assert a.role == "maintainer"


class TestCompleteness:
    def test_partial_completeness(self):
        c = Completeness(openings=CompletenessStatus.COMPLETE, slam_bidding=CompletenessStatus.TODO)
        assert c.openings == CompletenessStatus.COMPLETE
        assert c.defensive is None

    def test_from_string(self):
        c = Completeness(openings="complete")  # type: ignore
        assert c.openings == CompletenessStatus.COMPLETE
