"""Bid models: HandConstraint, BidMeaning, ForeachSuit, BidNode."""

from __future__ import annotations

from typing import Any, Literal, Union

from pydantic import BaseModel, Field

from .common import ForcingLevel, I18nString, Range


class HandConstraint(BaseModel):
    """Hand constraint — core schema, clean of import transition fields (ADR-4)."""

    # Strength
    hcp: Range | None = None
    controls: Range | None = None
    losing_tricks: Range | None = None
    total_points: Range | None = None
    # Suit lengths
    clubs: Range | None = None
    diamonds: Range | None = None
    hearts: Range | None = None
    spades: Range | None = None
    bid_suit: Range | None = None
    longest_suit: Range | None = None
    second_suit: Range | None = None
    # Shape
    shape: Union[str, dict] | None = None  # "any" | {"ref": "balanced"}
    # Suit quality
    suit_quality: dict | None = None
    # Special
    four_card_major: bool | None = None
    support_for_partner: Range | None = None
    stopper_in: str | None = None
    specific_cards: list[str] | None = None  # ["AS", "KH"]
    # Nested conditions
    conditions: list[dict] | None = None

    model_config = {"extra": "allow"}


class BidMeaning(BaseModel):
    """Meaning/interpretation of a bid."""

    description: I18nString | None = None
    hand: HandConstraint | None = None
    artificial: bool = False
    alertable: bool = False
    preemptive: bool = False
    forcing: ForcingLevel | None = None
    transfer_to: str | None = None
    notes: I18nString | None = None


class ForeachSuit(BaseModel):
    """foreach_suit expansion directive."""

    variable: str
    over: Literal["majors", "minors", "reds", "blacks", "all"]


class BidNode(BaseModel):
    """Node in the bidding tree (recursive)."""

    bid: str | None = None
    id: str | None = None
    by: Literal["opener", "responder", "overcaller", "advancer"] | None = None
    ref: str | None = None
    foreach_suit: ForeachSuit | None = None
    meaning: BidMeaning | None = None
    priority: int | None = Field(None, ge=0, le=1000)
    context_overrides: list[dict[str, Any]] | None = None
    conventions_applied: list[Union[str, dict]] | None = None
    responses: list[BidNode] | None = None
    continuations: list[BidNode] | None = None
    when: str | None = None

    model_config = {"extra": "allow"}
