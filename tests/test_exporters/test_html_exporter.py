"""Tests for bbdsl.exporters.html_exporter."""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.html_exporter import (
    export_html,
    _t,
    _hand_parts,
    _build_description,
    _build_hand_tooltip,
    _node_id,
    _flatten_tree,
    _build_conv_views,
)
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import ForcingLevel, Range


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def precision_doc(examples_dir):
    return load_document(examples_dir / "precision.bbdsl.yaml")


@pytest.fixture
def minimal_doc(fixtures_dir):
    return load_document(fixtures_dir / "valid" / "minimal.yaml")


# ---------------------------------------------------------------------------
# Test _t (i18n extractor)
# ---------------------------------------------------------------------------

class TestT:
    def test_none_returns_empty(self):
        assert _t(None, "en") == ""

    def test_string_passthrough(self):
        assert _t("hello", "en") == "hello"

    def test_dict_en(self):
        assert _t({"en": "Hello", "zh-TW": "你好"}, "en") == "Hello"

    def test_dict_zh(self):
        assert _t({"en": "Hello", "zh-TW": "你好"}, "zh-TW") == "你好"

    def test_dict_fallback_to_en(self):
        assert _t({"en": "Hello"}, "zh-TW") == "Hello"

    def test_dict_fallback_to_first_value(self):
        assert _t({"fr": "Bonjour"}, "en") == "Bonjour"


# ---------------------------------------------------------------------------
# Test _node_id
# ---------------------------------------------------------------------------

class TestNodeId:
    def test_simple_bid(self):
        assert _node_id("1C") == "n-1C"

    def test_path_with_hyphen(self):
        nid = _node_id("1C-1D")
        assert nid.startswith("n-")
        assert "-" not in nid[2:]  # hyphens replaced with underscores

    def test_path_with_space(self):
        nid = _node_id("1C 1D")
        assert " " not in nid


# ---------------------------------------------------------------------------
# Test _hand_parts
# ---------------------------------------------------------------------------

class TestHandParts:
    def _hand(self, **kwargs):
        return HandConstraint(**kwargs)

    def test_hcp_range(self):
        h = self._hand(hcp=Range(min=15, max=17))
        parts = _hand_parts(h, "en", False)
        assert "15-17 HCP" in parts

    def test_hcp_min_only(self):
        h = self._hand(hcp=Range(min=16))
        parts = _hand_parts(h, "en", False)
        assert "16+ HCP" in parts

    def test_hcp_max_only(self):
        h = self._hand(hcp=Range(max=7))
        parts = _hand_parts(h, "en", False)
        assert "≤7 HCP" in parts

    def test_suit_en(self):
        h = self._hand(hearts=Range(min=5))
        parts = _hand_parts(h, "en", False)
        assert any("hearts" in p for p in parts)

    def test_suit_zh(self):
        h = self._hand(hearts=Range(min=5))
        parts = _hand_parts(h, "zh-TW", False)
        assert any("紅心" in p for p in parts)

    def test_suit_symbols(self):
        h = self._hand(spades=Range(min=5))
        parts = _hand_parts(h, "en", True)
        assert any("♠" in p for p in parts)

    def test_shape_ref(self):
        h = self._hand(shape={"ref": "balanced"})
        parts = _hand_parts(h, "en", False)
        assert "balanced" in parts

    def test_shape_ref_zh(self):
        h = self._hand(shape={"ref": "balanced"})
        parts = _hand_parts(h, "zh-TW", False)
        assert "平均" in parts

    def test_none_hand_returns_empty(self):
        assert _hand_parts(None, "en", False) == []


# ---------------------------------------------------------------------------
# Test _build_description
# ---------------------------------------------------------------------------

class TestBuildDescription:
    class _Node:
        def __init__(self, meaning=None, ref=None):
            self.meaning = meaning
            self.ref = ref

    def test_no_meaning_no_ref(self):
        node = self._Node()
        assert _build_description(node, "en", False) == ""

    def test_ref_only(self):
        node = self._Node(meaning=None, ref="bbdsl/stayman-v1")
        assert "stayman" in _build_description(node, "en", False)

    def test_description_en(self):
        meaning = BidMeaning(description={"en": "Balanced", "zh-TW": "平均"})
        node = self._Node(meaning=meaning)
        desc = _build_description(node, "en", False)
        assert "Balanced" in desc

    def test_description_zh(self):
        meaning = BidMeaning(description={"en": "Balanced", "zh-TW": "平均"})
        node = self._Node(meaning=meaning)
        desc = _build_description(node, "zh-TW", False)
        assert "平均" in desc

    def test_artificial_flag(self):
        meaning = BidMeaning(
            description={"en": "Artificial"}, artificial=True
        )
        node = self._Node(meaning=meaning)
        desc = _build_description(node, "en", False)
        assert "art" in desc

    def test_forcing_gf(self):
        meaning = BidMeaning(
            description={"en": "Strong"}, forcing=ForcingLevel.GAME
        )
        node = self._Node(meaning=meaning)
        desc = _build_description(node, "en", False)
        assert "GF" in desc

    def test_preemptive_flag_en(self):
        meaning = BidMeaning(
            description={"en": "Weak Two"}, preemptive=True
        )
        node = self._Node(meaning=meaning)
        desc = _build_description(node, "en", False)
        assert "preemptive" in desc


# ---------------------------------------------------------------------------
# Test _flatten_tree
# ---------------------------------------------------------------------------

