"""Tests for bbdsl.exporters.convcard_exporter."""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.convcard_exporter import (
    export_convcard,
    _t,
    _hand_summary,
    _extract_opening_rows,
    _extract_nt_info,
    _extract_strong_2c_info,
    _extract_weak_twos,
    _extract_conventions_list,
)
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import Range


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def precision_doc(examples_dir):
    return load_document(examples_dir / "precision.bbdsl.yaml")


@pytest.fixture
def sayc_doc(examples_dir):
    return load_document(examples_dir / "sayc.bbdsl.yaml")


@pytest.fixture
def two_over_one_doc(examples_dir):
    return load_document(examples_dir / "two_over_one.bbdsl.yaml")


@pytest.fixture
def minimal_doc(fixtures_dir):
    return load_document(fixtures_dir / "valid" / "minimal.yaml")


# ---------------------------------------------------------------------------
# Test _t (i18n)
# ---------------------------------------------------------------------------

class TestT:
    def test_none_returns_empty(self):
        assert _t(None, "en") == ""

    def test_string(self):
        assert _t("hello", "en") == "hello"

    def test_dict_en(self):
        assert _t({"en": "A", "zh-TW": "B"}, "en") == "A"

    def test_dict_zh(self):
        assert _t({"en": "A", "zh-TW": "B"}, "zh-TW") == "B"


# ---------------------------------------------------------------------------
# Test _hand_summary
# ---------------------------------------------------------------------------

class TestHandSummary:
    def _hand(self, **kwargs):
        return HandConstraint(**kwargs)

    def test_hcp_range(self):
        h = self._hand(hcp=Range(min=15, max=17))
        assert "15-17 HCP" in _hand_summary(h, "en")

    def test_hcp_min_only(self):
        h = self._hand(hcp=Range(min=22))
        assert "22+" in _hand_summary(h, "en")

    def test_hcp_max_only(self):
        h = self._hand(hcp=Range(max=7))
        assert "≤7 HCP" in _hand_summary(h, "en")

    def test_suit_length(self):
        h = self._hand(hearts=Range(min=5))
        summary = _hand_summary(h, "en")
        assert "hearts" in summary

    def test_suit_length_zh(self):
        h = self._hand(hearts=Range(min=5))
        summary = _hand_summary(h, "zh-TW")
        assert "紅心" in summary

    def test_shape_ref(self):
        h = self._hand(shape={"ref": "balanced"})
        summary = _hand_summary(h, "en")
        assert "balanced" in summary

    def test_none_hand(self):
        assert _hand_summary(None, "en") == ""

    def test_exact_suit_length(self):
        h = self._hand(hearts=Range(min=5, max=5))
        summary = _hand_summary(h, "en")
        assert "5=hearts" in summary


# ---------------------------------------------------------------------------
# Test _extract_opening_rows
# ---------------------------------------------------------------------------

class TestExtractOpeningRows:
    def test_precision_row_count(self, precision_doc):
        rows = _extract_opening_rows(precision_doc, "en")
        # Precision has 10 openings (1C/1D/1H/1S/1NT/2C/2D/2H/2S + one more)
        assert len(rows) >= 9

    def test_row_has_bid(self, precision_doc):
        rows = _extract_opening_rows(precision_doc, "en")
        bids = [r["bid"] for r in rows]
        assert "1C" in bids
        assert "1NT" in bids

    def test_artificial_flag(self, precision_doc):
        rows = _extract_opening_rows(precision_doc, "en")
        one_c = next(r for r in rows if r["bid"] == "1C")
        assert one_c["artificial"] is True

    def test_hcp_field(self, precision_doc):
        rows = _extract_opening_rows(precision_doc, "en")
        one_c = next(r for r in rows if r["bid"] == "1C")
        assert "16" in one_c["hcp"]

    def test_preemptive_flag(self, sayc_doc):
        rows = _extract_opening_rows(sayc_doc, "en")
        weak_two = next((r for r in rows if r["bid"] == "2H"), None)
        assert weak_two is not None
        assert weak_two["preemptive"] is True

    def test_description_populated(self, precision_doc):
        rows = _extract_opening_rows(precision_doc, "en")
        one_c = next(r for r in rows if r["bid"] == "1C")
        assert one_c["description"] != ""


# ---------------------------------------------------------------------------
# Test _extract_nt_info
# ---------------------------------------------------------------------------

class TestExtractNtInfo:
    def test_precision_has_nt(self, precision_doc):
        info = _extract_nt_info(precision_doc, "en")
        assert info is not None

    def test_hcp_range_precision(self, precision_doc):
        info = _extract_nt_info(precision_doc, "en")
        assert "15-17" in info["hcp_range"]

    def test_sayc_has_nt(self, sayc_doc):
        info = _extract_nt_info(sayc_doc, "en")
        assert info is not None
        assert "15-17" in info["hcp_range"]

    def test_has_stayman(self, precision_doc):
        info = _extract_nt_info(precision_doc, "en")
        assert info["has_stayman"] is True

    def test_has_jacoby(self, precision_doc):
        info = _extract_nt_info(precision_doc, "en")
        assert info["has_jacoby_transfer"] is True

    def test_no_nt_returns_none(self, minimal_doc):
        # minimal.yaml only has 1C
        info = _extract_nt_info(minimal_doc, "en")
        assert info is None


# ---------------------------------------------------------------------------
# Test _extract_strong_2c_info
# ---------------------------------------------------------------------------

