"""Convention models: ConventionParameter, Convention."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, field_validator

from .bid import BidMeaning, BidNode, ForeachSuit, HandConstraint
from .common import I18nString

CONVENTION_ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}/[a-z][a-z0-9_-]{0,63}-v[0-9]+$")


class ConventionParameter(BaseModel):
    """Convention parameter definition."""

    type: Literal["bid", "boolean", "integer", "string", "suit"]
    default: Any = None
    description: I18nString | None = None


class ConventionTrigger(BaseModel):
    """What triggers a convention."""

    after: list[str] | None = None  # e.g. ["1NT"]
    bid: str | None = None  # e.g. "2C"


class Convention(BaseModel):
    """Convention module definition."""

    id: str
    name: I18nString
    version: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    description: I18nString | None = None
    parameters: dict[str, ConventionParameter] | None = None
    # Trigger
    trigger: ConventionTrigger | None = None
    # Relationships
    requires: list[str] | None = None
    conflicts_with: list[str] | None = None
    recommends: list[str] | None = None
    # Content
    foreach_suit: ForeachSuit | None = None
    responder_hand: HandConstraint | None = None
    responses: list[BidNode] | None = None
    bids: list[BidNode] | None = None
    meaning: BidMeaning | None = None

    @field_validator("id")
    @classmethod
    def validate_convention_id(cls, v: str) -> str:
        if not CONVENTION_ID_RE.match(v):
            raise ValueError(
                f"Convention ID '{v}' does not match required format: "
                "scope/name-vN (e.g. 'bbdsl/stayman-v1')"
            )
        return v

    model_config = {"extra": "allow"}
