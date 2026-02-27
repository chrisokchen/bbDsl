"""Common types: enums, I18nString, Range, Author, Completeness."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Union

from pydantic import BaseModel, model_validator


class ForcingLevel(str, Enum):
    SIGNOFF = "signoff"
    NONE = "none"
    INVITATIONAL = "invitational"
    ONE_ROUND = "one_round"
    GAME = "game"
    SLAM = "slam"


class Seat(str, Enum):
    FIRST = "1st"
    SECOND = "2nd"
    THIRD = "3rd"
    FOURTH = "4th"
    ANY = "any"


class Vulnerability(str, Enum):
    NONE = "none"
    US = "us"
    THEM = "them"
    BOTH = "both"
    ANY = "any"


class CompletenessStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    DRAFT = "draft"
    TODO = "todo"


class BidType(str, Enum):
    PASS = "pass"
    SIMPLE_OVERCALL = "simple_overcall"
    JUMP_OVERCALL = "jump_overcall"
    PREEMPT = "preempt"
    CUE_BID = "cue_bid"
    NT_OVERCALL = "nt_overcall"
    TAKEOUT_DOUBLE = "takeout_double"
    PENALTY_DOUBLE = "penalty_double"
    ARTIFICIAL = "artificial"
    RAISE = "raise"
    NEW_SUIT = "new_suit"
    REDOUBLE = "redouble"


# I18nString: plain string or {locale: text} dict
I18nString = Annotated[Union[str, dict[str, str]], ...]


class Range(BaseModel):
    """Numeric range constraint."""

    min: int | None = None
    max: int | None = None
    exactly: int | None = None

    @model_validator(mode="after")
    def check_consistency(self) -> Range:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"min ({self.min}) must be <= max ({self.max})")
        if self.exactly is not None and (self.min is not None or self.max is not None):
            raise ValueError("'exactly' cannot be combined with 'min'/'max'")
        return self


class Author(BaseModel):
    """Author metadata."""

    name: str
    contact: str | None = None
    role: str | None = None


class Completeness(BaseModel):
    """Tracks which sections of a bidding system are defined."""

    openings: CompletenessStatus | None = None
    responses_to_1c: CompletenessStatus | None = None
    responses_to_1nt: CompletenessStatus | None = None
    defensive: CompletenessStatus | None = None
    competitive: CompletenessStatus | None = None
    slam_bidding: CompletenessStatus | None = None

    model_config = {"extra": "allow"}
