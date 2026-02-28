"""Tests for bbdsl.core.comparator."""

import json

import pytest

from bbdsl.core.comparator import (
    ComparisonReport,
    DiffCase,
    compare_systems,
)
from bbdsl.core.loader import load_document
from bbdsl.core.sim_engine import AuctionStep, Deal, generate_deal

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"
TWO_OVER_ONE_PATH = "examples/two_over_one.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


@pytest.fixture(scope="module")
def two_over_one_doc():
    return load_document(TWO_OVER_ONE_PATH)


# ---------------------------------------------------------------------------
# TestDiffCase
# ---------------------------------------------------------------------------

class TestDiffCase:
    def _make_diff_case(self):
        deal = generate_deal(seed=1)
        return DiffCase(
            deal_number=1,
            deal=deal,
            auction_a=[AuctionStep("N", "1C", "opener", "16+ HCP")],
            auction_b=[AuctionStep("N", "Pass", "opener", "No match")],
            contract_a="1C by North",
            contract_b=None,
        )

    def test_to_dict_has_deal_number(self):
        dc = self._make_diff_case()
        assert dc.to_dict()["deal_number"] == 1

    def test_to_dict_has_deal(self):
        dc = self._make_diff_case()
        d = dc.to_dict()
        assert "deal" in d
        assert "north" in d["deal"]

    def test_to_dict_has_auction_a(self):
        dc = self._make_diff_case()
        d = dc.to_dict()
        assert "auction_a" in d
        assert isinstance(d["auction_a"], list)

    def test_to_dict_has_auction_b(self):
        dc = self._make_diff_case()
        d = dc.to_dict()
        assert "auction_b" in d

    def test_to_dict_has_contracts(self):
        dc = self._make_diff_case()
        d = dc.to_dict()
        assert "contract_a" in d
        assert "contract_b" in d

    def test_to_dict_json_serializable(self):
        dc = self._make_diff_case()
        serialized = json.dumps(dc.to_dict())
        assert len(serialized) > 0

    def test_contracts_stored_correctly(self):
        dc = self._make_diff_case()
        assert dc.contract_a == "1C by North"
        assert dc.contract_b is None


# ---------------------------------------------------------------------------
# TestComparisonReport
# ---------------------------------------------------------------------------

class TestComparisonReport:
    def _make_report(self, same=3, differ=2, n=5):
        return ComparisonReport(
            system_a="Precision Club",
            system_b="SAYC",
            n_deals=n,
            same_count=same,
            differ_count=differ,
            passed_out_a=1,
            passed_out_b=0,
            diff_cases=[],
            seed=42,
        )

    def test_agree_rate_correct(self):
        r = self._make_report(same=3, differ=2, n=5)
        assert abs(r.agree_rate - 0.6) < 1e-9

    def test_agree_rate_zero_deals(self):
        r = self._make_report(same=0, differ=0, n=0)
        assert r.agree_rate == 0.0

    def test_agree_rate_all_same(self):
        r = self._make_report(same=10, differ=0, n=10)
        assert r.agree_rate == 1.0

    def test_summary_text_en_contains_system_names(self):
        r = self._make_report()
        t = r.summary_text("en")
        assert "Precision Club" in t
        assert "SAYC" in t

    def test_summary_text_en_contains_counts(self):
        r = self._make_report(same=3, differ=2, n=5)
        t = r.summary_text("en")
        assert "3" in t
        assert "2" in t
        assert "5" in t

    def test_summary_text_zh_tw(self):
        r = self._make_report()
        t = r.summary_text("zh-TW")
        assert "制度比較" in t
        assert "Precision Club" in t

    def test_summary_text_agree_rate_percent(self):
        r = self._make_report(same=3, differ=2, n=5)
        t = r.summary_text("en")
        assert "60.0%" in t

    def test_to_dict_has_all_keys(self):
        r = self._make_report()
        d = r.to_dict()
        required = {
            "system_a", "system_b", "n_deals", "same_count", "differ_count",
            "passed_out_a", "passed_out_b", "agree_rate", "seed", "diff_cases"
        }
        assert required.issubset(d.keys())

    def test_to_dict_json_serializable(self):
        r = self._make_report()
        serialized = json.dumps(r.to_dict())
        assert len(serialized) > 0

    def test_to_dict_agree_rate_value(self):
        r = self._make_report(same=3, differ=2, n=5)
        assert abs(r.to_dict()["agree_rate"] - 0.6) < 1e-9

    def test_seed_stored(self):
        r = self._make_report()
        assert r.to_dict()["seed"] == 42


