"""BBDSL System Comparator.

Compares two bidding systems by simulating the same deals with both and
reporting the differences in final contracts.

Data structures:
  DiffCase         — one deal where the two systems disagree
  ComparisonReport — aggregated statistics and all differing cases

Public API:
  compare_systems(doc_a, doc_b, n_deals, seed, locale, dealer) -> ComparisonReport

Example::

    from bbdsl.core.loader import load_document
    from bbdsl.core.comparator import compare_systems

    precision = load_document("examples/precision.bbdsl.yaml")
    sayc      = load_document("examples/sayc.bbdsl.yaml")
    report    = compare_systems(precision, sayc, n_deals=50, seed=42)
    print(report.summary_text())
    print(f"Agreement rate: {report.agree_rate:.1%}")
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from bbdsl.core.sim_engine import (
    AuctionStep,
    Deal,
    generate_deal,
    simulate_deal,
)
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DiffCase:
    """One deal where the two systems reach different final contracts."""

    deal_number: int
    deal: Deal
    auction_a: list[AuctionStep]
    auction_b: list[AuctionStep]
    contract_a: str | None   # e.g. "3NT by North"
    contract_b: str | None

    def to_dict(self) -> dict:
        return {
            "deal_number": self.deal_number,
            "deal": self.deal.to_dict(),
            "auction_a": [s.to_dict() for s in self.auction_a],
            "auction_b": [s.to_dict() for s in self.auction_b],
            "contract_a": self.contract_a,
            "contract_b": self.contract_b,
        }


@dataclass
class ComparisonReport:
    """Aggregated result of comparing two bidding systems over multiple deals."""

    system_a: str
    system_b: str
    n_deals: int
    same_count: int
    differ_count: int
    passed_out_a: int
    passed_out_b: int
    diff_cases: list[DiffCase] = field(default_factory=list)
    seed: int | None = None

    @property
    def agree_rate(self) -> float:
        """Fraction of deals where both systems reach the same contract."""
        return self.same_count / self.n_deals if self.n_deals > 0 else 0.0

    def summary_text(self, locale: str = "en") -> str:
        """Return a human-readable summary of the comparison."""
        if locale == "zh-TW":
            lines = [
                f"制度比較：{self.system_a} vs {self.system_b}",
                f"模擬副數：{self.n_deals}",
                f"相同合約：{self.same_count} ({self.agree_rate:.1%})",
                f"不同合約：{self.differ_count}",
                f"{self.system_a} 全過：{self.passed_out_a}",
                f"{self.system_b} 全過：{self.passed_out_b}",
            ]
        else:
            lines = [
                f"System Comparison: {self.system_a} vs {self.system_b}",
                f"Deals simulated: {self.n_deals}",
                f"Same contract: {self.same_count} ({self.agree_rate:.1%})",
                f"Different contracts: {self.differ_count}",
                f"{self.system_a} passed out: {self.passed_out_a}",
                f"{self.system_b} passed out: {self.passed_out_b}",
            ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "system_a": self.system_a,
            "system_b": self.system_b,
            "n_deals": self.n_deals,
            "same_count": self.same_count,
            "differ_count": self.differ_count,
            "passed_out_a": self.passed_out_a,
            "passed_out_b": self.passed_out_b,
            "agree_rate": self.agree_rate,
            "seed": self.seed,
            "diff_cases": [c.to_dict() for c in self.diff_cases],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _system_name(doc: BBDSLDocument, locale: str = "en") -> str:
    name = doc.system.name
    if isinstance(name, dict):
        return name.get(locale) or name.get("en") or next(iter(name.values()), "System")
    return str(name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_systems(
    doc_a: BBDSLDocument,
    doc_b: BBDSLDocument,
    n_deals: int = 50,
    seed: int | None = None,
    locale: str = "en",
    dealer: str = "N",
) -> ComparisonReport:
    """Compare two bidding systems by simulating the same deals with both.

    For each deal, both systems process the identical hands.  Deals where
    they reach different final contracts are recorded as :class:`DiffCase`
    entries.

    Args:
        doc_a: First BBDSL document (system A).
        doc_b: Second BBDSL document (system B).
        n_deals: Number of deals to simulate.
        seed: Base random seed.  Deal *i* uses ``seed + i`` if *seed* given.
        locale: Language for system name resolution.
        dealer: Starting dealer seat.

    Returns:
        A :class:`ComparisonReport` with statistics and all differing cases.
    """
    name_a = _system_name(doc_a, locale)
    name_b = _system_name(doc_b, locale)

    same_count = 0
    differ_count = 0
    passed_out_a = 0
    passed_out_b = 0
    diff_cases: list[DiffCase] = []

    for i in range(n_deals):
        deal_seed = (seed + i) if seed is not None else None
        deal = generate_deal(seed=deal_seed)

        result_a = simulate_deal(
            doc_a, deal=deal, dealer=dealer, deal_number=i + 1, seed=deal_seed
        )
        result_b = simulate_deal(
            doc_b, deal=deal, dealer=dealer, deal_number=i + 1, seed=deal_seed
        )

        if result_a.passed_out:
            passed_out_a += 1
        if result_b.passed_out:
            passed_out_b += 1

        if result_a.final_contract == result_b.final_contract:
            same_count += 1
        else:
            differ_count += 1
            diff_cases.append(DiffCase(
                deal_number=i + 1,
                deal=deal,
                auction_a=result_a.auction,
                auction_b=result_b.auction,
                contract_a=result_a.final_contract,
                contract_b=result_b.final_contract,
            ))

    return ComparisonReport(
        system_a=name_a,
        system_b=name_b,
        n_deals=n_deals,
        same_count=same_count,
        differ_count=differ_count,
        passed_out_a=passed_out_a,
        passed_out_b=passed_out_b,
        diff_cases=diff_cases,
        seed=seed,
    )