class TestExtractStrong2cInfo:
    def test_precision_has_strong_2c(self, precision_doc):
        info = _extract_strong_2c_info(precision_doc, "en")
        assert info is not None

    def test_hcp_summary_present(self, precision_doc):
        info = _extract_strong_2c_info(precision_doc, "en")
        assert info["hcp_summary"] != ""

    def test_sayc_has_strong_2c(self, sayc_doc):
        info = _extract_strong_2c_info(sayc_doc, "en")
        assert info is not None

    def test_minimal_no_2c(self, minimal_doc):
        info = _extract_strong_2c_info(minimal_doc, "en")
        assert info is None


# ---------------------------------------------------------------------------
# Test _extract_weak_twos
# ---------------------------------------------------------------------------

class TestExtractWeakTwos:
    def test_sayc_has_weak_twos(self, sayc_doc):
        wts = _extract_weak_twos(sayc_doc, "en")
        assert len(wts) >= 2  # at least 2H and 2S

    def test_precision_has_weak_twos(self, precision_doc):
        wts = _extract_weak_twos(precision_doc, "en")
        # Precision 2H and 2S are preemptive
        assert len(wts) >= 2

    def test_minimal_no_weak_twos(self, minimal_doc):
        wts = _extract_weak_twos(minimal_doc, "en")
        assert wts == []

    def test_bid_field_present(self, sayc_doc):
        wts = _extract_weak_twos(sayc_doc, "en")
        bids = [wt["bid"] for wt in wts]
        assert "2H" in bids or "2S" in bids


# ---------------------------------------------------------------------------
# Test _extract_conventions_list
# ---------------------------------------------------------------------------

class TestExtractConventionsList:
    def test_precision_has_two_conventions(self, precision_doc):
        convs = _extract_conventions_list(precision_doc, "en")
        assert len(convs) == 2

    def test_convention_has_name(self, precision_doc):
        convs = _extract_conventions_list(precision_doc, "en")
        names = [c["name"] for c in convs]
        assert any("Stayman" in n for n in names)

    def test_convention_has_id(self, precision_doc):
        convs = _extract_conventions_list(precision_doc, "en")
        ids = [c["id"] for c in convs]
        assert any("stayman" in i.lower() for i in ids)

    def test_no_conventions_empty(self, minimal_doc):
        if not minimal_doc.conventions:
            convs = _extract_conventions_list(minimal_doc, "en")
            assert convs == []


# ---------------------------------------------------------------------------
# Test export_convcard (integration)
# ---------------------------------------------------------------------------

class TestExportConvcard:
    def test_returns_string(self, precision_doc):
        html = export_convcard(precision_doc)
        assert isinstance(html, str)

    def test_doctype_present(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "<!DOCTYPE html>" in html

    def test_system_name_in_html(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "Precision" in html

    def test_custom_title(self, precision_doc):
        html = export_convcard(precision_doc, title="My Custom Card")
        assert "My Custom Card" in html

    def test_opening_bids_as_table_rows(self, precision_doc):
        html = export_convcard(precision_doc)
        # Table contains 1C and 1NT as bid cells
        assert "1C" in html
        assert "1NT" in html

    def test_hcp_range_in_nt_section(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "15-17" in html

    def test_artificial_badge_present(self, precision_doc):
        html = export_convcard(precision_doc)
        # Artificial 1C opening should show art badge
        assert "art" in html or "Artificial" in html or "人工" in html

    def test_conventions_section_present(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "Stayman" in html or "stayman" in html

    def test_wbf_style_label(self, precision_doc):
        html = export_convcard(precision_doc, style="wbf")
        assert "WBF" in html

    def test_acbl_style_label(self, precision_doc):
        html = export_convcard(precision_doc, style="acbl")
        assert "ACBL" in html

    def test_locale_zh_system_name(self, precision_doc):
        html = export_convcard(precision_doc, locale="zh-TW")
        # precision has zh-TW name 精準制
        assert "精準制" in html

    def test_locale_zh_nt_label(self, precision_doc):
        html = export_convcard(precision_doc, locale="zh-TW")
        assert "1NT 開叫" in html

    def test_write_to_file(self, precision_doc, tmp_path):
        out = tmp_path / "precision.html"
        html = export_convcard(precision_doc, output_path=out)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == html

    def test_write_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "subdir" / "card.html"
        export_convcard(precision_doc, output_path=out)
        assert out.exists()

    def test_tailwind_cdn_present(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "tailwindcss" in html or "tailwind" in html.lower()

    def test_sayc_no_crash(self, sayc_doc):
        html = export_convcard(sayc_doc)
        assert "<!DOCTYPE html>" in html
        assert "1NT" in html

    def test_two_over_one_no_crash(self, two_over_one_doc):
        html = export_convcard(two_over_one_doc)
        assert "<!DOCTYPE html>" in html

    def test_minimal_no_crash(self, minimal_doc):
        html = export_convcard(minimal_doc)
        assert "<!DOCTYPE html>" in html
        assert "1C" in html

    def test_completeness_badge_present(self, precision_doc):
        html = export_convcard(precision_doc)
        # Precision has completeness defined
        assert "bg-green-500" in html or "bg-yellow-400" in html

    def test_strong_2c_section_present(self, precision_doc):
        html = export_convcard(precision_doc)
        assert "Strong" in html or "2♣" in html

    def test_weak_two_section_present(self, sayc_doc):
        html = export_convcard(sayc_doc)
        assert "Weak" in html or "弱二" in html

    def test_acbl_section_label_differs(self, sayc_doc):
        wbf_html = export_convcard(sayc_doc, style="wbf")
        acbl_html = export_convcard(sayc_doc, style="acbl")
        # ACBL uses "Two-Level Openings" vs "Weak Twos"
        assert wbf_html != acbl_html
