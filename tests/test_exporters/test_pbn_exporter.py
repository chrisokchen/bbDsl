"""Tests for bbdsl.exporters.pbn_exporter."""

import re

import pytest

from bbdsl.core.hand_generator import BridgeHand
from bbdsl.core.loader import load_document
from bbdsl.core.sim_engine import AuctionStep, Deal, SimulationResult, generate_deal
from bbdsl.exporters.pbn_exporter import (
    _auction_to_pbn,
    _build_note,
    _deal_to_pbn_deal,
    _hand_to_pbn,
    export_pbn,
    result_to_pbn_record,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


def _simple_deal() -> Deal:
    return generate_deal(seed=42)


def _simple_auction() -> list[AuctionStep]:
    return [
        AuctionStep("N", "1C", "opener", "1C: 16+ HCP"),
        AuctionStep("E", "Pass", "opponent", "Default E/W pass"),
        AuctionStep("S", "1D", "responder", "1D: negative"),
        AuctionStep("W", "Pass", "opponent", "Default E/W pass"),
        AuctionStep("N", "1NT", "opener", "1NT: 15-17, balanced"),
        AuctionStep("E", "Pass", "opponent", "Default E/W pass"),
        AuctionStep("S", "3NT", "responder", "3NT: game"),
        AuctionStep("W", "Pass", "opponent", "Default E/W pass"),
        AuctionStep("N", "Pass", "opener", "Default pass"),
        AuctionStep("E", "Pass", "opponent", "Default E/W pass"),
        AuctionStep("S", "Pass", "responder", "Default pass"),
    ]


# ---------------------------------------------------------------------------
# TestHandToPbn
# ---------------------------------------------------------------------------

class TestHandToPbn:
    def test_normal_hand_format(self):
        hand = BridgeHand(
            spades=["A", "K", "7", "3"],
            hearts=["A", "8", "6"],
            diamonds=["A", "Q", "7"],
            clubs=["K", "7", "3"],
            hcp=17,
        )
        result = _hand_to_pbn(hand)
        assert result == "AK73.A86.AQ7.K73"

    def test_void_suit_is_dash(self):
        hand = BridgeHand(
            spades=[],
            hearts=["A", "K", "Q", "J", "T"],
            diamonds=["A", "K", "Q", "J", "T"],
            clubs=["A", "K", "Q", "J", "T", "9", "8", "7"],
            hcp=20,
        )
        result = _hand_to_pbn(hand)
        assert result.startswith("-.")

    def test_four_sections_separated_by_dots(self):
        hand = _simple_deal().north
        result = _hand_to_pbn(hand)
        parts = result.split(".")
        assert len(parts) == 4

    def test_ten_represented_as_T(self):
        hand = BridgeHand(
            spades=["T"],
            hearts=["T"],
            diamonds=["T"],
            clubs=["T"],
            hcp=0,
        )
        result = _hand_to_pbn(hand)
        assert result == "T.T.T.T"

    def test_all_void_gives_four_dashes(self):
        hand = BridgeHand(spades=[], hearts=[], diamonds=[], clubs=[], hcp=0)
        result = _hand_to_pbn(hand)
        assert result == "-.-.-.-"

    def test_order_is_spades_hearts_diamonds_clubs(self):
        hand = BridgeHand(
            spades=["A"],
            hearts=["K"],
            diamonds=["Q"],
            clubs=["J"],
            hcp=10,
        )
        result = _hand_to_pbn(hand)
        parts = result.split(".")
        assert parts[0] == "A"   # spades
        assert parts[1] == "K"   # hearts
        assert parts[2] == "Q"   # diamonds
        assert parts[3] == "J"   # clubs


# ---------------------------------------------------------------------------
# TestDealToPbnDeal
# ---------------------------------------------------------------------------

class TestDealToPbnDeal:
    def test_starts_with_dealer_prefix(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="N")
        assert result.startswith("N:")

    def test_four_hands_separated_by_space(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="N")
        body = result[2:]  # strip "N:"
        hands = body.split(" ")
        assert len(hands) == 4

    def test_each_hand_has_four_suit_sections(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="N")
        body = result[2:]
        for hand_str in body.split(" "):
            assert len(hand_str.split(".")) == 4

    def test_dealer_e_changes_prefix(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="E")
        assert result.startswith("E:")

    def test_dealer_s_changes_prefix(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="S")
        assert result.startswith("S:")

    def test_different_dealers_give_different_hand_orders(self):
        deal = _simple_deal()
        r_n = _deal_to_pbn_deal(deal, dealer="N")
        r_e = _deal_to_pbn_deal(deal, dealer="E")
        # Same deal but different hand order
        assert r_n != r_e

    def test_all_cards_present(self):
        deal = _simple_deal()
        result = _deal_to_pbn_deal(deal, dealer="N")
        # Count non-dash characters (rank chars)
        ranks_in_output = sum(
            1 for c in result if c in "AKQJT98765432"
        )
        assert ranks_in_output == 52


# ---------------------------------------------------------------------------
# TestAuctionToPbn
# ---------------------------------------------------------------------------

class TestAuctionToPbn:
    def test_pass_only(self):
        auction = [
            AuctionStep("N", "Pass", "opener", ""),
            AuctionStep("E", "Pass", "opponent", ""),
            AuctionStep("S", "Pass", "responder", ""),
            AuctionStep("W", "Pass", "opponent", ""),
        ]
        result = _auction_to_pbn(auction)
        assert "Pass Pass Pass Pass" in result

    def test_bids_included(self):
        auction = _simple_auction()
        result = _auction_to_pbn(auction)
        assert "1C" in result
        assert "1D" in result
        assert "1NT" in result
        assert "3NT" in result

    def test_four_per_line(self):
        # With 8 calls we should have 2 lines
        auction = [AuctionStep("N", "Pass", "opener", "")] * 8
        result = _auction_to_pbn(auction)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            assert len(line.split()) == 4

    def test_returns_string(self):
        assert isinstance(_auction_to_pbn([]), str)

    def test_empty_auction(self):
        result = _auction_to_pbn([])
        assert result == ""


# ---------------------------------------------------------------------------
# TestBuildNote
# ---------------------------------------------------------------------------

class TestBuildNote:
    def test_contains_system_name(self):
        note = _build_note(_simple_auction(), "Precision Club")
        assert "Precision Club" in note

    def test_starts_with_bbdsl_prefix(self):
        note = _build_note(_simple_auction(), "SAYC")
        assert note.startswith("BBDSL:")

    def test_contains_ns_bids(self):
        note = _build_note(_simple_auction(), "Precision Club")
        assert "N:1C" in note
        assert "S:1D" in note

    def test_passed_out_note(self):
        auction = [
            AuctionStep("N", "Pass", "opener", ""),
            AuctionStep("E", "Pass", "opponent", ""),
            AuctionStep("S", "Pass", "responder", ""),
            AuctionStep("W", "Pass", "opponent", ""),
        ]
        note = _build_note(auction, "System")
        assert "passed out" in note

    def test_ew_bids_not_in_note(self):
        auction = [
            AuctionStep("N", "1C", "opener", "1C: 16+ HCP"),
            AuctionStep("E", "2H", "opponent", "2H: overcall"),
            AuctionStep("S", "Pass", "responder", "No match → Pass"),
        ]
        note = _build_note(auction, "System")
        # E:2H should NOT appear
        assert "E:2H" not in note


# ---------------------------------------------------------------------------
# TestResultToPbnRecord
# ---------------------------------------------------------------------------

class TestResultToPbnRecord:
    def _make_result(self) -> SimulationResult:
        deal = _simple_deal()
        return SimulationResult(
            deal_number=1,
            deal=deal,
            auction=_simple_auction(),
            final_contract="3NT by North",
            passed_out=False,
        )

    def test_contains_deal_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert '[Deal "' in record

    def test_contains_auction_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert '[Auction "' in record

    def test_contains_note_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert '[Note "' in record

    def test_contains_dealer_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club", dealer="N")
        assert '[Dealer "N"]' in record

    def test_contains_contract_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert '[Contract "' in record

    def test_contract_value_extracted(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert "3NT" in record

    def test_passed_out_contract_is_pass(self):
        deal = _simple_deal()
        result = SimulationResult(
            deal_number=1, deal=deal,
            auction=[
                AuctionStep("N", "Pass", "opener", ""),
                AuctionStep("E", "Pass", "opponent", ""),
                AuctionStep("S", "Pass", "responder", ""),
                AuctionStep("W", "Pass", "opponent", ""),
            ],
            final_contract=None,
            passed_out=True,
        )
        record = result_to_pbn_record(result, "System")
        assert '[Contract "Pass"]' in record

    def test_vulnerable_tag(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club", vulnerable="NS")
        assert '[Vulnerable "NS"]' in record

    def test_board_number_in_record(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "System", record_number=3)
        assert '"3"' in record

    def test_note_contains_bbdsl(self):
        result = self._make_result()
        record = result_to_pbn_record(result, "Precision Club")
        assert "BBDSL" in record


# ---------------------------------------------------------------------------
# TestExportPbn
# ---------------------------------------------------------------------------

class TestExportPbn:
    def test_returns_string(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42)
        assert isinstance(result, str)

    def test_starts_with_pbn_header(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42)
        assert result.startswith("% PBN 2.1")

    def test_contains_generated_by_bbdsl(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42)
        assert "Generated by BBDSL" in result

    def test_n_deals_records_present(self, precision_doc):
        n = 3
        result = export_pbn(precision_doc, n_deals=n, seed=42)
        # Each record starts with [Event "..."]
        event_count = result.count('[Event "BBDSL Simulation"]')
        assert event_count == n

    def test_contains_deal_tags(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42)
        assert result.count('[Deal "') == 2

    def test_seed_reproducible(self, precision_doc):
        r1 = export_pbn(precision_doc, n_deals=3, seed=42)
        r2 = export_pbn(precision_doc, n_deals=3, seed=42)
        assert r1 == r2

    def test_different_seeds_differ(self, precision_doc):
        r1 = export_pbn(precision_doc, n_deals=3, seed=1)
        r2 = export_pbn(precision_doc, n_deals=3, seed=999)
        assert r1 != r2

    def test_writes_file(self, precision_doc, tmp_path):
        out = tmp_path / "test.pbn"
        export_pbn(precision_doc, output_path=out, n_deals=2, seed=42)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "% PBN 2.1" in content

    def test_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "nested" / "out.pbn"
        export_pbn(precision_doc, output_path=out, n_deals=1, seed=1)
        assert out.exists()

    def test_file_content_matches_return(self, precision_doc, tmp_path):
        out = tmp_path / "check.pbn"
        pbn_text = export_pbn(precision_doc, output_path=out, n_deals=2, seed=42)
        assert out.read_text(encoding="utf-8") == pbn_text

    def test_sayc_no_crash(self, sayc_doc):
        result = export_pbn(sayc_doc, n_deals=3, seed=1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_zero_deals_header_only(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=0, seed=1)
        assert "% PBN 2.1" in result
        assert result.count('[Event "BBDSL Simulation"]') == 0

    def test_note_contains_system_name(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42)
        assert "Precision Club" in result

    def test_dealer_option(self, precision_doc):
        result = export_pbn(precision_doc, n_deals=2, seed=42, dealer="S")
        assert '[Dealer "S"]' in result