# ---------------------------------------------------------------------------
# TestCompareSystems
# ---------------------------------------------------------------------------

class TestCompareSystems:
    def test_returns_comparison_report(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=5, seed=1)
        assert isinstance(report, ComparisonReport)

    def test_system_names_set(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=3, seed=1)
        assert len(report.system_a) > 0
        assert len(report.system_b) > 0

    def test_same_plus_differ_equals_n_deals(self, precision_doc, sayc_doc):
        n = 10
        report = compare_systems(precision_doc, sayc_doc, n_deals=n, seed=2)
        assert report.same_count + report.differ_count == n

    def test_n_deals_stored(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=7, seed=3)
        assert report.n_deals == 7

    def test_diff_cases_length_equals_differ_count(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=10, seed=5)
        assert len(report.diff_cases) == report.differ_count

    def test_passed_out_counts_non_negative(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=5, seed=6)
        assert report.passed_out_a >= 0
        assert report.passed_out_b >= 0

    def test_seed_reproducible(self, precision_doc, sayc_doc):
        r1 = compare_systems(precision_doc, sayc_doc, n_deals=5, seed=42)
        r2 = compare_systems(precision_doc, sayc_doc, n_deals=5, seed=42)
        assert r1.same_count == r2.same_count
        assert r1.differ_count == r2.differ_count

    def test_different_seeds_may_differ(self, precision_doc, sayc_doc):
        r1 = compare_systems(precision_doc, sayc_doc, n_deals=20, seed=1)
        r2 = compare_systems(precision_doc, sayc_doc, n_deals=20, seed=999)
        # With different random deals, counts will almost certainly differ
        # (not guaranteed, but true in practice for 20 deals)
        assert r1.n_deals == r2.n_deals  # at least n_deals is consistent

    def test_n_deals_zero(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=0, seed=1)
        assert report.same_count == 0
        assert report.differ_count == 0
        assert report.n_deals == 0
        assert report.diff_cases == []

    def test_diff_cases_have_correct_fields(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=10, seed=7)
        for dc in report.diff_cases:
            assert isinstance(dc.deal, Deal)
            assert isinstance(dc.auction_a, list)
            assert isinstance(dc.auction_b, list)
            assert dc.contract_a != dc.contract_b  # Must be different

    def test_zh_tw_locale_system_names(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=3, seed=1, locale="zh-TW")
        t = report.summary_text("zh-TW")
        assert "制度比較" in t

    def test_precision_vs_two_over_one_no_crash(self, precision_doc, two_over_one_doc):
        report = compare_systems(precision_doc, two_over_one_doc, n_deals=5, seed=42)
        assert isinstance(report, ComparisonReport)

    def test_same_system_high_agree_rate(self, precision_doc):
        report = compare_systems(precision_doc, precision_doc, n_deals=10, seed=42)
        # Same system should always produce identical results
        assert report.agree_rate == 1.0

    def test_to_dict_json_serializable(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=5, seed=42)
        d = report.to_dict()
        serialized = json.dumps(d, ensure_ascii=False)
        assert len(serialized) > 0

    def test_seed_stored_in_report(self, precision_doc, sayc_doc):
        report = compare_systems(precision_doc, sayc_doc, n_deals=3, seed=99)
        assert report.seed == 99
