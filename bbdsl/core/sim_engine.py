"""BBDSL Simulation Engine.

Generates random bridge deals and simulates complete bidding auctions using
a BBDSL bidding system document.

Data structures:
  Deal            — 4 bridge hands dealt from one 52-card deck
  AuctionStep     — one bid in the auction (seat, bid, by, reasoning)
  SimulationResult — complete result for one deal

Public API:
  generate_deal(seed)           → Deal
  simulate_deal(ns_doc, ...)    → SimulationResult
  simulate(ns_doc, n_deals, ...) → list[SimulationResult]

Example::

    from bbdsl.core.loader import load_document
    from bbdsl.core.sim_engine import simulate

    doc = load_document("examples/precision.bbdsl.yaml")
    results = simulate(doc, n_deals=5, seed=42)
    for r in results:
        print(f"Deal {r.deal_number}: {r.final_contract}")
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from bbdsl.core.hand_generator import (
    RANKS,
    SUITS,
    BridgeHand,
    _RANK_IDX,
    _calc_hcp,
    _check_controls,
    _check_hcp,
    _check_shape,
    _check_suit,
)
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Deal:
    """Four bridge hands dealt from one 52-card deck."""

    north: BridgeHand
    south: BridgeHand
    east: BridgeHand
    west: BridgeHand
    seed: int | None = None

    def to_dict(self) -> dict:
        return {
            "north": self.north.to_dict(),
            "south": self.south.to_dict(),
            "east": self.east.to_dict(),
            "west": self.west.to_dict(),
            "seed": self.seed,
        }


@dataclass
class AuctionStep:
    """One bid in the auction."""

    seat: str       # "N", "E", "S", "W"
    bid: str        # "Pass", "1C", "1NT", ...
    by: str         # "opener" | "responder" | "opponent"
    reasoning: str  # human-readable explanation

    def to_dict(self) -> dict:
        return {
            "seat": self.seat,
            "bid": self.bid,
            "by": self.by,
            "reasoning": self.reasoning,
        }


@dataclass
class SimulationResult:
    """Complete auction result for one deal."""

    deal_number: int
    deal: Deal
    auction: list[AuctionStep] = field(default_factory=list)
    final_contract: str | None = None  # "3NT by North" or None
    passed_out: bool = False

    def to_dict(self) -> dict:
        return {
            "deal_number": self.deal_number,
            "deal": self.deal.to_dict(),
            "auction": [s.to_dict() for s in self.auction],
            "final_contract": self.final_contract,
            "passed_out": self.passed_out,
        }


# ---------------------------------------------------------------------------
# Deal generation
# ---------------------------------------------------------------------------

def generate_deal(seed: int | None = None) -> Deal:
    """Generate a random complete bridge deal from one 52-card deck.

    Each card appears exactly once across the four hands.

    Args:
        seed: Random seed for reproducibility.

    Returns:
        A :class:`Deal` with four 13-card hands.
    """
    rng = random.Random(seed)

    # Build full 52-card deck as (rank, suit) pairs
    deck: list[tuple[str, str]] = [
        (rank, suit)
        for suit in SUITS
        for rank in RANKS
    ]
    rng.shuffle(deck)

    def _build_hand(cards: list[tuple[str, str]]) -> BridgeHand:
        by_suit: dict[str, list[str]] = {s: [] for s in SUITS}
        for rank, suit in cards:
            by_suit[suit].append(rank)
        # Sort each suit high-to-low
        for s in SUITS:
            by_suit[s].sort(key=lambda r: _RANK_IDX[r])
        hcp = _calc_hcp(by_suit)
        return BridgeHand(
            spades=by_suit["spades"],
            hearts=by_suit["hearts"],
            diamonds=by_suit["diamonds"],
            clubs=by_suit["clubs"],
            hcp=hcp,
        )

    return Deal(
        north=_build_hand(deck[0:13]),
        east=_build_hand(deck[13:26]),
        south=_build_hand(deck[26:39]),
        west=_build_hand(deck[39:52]),
        seed=seed,
    )


# ---------------------------------------------------------------------------
# Constraint matching
# ---------------------------------------------------------------------------

def _matches_constraint(hand: BridgeHand, constraint: Any) -> bool:
    """Check whether *hand* satisfies *constraint*.

    Args:
        hand: A :class:`BridgeHand` instance.
        constraint: A ``HandConstraint`` instance, or None.

    Returns:
        True if constraint is None (any hand matches) or if all fields pass.
    """
    if constraint is None:
        return True

    by_suit = {
        "spades": hand.spades,
        "hearts": hand.hearts,
        "diamonds": hand.diamonds,
        "clubs": hand.clubs,
    }

    if not _check_hcp(hand.hcp, constraint):
        return False
    if not _check_shape(by_suit, constraint):
        return False
    for suit in SUITS:
        r = getattr(constraint, suit, None)
        if not _check_suit(by_suit[suit], r):
            return False
    if not _check_controls(by_suit, constraint):
        return False
    return True


def _describe_constraint(constraint: Any) -> str:
    """Return a brief human-readable summary of *constraint*."""
    if constraint is None:
        return "no constraint"
    parts: list[str] = []

    hcp = getattr(constraint, "hcp", None)
    if hcp:
        if hcp.min is not None and hcp.max is not None:
            parts.append(f"{hcp.min}-{hcp.max} HCP")
        elif hcp.min is not None:
            parts.append(f"{hcp.min}+ HCP")
        elif hcp.max is not None:
            parts.append(f"≤{hcp.max} HCP")

    for suit, sym in (("spades", "S"), ("hearts", "H"), ("diamonds", "D"), ("clubs", "C")):
        r = getattr(constraint, suit, None)
        if r and r.min is not None:
            parts.append(f"{r.min}+ {sym}")

    shape = getattr(constraint, "shape", None)
    if shape and isinstance(shape, dict):
        ref = shape.get("ref", "")
        if ref:
            parts.append(ref)

    return ", ".join(parts) if parts else "any hand"


# ---------------------------------------------------------------------------
# Tree navigation
# ---------------------------------------------------------------------------

def _find_node_by_bid(nodes: list[Any], bid: str) -> Any | None:
    """Find the first BidNode with matching bid string."""
    for node in nodes:
        if getattr(node, "bid", None) == bid:
            return node
    return None


def _navigate_tree(doc: BBDSLDocument, ns_path: list[str]) -> Any | None:
    """Navigate the bidding tree by ns_path.

    Args:
        doc: The BBDSL document.
        ns_path: List of N/S non-Pass bids in order (e.g. ``["1C", "1D"]``).

    Returns:
        The BidNode for the last bid in *ns_path*, or None if path is empty
        or any bid is not found.

    Navigation alternates between responses and continuations:
      - ns_path[0]: found in ``doc.openings``
      - ns_path[1]: found in previous node's ``responses`` (search-depth 0, even)
      - ns_path[2]: found in previous node's ``continuations`` (search-depth 1, odd)
      - ns_path[3]: found in previous node's ``responses`` (search-depth 2, even)
      - ...
    """
    if not ns_path:
        return None

    current = _find_node_by_bid(doc.openings or [], ns_path[0])
    if current is None:
        return None

    # search_depth 0 (even) → responses, 1 (odd) → continuations, 2 → responses, ...
    for search_depth, bid in enumerate(ns_path[1:]):
        if search_depth % 2 == 0:
            candidates = getattr(current, "responses", None) or []
        else:
            candidates = getattr(current, "continuations", None) or []
        current = _find_node_by_bid(candidates, bid)
        if current is None:
            return None

    return current


def _get_candidates(current: Any | None, doc: BBDSLDocument) -> list[Any]:
    """Get BidNode candidates for the next N/S bid.

    Args:
        current: The current BidNode (from :func:`_navigate_tree`), or None
                 if about to open.
        doc: The BBDSL document.

    Returns:
        List of candidate BidNodes (responses + continuations, or openings).
    """
    if current is None:
        return doc.openings or []
    return (getattr(current, "responses", None) or []) + (
        getattr(current, "continuations", None) or []
    )


# ---------------------------------------------------------------------------
# Bid selection
# ---------------------------------------------------------------------------

def _select_bid(hand: BridgeHand, candidates: list[Any]) -> tuple[str, str]:
    """Select the first candidate bid whose constraint is satisfied by *hand*.

    Args:
        hand: The bridge hand to evaluate.
        candidates: Ordered list of BidNodes.

    Returns:
        ``(bid_string, reasoning_string)`` — ``("Pass", ...)`` if no match.
    """
    for node in candidates:
        bid = getattr(node, "bid", None)
        if not bid:
            continue
        meaning = getattr(node, "meaning", None)
        constraint = getattr(meaning, "hand", None) if meaning else None
        if _matches_constraint(hand, constraint):
            if constraint is None:
                reasoning = f"No constraint (any hand) → {bid}"
            else:
                desc = _describe_constraint(constraint)
                reasoning = f"{bid}: {desc}"
            return (bid, reasoning)

    return ("Pass", "No matching constraint → Pass")


# ---------------------------------------------------------------------------
# Auction termination helpers
# ---------------------------------------------------------------------------

def _final_contract(steps: list[AuctionStep]) -> tuple[str | None, bool]:
    """Determine the final contract from the completed auction.

    Returns:
        ``(contract_string, passed_out)`` where *contract_string* is e.g.
        ``"3NT by North"`` or ``None`` if all seats passed.
    """
    last_non_pass: AuctionStep | None = None
    for step in steps:
        if step.bid != "Pass":
            last_non_pass = step

    if last_non_pass is None:
        return (None, True)

    seat_full = {"N": "North", "E": "East", "S": "South", "W": "West"}
    return (f"{last_non_pass.bid} by {seat_full[last_non_pass.seat]}", False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SEAT_ORDER = ["N", "E", "S", "W"]
_SEAT_FULL = {"N": "North", "E": "East", "S": "South", "W": "West"}


def simulate_deal(
    ns_doc: BBDSLDocument,
    deal: Deal | None = None,
    ew_doc: BBDSLDocument | None = None,
    dealer: str = "N",
    deal_number: int = 1,
    seed: int | None = None,
) -> SimulationResult:
    """Run one complete bidding auction.

    Auction order: dealer → clockwise (N→E→S→W→N→...).
    E/W default to Pass unless *ew_doc* is provided.
    Ends after 3 consecutive Passes following any non-Pass bid, or 4 Passes
    at the start (passed out). Maximum 40 bids (safety limit).

    Args:
        ns_doc: BBDSL document for the N/S pair.
        deal: Pre-generated deal (randomly generated if None).
        ew_doc: Optional BBDSL document for the E/W pair.
        dealer: Starting seat ("N", "E", "S", or "W").
        deal_number: Sequence number used in the result.
        seed: Random seed used when generating the deal (ignored if *deal* given).

    Returns:
        A :class:`SimulationResult`.
    """
    if deal is None:
        deal = generate_deal(seed=seed)

    seat_hands: dict[str, BridgeHand] = {
        "N": deal.north,
        "E": deal.east,
        "S": deal.south,
        "W": deal.west,
    }

    # Assign opener/responder roles: whichever N/S seat bids first is opener
    dealer_idx = _SEAT_ORDER.index(dealer)
    ns_opener = "N"
    ns_responder = "S"
    for i in range(4):
        s = _SEAT_ORDER[(dealer_idx + i) % 4]
        if s in ("N", "S"):
            ns_opener = s
            ns_responder = "S" if ns_opener == "N" else "N"
            break

    auction: list[AuctionStep] = []
    ns_path: list[str] = []
    ew_path: list[str] = []
    consecutive_passes = 0
    any_non_pass = False

    for step_num in range(40):
        seat = _SEAT_ORDER[(dealer_idx + step_num) % 4]
        hand = seat_hands[seat]
        is_ns = seat in ("N", "S")

        if is_ns:
            current = _navigate_tree(ns_doc, ns_path)
            candidates = _get_candidates(current, ns_doc)
            bid, reasoning = _select_bid(hand, candidates)
            if bid != "Pass":
                ns_path.append(bid)
            by = "opener" if seat == ns_opener else "responder"
        else:
            if ew_doc is None:
                bid = "Pass"
                reasoning = "Default E/W pass"
            else:
                current = _navigate_tree(ew_doc, ew_path)
                candidates = _get_candidates(current, ew_doc)
                bid, reasoning = _select_bid(hand, candidates)
                if bid != "Pass":
                    ew_path.append(bid)
            by = "opponent"

        auction.append(AuctionStep(seat=seat, bid=bid, by=by, reasoning=reasoning))

        if bid == "Pass":
            consecutive_passes += 1
        else:
            consecutive_passes = 0
            any_non_pass = True

        # Termination conditions
        if any_non_pass and consecutive_passes >= 3:
            break
        if not any_non_pass and consecutive_passes >= 4:
            break

    final_contract, passed_out = _final_contract(auction)

    return SimulationResult(
        deal_number=deal_number,
        deal=deal,
        auction=auction,
        final_contract=final_contract,
        passed_out=passed_out,
    )


def simulate(
    ns_doc: BBDSLDocument,
    n_deals: int = 10,
    ew_doc: BBDSLDocument | None = None,
    dealer: str = "N",
    seed: int | None = None,
) -> list[SimulationResult]:
    """Run *n_deals* complete auctions with sequential seeds.

    Args:
        ns_doc: BBDSL document for the N/S pair.
        n_deals: Number of deals to simulate.
        ew_doc: Optional BBDSL document for E/W pair.
        dealer: Starting dealer seat.
        seed: Base random seed. Deal *i* uses ``seed + i`` if *seed* is given.

    Returns:
        List of :class:`SimulationResult` objects, one per deal.
    """
    results: list[SimulationResult] = []
    for i in range(n_deals):
        deal_seed = (seed + i) if seed is not None else None
        deal = generate_deal(seed=deal_seed)
        result = simulate_deal(
            ns_doc,
            deal=deal,
            ew_doc=ew_doc,
            dealer=dealer,
            deal_number=i + 1,
            seed=deal_seed,
        )
        results.append(result)
    return results
