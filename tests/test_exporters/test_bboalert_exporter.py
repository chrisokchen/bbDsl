"""Tests for bbdsl.exporters.bboalert_exporter."""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.bboalert_exporter import (
    BBORow,
    build_explanation,
    export_bboalert,
    flatten_document,
)
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import ForcingLevel, Range


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).parent.parent / "fixtures" / ".." / ".." / "examples"


@pytest.fixture
def precision_doc(examples_dir):
    return load_document(examples_dir / "precision.bbdsl.yaml")


# ---------------------------------------------------------------------------
# TestBuildExplanation
# ---------------------------------------------------------------------------

class TestBuildExplanation:
    def test_none_meaning(self):
        assert build_explanation(None) == ''

    def test_description_only(self):
        m = BidMeaning(description={'en': 'Strong opening'})
        result = build_explanation(m, locale='en')
        assert 'Strong opening' in result

    def test_description_zh_tw(self):
        m = BidMeaning(description={'zh-TW': '強梅花'})
        result = build_explanation(m, locale='zh-TW')
        assert '強梅花' in result

    def test_hcp_range(self):
        m = BidMeaning(hand=HandConstraint(hcp=Range(min=16)))
        result = build_explanation(m, locale='en')
        assert '16+ HCP' in result

    def test_hcp_min_max(self):
        m = BidMeaning(hand=HandConstraint(hcp=Range(min=15, max=17)))
        result = build_explanation(m, locale='en')
        assert '15-17 HCP' in result

    def test_suit_length(self):
        m = BidMeaning(hand=HandConstraint(hearts=Range(min=5)))
        result = build_explanation(m, locale='en')
        assert '5+ hearts' in result

    def test_shape_ref(self):
        m = BidMeaning(hand=HandConstraint(shape={'ref': 'balanced'}))
        result = build_explanation(m, locale='en')
        assert 'balanced' in result

    def test_artificial_flag(self):
        m = BidMeaning(
            hand=HandConstraint(hcp=Range(min=16)),
            artificial=True,
        )
        result = build_explanation(m, locale='en')
        assert 'Alert' in result

    def test_forcing_gf(self):
        m = BidMeaning(
            hand=HandConstraint(hcp=Range(min=8)),
            forcing=ForcingLevel.GAME,
        )
        result = build_explanation(m, locale='en')
        assert 'GF' in result

    def test_transfer_to(self):
        m = BidMeaning(transfer_to='H', artificial=True, alertable=True)
        result = build_explanation(m, locale='en')
        assert '→H' in result

    def test_zh_tw_suit_labels(self):
        m = BidMeaning(hand=HandConstraint(hearts=Range(min=5)))
        result = build_explanation(m, locale='zh-TW')
        assert '紅心' in result

    def test_zh_tw_forcing(self):
        m = BidMeaning(
            hand=HandConstraint(hcp=Range(min=8)),
            forcing=ForcingLevel.GAME,
        )
        result = build_explanation(m, locale='zh-TW')
        assert '成局強迫' in result


# ---------------------------------------------------------------------------
# TestFlattenDocument
# ---------------------------------------------------------------------------

class TestFlattenDocument:
    def test_precision_openings_count(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        # 9 openings + many responses
        contexts = [r[0] for r in rows]
        # Root openings have empty context
        root_rows = [r for r in rows if r[0] == '']
        assert len(root_rows) == 9  # 1C 1D 1H 1S 1NT 2C 2D 2H 2S

    def test_response_has_nonempty_context(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        # There should be rows with '1C' as context (responses to 1C)
        one_c_responses = [r for r in rows if r[0] == '1C']
        assert len(one_c_responses) >= 3

    def test_call_column_is_bid(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        calls = {r[1] for r in rows}
        assert '1C' in calls
        assert '1NT' in calls

    def test_explanation_nonempty_for_described_bids(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        # 1C opening should have an explanation
        one_c = next((r for r in rows if r[0] == '' and r[1] == '1C'), None)
        assert one_c is not None
        assert one_c[2]  # explanation is not empty

    def test_zh_tw_locale(self, precision_doc):
        rows = flatten_document(precision_doc, locale='zh-TW')
        # Find 1C and check its explanation is in Chinese
        one_c = next((r for r in rows if r[0] == '' and r[1] == '1C'), None)
        assert one_c is not None
        # Should contain Chinese characters or numbers
        assert one_c[2]

    def test_nested_responses(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        # 1NT responses (like 2C Stayman) should have '1NT' as context
        nt_responses = [r for r in rows if r[0] == '1NT']
        assert len(nt_responses) >= 2

    def test_row_is_three_tuple(self, precision_doc):
        rows = flatten_document(precision_doc, locale='en')
        for row in rows:
            assert len(row) == 3
            assert all(isinstance(s, str) for s in row)


# ---------------------------------------------------------------------------
# TestExportBboalert
# ---------------------------------------------------------------------------

class TestExportBboalert:
    def test_returns_rows(self, precision_doc):
        rows = export_bboalert(precision_doc)
        assert isinstance(rows, list)
        assert len(rows) > 0

    def test_writes_file(self, precision_doc, tmp_path):
        out = tmp_path / 'precision.bboalert'
        export_bboalert(precision_doc, output_path=out, locale='en')
        assert out.exists()
        content = out.read_text(encoding='utf-8')
        assert '1C' in content

    def test_file_has_header_comments(self, precision_doc, tmp_path):
        out = tmp_path / 'precision.bboalert'
        export_bboalert(precision_doc, output_path=out, include_comments=True)
        content = out.read_text(encoding='utf-8')
        assert content.startswith('#')
        assert 'BBDSL' in content

    def test_file_no_comments(self, precision_doc, tmp_path):
        out = tmp_path / 'precision.bboalert'
        export_bboalert(precision_doc, output_path=out, include_comments=False)
        content = out.read_text(encoding='utf-8')
        assert not content.startswith('#')

    def test_csv_parseable(self, precision_doc, tmp_path):
        import csv
        out = tmp_path / 'precision.bboalert'
        export_bboalert(precision_doc, output_path=out, include_comments=False)
        rows = []
        with open(out, encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(row)
        assert all(len(r) >= 2 for r in rows)

    def test_alert_in_explanation_for_artificial(self, precision_doc):
        rows = export_bboalert(precision_doc, locale='en')
        # 1C opening is artificial → should have 'Alert' in explanation
        one_c = next((r for r in rows if r[0] == '' and r[1] == '1C'), None)
        assert one_c is not None
        assert 'Alert' in one_c[2]

    def test_zh_tw_export(self, precision_doc, tmp_path):
        out = tmp_path / 'precision_zh.bboalert'
        rows = export_bboalert(precision_doc, output_path=out, locale='zh-TW')
        assert rows
        content = out.read_text(encoding='utf-8')
        assert '精準' in content or 'HCP' in content
