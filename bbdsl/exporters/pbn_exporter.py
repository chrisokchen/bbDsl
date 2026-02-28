"""BBDSL → PBN (Portable Bridge Notation) exporter.

Converts BBDSL simulation results to PBN format for import into bridge
analysis software (e.g. Deep Finesse, HandViewer, BridgeComposer).

Each PBN record contains:
  [Deal]    — four hands in standard PBN encoding (S.H.D.C per hand)
  [Auction] — the simulated bidding sequence (4 calls per line)
  [Note]    — embedded BBDSL semantics (system name + bid reasoning)

PBN format reference: https://www.tistis.nl/pbn/

Example::

    from bbdsl.core.loader import load_document
    from bbdsl.exporters.pbn_exporter import export_pbn

    doc = load_document("examples/precision.bbdsl.yaml")
    pbn_text = export_pbn(doc, n_deals=5, seed=42)
    print(pbn_text)
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any

from bbdsl.core.hand_generator import BridgeHand
from bbdsl.core.sim_engine import AuctionStep, Deal, SimulationResult, simulate
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SEAT_ORDER = ["N", "E", "S", "W"]


def _hand_to_pbn(hand: BridgeHand) -> str:
    """Convert a BridgeHand to PBN suit string ``"S.H.D.C"``.

    Each suit is written as rank characters in high-to-low order.
    A void suit is represented as ``"-"`` (PBN standard).
    """
    def _ranks(cards: list[str]) -> str:
        return "".join(cards) if cards else "-"

    return (
        f"{_ranks(hand.spades)}.{_ranks(hand.hearts)}"
        f".{_ranks(hand.diamonds)}.{_ranks(hand.clubs)}"
    )


def _deal_to_pbn_deal(deal: Deal, dealer: str = "N") -> str:
    """Convert a Deal to PBN [Deal] value.

    Format: ``"<dealer>:<first_hand> <second_hand> <third_hand> <fourth_hand>"``
    Hands are listed clockwise starting from *dealer*.
    """
    seat_hands: dict[str, BridgeHand] = {
        "N": deal.north,
        "E": deal.east,
        "S": deal.south,
        "W": deal.west,
    }
    dealer_idx = _SEAT_ORDER.index(dealer)
    hands = [
        _hand_to_pbn(seat_hands[_SEAT_ORDER[(dealer_idx + i) % 4]])
        for i in range(4)
    ]
    return f"{dealer}:{' '.join(hands)}"


def _auction_to_pbn(auction: list[AuctionStep], dealer: str = "N") -> str:
    """Convert auction steps to PBN auction call string.

    Calls are grouped 4-per-line (N / E / S / W order).
    """
    calls = [step.bid for step in auction]
    rows: list[str] = []
    for i in range(0, len(calls), 4):
        rows.append(" ".join(calls[i : i + 4]))
    return "\n".join(rows)


def _build_note(auction: list[AuctionStep], system_name: str) -> str:
    """Build the BBDSL semantic string for the PBN [Note] tag.

    Only N/S (non-Pass) bids are included; E/W default-pass steps are skipped.
    """
    ns_bids = [s for s in auction if s.seat in ("N", "S") and s.bid != "Pass"]
    if not ns_bids:
        return f"BBDSL: {system_name} | (passed out)"

    bid_parts = []
    for s in ns_bids:
        # Extract concise reasoning (strip bid label prefix if present)
        reason = s.reasoning
        if ":" in reason:
            reason = reason.split(":", 1)[1].strip()
        bid_parts.append(f"{s.seat}:{s.bid}({reason})")

    return f"BBDSL: {system_name} | {' | '.join(bid_parts)}"


def result_to_pbn_record(
    result: SimulationResult,
    system_name: str,
    record_number: int = 1,
    dealer: str = "N",
    vulnerable: str = "None",
) -> str:
    """Generate one PBN record from a :class:`SimulationResult`.

    Args:
        result: The simulation result to convert.
        system_name: Bidding system name (used in [Note]).
        record_number: Board / record number.
        dealer: Dealer seat.
        vulnerable: Vulnerability string (``"None"``, ``"NS"``, ``"EW"``, ``"All"``).

    Returns:
        A single PBN record string.
    """
    deal_str    = _deal_to_pbn_deal(result.deal, dealer=dealer)
    auction_str = _auction_to_pbn(result.auction, dealer=dealer)
    note_str    = _build_note(result.auction, system_name)
    contract    = result.final_contract or "Pass"

    today = datetime.date.today().isoformat().replace("-", ".")

    lines = [
        f'[Event "BBDSL Simulation"]',
        f'[Site ""]',
        f'[Date "{today}"]',
        f'[Round "{record_number}"]',
        f'[Board "{record_number}"]',
        f'[West ""]',
        f'[North ""]',
        f'[East ""]',
        f'[South ""]',
        f'[Dealer "{dealer}"]',
        f'[Vulnerable "{vulnerable}"]',
        f'[Deal "{deal_str}"]',
        f'[Scoring ""]',
        f'[Contract "{contract}"]',
        f'[Result ""]',
        f'[Auction "{dealer}"]',
        auction_str,
        f'[Note "{note_str}"]',
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _system_name(doc: BBDSLDocument, locale: str = "en") -> str:
    name = doc.system.name
    if isinstance(name, dict):
        return name.get(locale) or name.get("en") or next(iter(name.values()), "System")
    return str(name)


def export_pbn(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    n_deals: int = 10,
    seed: int | None = None,
    dealer: str = "N",
    vulnerable: str = "None",
    locale: str = "en",
) -> str:
    """Simulate deals and export results as PBN (Portable Bridge Notation).

    Args:
        doc: The BBDSL document.
        output_path: If given, write PBN text to this file.
        n_deals: Number of deals to simulate.
        seed: Random seed for reproducibility.
        dealer: Starting dealer seat.
        vulnerable: Vulnerability for all boards.
        locale: Language for the system name.

    Returns:
        PBN text string (all records concatenated with blank lines).
    """
    system_name = _system_name(doc, locale)
    results = simulate(doc, n_deals=n_deals, seed=seed, dealer=dealer)

    header = "% PBN 2.1\n% Generated by BBDSL\n"
    records = [
        result_to_pbn_record(
            r,
            system_name=system_name,
            record_number=r.deal_number,
            dealer=dealer,
            vulnerable=vulnerable,
        )
        for r in results
    ]

    pbn_text = header + "\n\n".join(records) + "\n"

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(pbn_text, encoding="utf-8")

    return pbn_text
