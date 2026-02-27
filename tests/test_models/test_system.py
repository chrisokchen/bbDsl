"""Tests for bbdsl.models.system."""

import pytest
from pydantic import ValidationError

from bbdsl.models.bid import BidNode
from bbdsl.models.common import Range
from bbdsl.models.system import (
    BBDSLDocument,
    Definitions,
    PatternDef,
    StrengthMethodDef,
    SuitQualityDef,
    SystemMetadata,
)


class TestDefinitions:
    def test_patterns(self):
        defs = Definitions(
            patterns={
                "balanced": PatternDef(
                    description="Balanced",
                    shapes=["4-3-3-3", "4-4-3-2", "5-3-3-2"],
                ),
            }
        )
        assert len(defs.patterns["balanced"].shapes) == 3

    def test_strength_methods(self):
        defs = Definitions(
            strength_methods={
                "hcp": StrengthMethodDef(
                    description={"zh-TW": "大牌點", "en": "HCP"},
                    range=[0, 37],
                ),
            }
        )
        assert defs.strength_methods["hcp"].range == [0, 37]

    def test_suit_qualities(self):
        defs = Definitions(
            suit_qualities={
                "good": SuitQualityDef(
                    top3_honors=Range(min=2),
                ),
            }
        )
        assert defs.suit_qualities["good"].top3_honors.min == 2


class TestSystemMetadata:
    def test_basic_metadata(self):
        sm = SystemMetadata(name="SAYC", version="1.0.0")
        assert sm.name == "SAYC"

    def test_i18n_name(self):
        sm = SystemMetadata(name={"zh-TW": "精準制", "en": "Precision Club"})
        assert sm.name["en"] == "Precision Club"


class TestBBDSLDocument:
    def test_minimal_document(self):
        doc = BBDSLDocument(
            bbdsl="0.3",
            system=SystemMetadata(name="Test"),
            openings=[BidNode(bid="1C")],
        )
        assert doc.bbdsl == "0.3"
        assert len(doc.openings) == 1

    def test_missing_system_raises(self):
        with pytest.raises(ValidationError):
            BBDSLDocument(bbdsl="0.3", openings=[BidNode(bid="1C")])

    def test_missing_openings_raises(self):
        with pytest.raises(ValidationError):
            BBDSLDocument(bbdsl="0.3", system=SystemMetadata(name="Test"))

    def test_import_alias(self):
        """The 'import' YAML key maps to import_ field."""
        doc = BBDSLDocument.model_validate({
            "bbdsl": "0.3",
            "system": {"name": "Test"},
            "openings": [{"bid": "1C"}],
            "import": {"bml": {"enabled": True}},
        })
        assert doc.import_ is not None
        assert doc.import_.bml == {"enabled": True}
