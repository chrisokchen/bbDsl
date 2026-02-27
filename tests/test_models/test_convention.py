"""Tests for bbdsl.models.convention."""

import pytest
from pydantic import ValidationError

from bbdsl.models.convention import Convention, ConventionParameter, ConventionTrigger


class TestConventionId:
    def test_valid_ids(self):
        valid_ids = [
            "bbdsl/stayman-v1",
            "chris/precision-relay-v2",
            "acbl/jacoby-transfer-v1",
            "my-club/lebensohl-v3",
        ]
        for cid in valid_ids:
            conv = Convention(id=cid, name="Test")
            assert conv.id == cid

    def test_invalid_ids(self):
        invalid_ids = [
            "Stayman-v1",          # no scope
            "bbdsl/Stayman-v1",    # uppercase
            "/stayman-v1",         # empty scope
            "bbdsl/stayman",       # no version
            "bbdsl/stayman-v",     # no version number
            "1scope/name-v1",      # starts with digit
        ]
        for cid in invalid_ids:
            with pytest.raises(ValidationError, match="Convention ID"):
                Convention(id=cid, name="Test")


class TestConvention:
    def test_basic_convention(self):
        conv = Convention(
            id="bbdsl/stayman-v1",
            name={"zh-TW": "史泰曼", "en": "Stayman"},
            category="notrump",
            trigger=ConventionTrigger(after=["1NT"], bid="2C"),
        )
        assert conv.category == "notrump"
        assert conv.trigger.bid == "2C"

    def test_convention_with_parameters(self):
        conv = Convention(
            id="bbdsl/stayman-v1",
            name="Stayman",
            parameters={
                "puppet": ConventionParameter(type="boolean", default=False),
            },
        )
        assert conv.parameters["puppet"].type == "boolean"

    def test_convention_relationships(self):
        conv = Convention(
            id="bbdsl/stayman-v1",
            name="Stayman",
            conflicts_with=["bbdsl/puppet-stayman-v1"],
            requires=["bbdsl/jacoby-transfer-v1"],
        )
        assert len(conv.conflicts_with) == 1
