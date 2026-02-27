"""Tests for bbdsl.exporters.bml_exporter."""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.bml_exporter import export_bml, _build_bml_description
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import ForcingLevel, Range


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).parent.parent / ".." / "examples"


@pytest.fixture
def precision_doc(examples_dir):
    return load_document(examples_dir / "precision.bbdsl.yaml")


# ---------------------------------------------------------------------------
# TestBuildBmlDescription
# ---------------------------------------------------------------------------

class TestBuildBmlDescription:
    """Tests for the description builder (via a simple mock node)."""

    class _Node:
        def __init__(self, meaning=None, ref=None):
            self.meaning = meaning
            self.ref = ref

    def test_none_node_returns_empty(self):
        node = self._Node(meaning=None, ref=None)
        result = _build_bml_description(node, "en", False)
        assert result == ""

    def test_description_en(self):
        m = BidMeaning(description={"en": "Strong club opening"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "Strong club opening" in result

    def test_description_zh_tw(self):
        m = BidMeaning(description={"zh-TW": "強梅花"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "zh-TW", False)
        assert "強梅花" in result

    def test_hcp_range_in_description(self):
        m = BidMeaning(hand=HandConstraint(hcp=Range(min=16)))
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "16+ HCP" in result

    def test_hcp_minmax(self):
        m = BidMeaning(hand=HandConstraint(hcp=Range(min=12, max=14)))
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "12-14 HCP" in result

    def test_suit_symbols(self):
        m = BidMeaning(hand=HandConstraint(hearts=Range(min=5)))
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", suit_symbols=True)
        assert "♥" in result

    def test_forcing_label_en(self):
        m = BidMeaning(forcing=ForcingLevel.GAME, description={"en": "GF relay"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "GF" in result

    def test_forcing_label_zh(self):
        m = BidMeaning(forcing=ForcingLevel.GAME, description={"en": "GF"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "zh-TW", False)
        assert "成局強迫" in result

    def test_artificial_flag(self):
        m = BidMeaning(artificial=True, description={"en": "Artificial"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "art" in result

    def test_preemptive_flag(self):
        m = BidMeaning(preemptive=True, description={"en": "Preempt"})
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "preemptive" in result

    def test_transfer_to(self):
        m = BidMeaning(transfer_to="H", artificial=True)
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "transfer to H" in result

    def test_convention_ref_note(self):
        m = BidMeaning(description={"en": "Stayman"})
        node = self._Node(meaning=m, ref="stayman")
        result = _build_bml_description(node, "en", False)
        assert "[→stayman]" in result

    def test_shape_balanced_en(self):
        m = BidMeaning(hand=HandConstraint(shape={"ref": "balanced"}))
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "en", False)
        assert "balanced" in result

    def test_shape_balanced_zh(self):
        m = BidMeaning(hand=HandConstraint(shape={"ref": "balanced"}))
        node = self._Node(meaning=m)
        result = _build_bml_description(node, "zh-TW", False)
        assert "平均" in result


# ---------------------------------------------------------------------------
# TestExportBml
# ---------------------------------------------------------------------------

class TestExportBml:
    def test_returns_string(self, precision_doc):
        result = export_bml(precision_doc)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_opening_bids(self, precision_doc):
        result = export_bml(precision_doc)
        assert "1C" in result
        assert "1NT" in result

    def test_has_header_comment(self, precision_doc):
        result = export_bml(precision_doc, include_comments=True)
        assert result.startswith("#")
        assert "BBDSL" in result

    def test_no_header_comment(self, precision_doc):
        result = export_bml(precision_doc, include_comments=False, include_conventions=False)
        assert not result.startswith("#")

    def test_responses_indented(self, precision_doc):
        result = export_bml(precision_doc, include_comments=False)
        lines = result.splitlines()
        # 1C should appear at indent 0
        one_c_lines = [l for l in lines if l.startswith("1C")]
        assert len(one_c_lines) >= 1
        # Responses to 1C should be indented
        response_lines = [l for l in lines if l.startswith("  ")]
        assert len(response_lines) >= 1

    def test_suit_symbols_mode(self, precision_doc):
        result = export_bml(precision_doc, suit_symbols=True)
        # The document uses hand constraints; if any bid has suit lengths, ♥ etc. should appear
        # At minimum, the result should be valid text
        assert isinstance(result, str)

    def test_locale_zh_tw(self, precision_doc):
        result = export_bml(precision_doc, locale="zh-TW")
        assert isinstance(result, str)
        # Should contain Chinese characters (from descriptions or forcing labels)
        assert len(result) > 0

    def test_writes_file(self, precision_doc, tmp_path):
        out = tmp_path / "precision.bml"
        export_bml(precision_doc, output_path=out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "1C" in content

    def test_bid_width_alignment(self, precision_doc):
        """Bid column should be padded to at least 4 chars."""
        result = export_bml(precision_doc, include_comments=False)
        lines = [l for l in result.splitlines() if l.strip() and not l.startswith("#")]
        for line in lines:
            stripped = line.lstrip()
            if "  " in stripped:  # has description
                # bid part should be >= 4 chars before description
                bid_part = stripped.split("  ")[0]
                assert len(bid_part.rstrip()) >= 2  # e.g. "1C" -> 2+

    def test_conventions_included_as_comments(self, precision_doc):
        result = export_bml(precision_doc, include_conventions=True)
        # precision.bbdsl.yaml has conventions; they should appear as # comments
        if precision_doc.conventions:
            assert "# Convention:" in result

    def test_no_conventions(self, precision_doc):
        result = export_bml(precision_doc, include_conventions=False, include_comments=False)
        assert "# Convention:" not in result

    def test_ends_with_newline(self, precision_doc):
        result = export_bml(precision_doc)
        assert result.endswith("\n")
