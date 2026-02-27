"""System-level models: Definitions, SystemMetadata, BBDSLDocument."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .bid import BidNode
from .common import Author, Completeness, I18nString, Range
from .context import Context, OpponentPattern
from .convention import Convention


class StrengthMethodDef(BaseModel):
    """Strength evaluation method definition."""

    description: I18nString | None = None
    range: list[int] | None = None  # [min, max]


class PatternDef(BaseModel):
    """Shape pattern definition."""

    description: I18nString | None = None
    shapes: list[str] | None = None  # generic: ["4-3-3-3", "4-4-3-2"]
    shapes_exact: list[str] | None = None  # exact: ["4=4=1=4"]
    constraints: dict | None = None


class SuitQualityDef(BaseModel):
    """Suit quality definition."""

    description: I18nString | None = None
    top3_honors: Range | None = None
    top5_honors: Range | None = None
    min_length: int | None = None


class Definitions(BaseModel):
    """Global definitions block."""

    strength_methods: dict[str, StrengthMethodDef] | None = None
    patterns: dict[str, PatternDef] | None = None
    suit_qualities: dict[str, SuitQualityDef] | None = None
    suit_groups: dict[str, list[str]] | None = None
    dealer_functions: dict | None = None
    bid_semantics: dict | None = None

    model_config = {"extra": "allow"}


class SystemMetadata(BaseModel):
    """System metadata."""

    name: I18nString
    version: str | None = None
    authors: list[Author] | None = None
    description: I18nString | None = None
    base: str | None = None
    locale: str | None = None
    license: str | None = None
    completeness: Completeness | None = None


class DefensiveEntry(BaseModel):
    """Defensive bidding entry."""

    when_opponent_opens: str | OpponentPattern | None = None
    actions: list[BidNode] | dict | None = None
    convention_ref: str | None = None

    model_config = {"extra": "allow"}


class DefenseToEntry(BaseModel):
    """Defense against a specific opponent system."""

    opponent_system: str
    description: I18nString | None = None
    when_opponent_opens: dict | None = None
    actions: list[BidNode] | None = None
    convention_ref: str | None = None


class ValidationConfig(BaseModel):
    """Validation configuration."""

    rules: list[dict] | None = None

    model_config = {"extra": "allow"}


class ExportConfig(BaseModel):
    """Export configuration."""

    bboalert: dict | None = None
    bml: dict | None = None
    convention_card: dict | None = None
    pbn: dict | None = None
    ai_knowledge_base: dict | None = None

    model_config = {"extra": "allow"}


class ImportConfig(BaseModel):
    """Import configuration."""

    bml: dict | None = None
    bboalert: dict | None = None

    model_config = {"extra": "allow"}


class BBDSLDocument(BaseModel):
    """Top-level BBDSL document."""

    bbdsl: str = "0.3"
    system: SystemMetadata
    definitions: Definitions | None = None
    contexts: dict[str, Context] | None = None
    conventions: dict[str, Convention] | None = None
    openings: list[BidNode]
    defensive: list[DefensiveEntry] | None = None
    defense_to: list[DefenseToEntry] | None = None
    selection_rules: dict | None = None
    validation: ValidationConfig | None = None
    export: ExportConfig | None = None
    import_: ImportConfig | None = Field(None, alias="import")

    model_config = {"populate_by_name": True}