class TestFlattenTree:
    def test_precision_openings_count(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        # At least one entry per opening (10+ openings in precision)
        assert len(result) >= 10

    def test_depth_zero_for_openings(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        depth0 = [n for n in result if n["depth"] == 0]
        assert len(depth0) == len(precision_doc.openings)

    def test_responses_are_depth_one(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        depth1 = [n for n in result if n["depth"] == 1]
        assert len(depth1) > 0

    def test_by_field_defaults(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        openers = [n for n in result if n["depth"] == 0]
        for node in openers:
            assert node["by"] == "opener"

    def test_path_format(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        # Top-level: just the bid; response: "opening-response"
        top = [n for n in result if n["depth"] == 0]
        assert all("-" not in n["path"] for n in top)
        resp = [n for n in result if n["depth"] == 1]
        assert all("-" in n["path"] for n in resp)

    def test_has_children_flag(self, precision_doc):
        result: list[dict] = []
        _flatten_tree(precision_doc.openings, "", 0, "en", False, result)
        # 1C has responses → has_children=True
        one_c = next(n for n in result if n["bid"] == "1C" and n["depth"] == 0)
        assert one_c["has_children"] is True


# ---------------------------------------------------------------------------
# Test _build_conv_views
# ---------------------------------------------------------------------------

class TestBuildConvViews:
    def test_precision_has_conventions(self, precision_doc):
        views = _build_conv_views(precision_doc, "en", False)
        assert len(views) >= 2  # stayman + jacoby_transfer

    def test_convention_has_name(self, precision_doc):
        views = _build_conv_views(precision_doc, "en", False)
        names = [v["name"] for v in views]
        assert any("Stayman" in n for n in names)

    def test_convention_node_id_format(self, precision_doc):
        views = _build_conv_views(precision_doc, "en", False)
        for v in views:
            assert v["node_id"].startswith("conv-")

    def test_no_conventions_returns_empty(self, minimal_doc):
        if not minimal_doc.conventions:
            views = _build_conv_views(minimal_doc, "en", False)
            assert views == []


# ---------------------------------------------------------------------------
# Test export_html (integration)
# ---------------------------------------------------------------------------

class TestExportHtml:
    def test_returns_string(self, precision_doc):
        html = export_html(precision_doc)
        assert isinstance(html, str)

    def test_doctype_present(self, precision_doc):
        html = export_html(precision_doc)
        assert "<!DOCTYPE html>" in html

    def test_system_name_in_title(self, precision_doc):
        html = export_html(precision_doc)
        assert "Precision" in html

    def test_custom_title(self, precision_doc):
        html = export_html(precision_doc, title="My Custom Title")
        assert "My Custom Title" in html

    def test_opening_bids_present(self, precision_doc):
        html = export_html(precision_doc)
        # Check a few bids are present as data-path attributes
        assert 'data-path="1C"' in html
        assert 'data-path="1NT"' in html

    def test_response_path_present(self, precision_doc):
        html = export_html(precision_doc)
        assert 'data-path="1C-1D"' in html

    def test_opener_color_class(self, precision_doc):
        html = export_html(precision_doc)
        assert "bg-blue-50" in html

    def test_responder_color_class(self, precision_doc):
        html = export_html(precision_doc)
        assert "bg-green-50" in html

    def test_artificial_badge(self, precision_doc):
        html = export_html(precision_doc)
        assert "art" in html

    def test_conventions_section_present(self, precision_doc):
        html = export_html(precision_doc)
        # Convention IDs should appear
        assert "stayman" in html.lower() or "Stayman" in html

    def test_completeness_items_present(self, precision_doc):
        html = export_html(precision_doc)
        # Precision has completeness field
        assert "bg-green-500" in html or "bg-yellow-400" in html

    def test_tailwind_cdn_present(self, precision_doc):
        html = export_html(precision_doc)
        assert "tailwindcss" in html or "tailwind" in html.lower()

    def test_locale_zh(self, precision_doc):
        html = export_html(precision_doc, locale="zh-TW")
        assert "精準制" in html or "開叫系統" in html

    def test_suit_symbols_flag(self, precision_doc):
        html = export_html(precision_doc, suit_symbols=True)
        # Suit symbols are used in hand tooltips/descriptions
        assert "♠" in html or "♥" in html or "♦" in html or "♣" in html

    def test_search_input_present(self, precision_doc):
        html = export_html(precision_doc)
        assert "handleSearch" in html

    def test_expand_collapse_buttons(self, precision_doc):
        html = export_html(precision_doc)
        assert "expandAll" in html
        assert "collapseAll" in html

    def test_node_json_embedded(self, precision_doc):
        html = export_html(precision_doc)
        assert "nodeData" in html

    def test_write_to_file(self, precision_doc, tmp_path):
        out = tmp_path / "precision.html"
        html = export_html(precision_doc, output_path=out)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == html

    def test_write_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "subdir" / "output.html"
        export_html(precision_doc, output_path=out)
        assert out.exists()

    def test_minimal_doc_no_crash(self, minimal_doc):
        html = export_html(minimal_doc)
        assert "<!DOCTYPE html>" in html
        assert 'data-path="1C"' in html

    def test_sayc_all_openings(self, examples_dir):
        doc = load_document(examples_dir / "sayc.bbdsl.yaml")
        html = export_html(doc)
        assert 'data-path="1NT"' in html
        assert 'data-path="2C"' in html

    def test_two_over_one_gf_badge(self, examples_dir):
        doc = load_document(examples_dir / "two_over_one.bbdsl.yaml")
        html = export_html(doc)
        # 2/1 GF responses should have GF badge
        assert "GF" in html
