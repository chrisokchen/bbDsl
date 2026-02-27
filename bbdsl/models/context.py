"""Context models: OpponentPattern, Context, ContextOverride."""

from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field

from .common import BidType, I18nString, Range, Seat, Vulnerability


class OpponentPattern(BaseModel):
    """Opponent action pattern — pure data, matching logic in core/opponent_matcher.py (ADR-5)."""

    # Simple forms
    simple: Literal["pass", "double", "any_action", "any_bid"] | None = None
    # Concrete bid
    bid: str | None = None
    bid_range: list[str] | None = None  # [from, to] e.g. ["2C", "3S"]
    # Level/suit filtering
    level: int | Range | list[int] | None = None
    suit: str | None = None  # C/D/H/S or major/minor
    bid_type: BidType | None = None
    # Composition
    any_of: list[OpponentPattern] | None = None
    all_of: list[OpponentPattern] | None = None
    not_: OpponentPattern | None = Field(None, alias="not")

    model_config = {"populate_by_name": True}


class Context(BaseModel):
    """Bidding context specification."""

    seat: Seat | list[Seat] | None = None
    vulnerability: Vulnerability | list[Vulnerability] | None = None
    opponent_action: Union[str, OpponentPattern] | None = None
    precondition: str | None = None
    description: I18nString | None = None


class ContextOverride(BaseModel):
    """Override meaning in a specific context."""

    context: Union[Context, dict] = ...  # dict for {"ref": "context_name"}
    meaning: dict | None = None  # BidMeaning as dict to avoid circular import
