"""Tests for bbdsl.models.context."""

from bbdsl.models.common import Seat, Vulnerability
from bbdsl.models.context import Context, ContextOverride, OpponentPattern


class TestOpponentPattern:
    def test_simple_pass(self):
        p = OpponentPattern(simple="pass")
        assert p.simple == "pass"

    def test_concrete_bid(self):
        p = OpponentPattern(bid="1H")
        assert p.bid == "1H"

    def test_bid_type(self):
        p = OpponentPattern(bid_type="takeout_double")
        assert p.bid_type == "takeout_double"

    def test_any_of_composition(self):
        p = OpponentPattern(
            any_of=[
                OpponentPattern(bid="1H"),
                OpponentPattern(bid="1S"),
            ]
        )
        assert len(p.any_of) == 2

    def test_not_pattern(self):
        p = OpponentPattern.model_validate({"not": {"simple": "pass"}})
        assert p.not_.simple == "pass"

    def test_nested_composition(self):
        p = OpponentPattern(
            all_of=[
                OpponentPattern(level=2),
                OpponentPattern.model_validate({"not": {"suit": "NT"}}),
            ]
        )
        assert len(p.all_of) == 2


class TestContext:
    def test_seat_context(self):
        c = Context(seat=Seat.FIRST)
        assert c.seat == Seat.FIRST

    def test_multi_seat(self):
        c = Context(seat=[Seat.THIRD, Seat.FOURTH])
        assert len(c.seat) == 2

    def test_vulnerability(self):
        c = Context(vulnerability=Vulnerability.US)
        assert c.vulnerability == Vulnerability.US

    def test_with_opponent(self):
        c = Context(opponent_action=OpponentPattern(simple="double"))
        assert c.opponent_action.simple == "double"


class TestContextOverride:
    def test_basic_override(self):
        co = ContextOverride(
            context=Context(seat=Seat.THIRD),
            meaning={"description": "Light opening in 3rd seat"},
        )
        assert co.context.seat == Seat.THIRD

    def test_ref_context(self):
        """When context is a dict with 'ref', it stays as dict via model_validate."""
        co = ContextOverride.model_validate({
            "context": {"ref": "third_seat_favorable"},
            "meaning": None,
        })
        # Pydantic tries Context first; since 'ref' isn't a Context field,
        # we check it was parsed (Context with extra='forbid' would reject,
        # but our model allows it as a valid Context with no matching fields)
        assert co.context is not None
