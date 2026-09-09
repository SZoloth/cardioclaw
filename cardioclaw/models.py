from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceKind(StrEnum):
    PUBMED = "pubmed"
    JOURNAL_RSS = "journal_rss"
    SOCIETY_NEWS = "society_news"


class Topic(StrEnum):
    NUCLEAR_CARDIOLOGY = "nuclear_cardiology"
    GENERAL_CARDIOLOGY = "general_cardiology"


class SourceScope(StrEnum):
    FULL_TEXT = "full_text"
    ABSTRACT_ONLY = "abstract_only"
    RSS_SNIPPET = "rss_snippet"


class EvidenceType(StrEnum):
    GUIDELINE = "guideline"
    RANDOMIZED_TRIAL = "randomized_trial"
    META_ANALYSIS = "meta_analysis"
    SYSTEMATIC_REVIEW = "systematic_review"
    OBSERVATIONAL = "observational"
    SOCIETY_ANNOUNCEMENT = "society_announcement"
    REGULATORY_NEWS = "regulatory_news"
    OTHER = "other"


class Candidate(StrictModel):
    candidate_id: str = Field(min_length=3)
    title: str = Field(min_length=3)
    abstract: str = ""
    full_text: str | None = None
    source_kind: SourceKind
    source_name: str
    source_url: str
    published_at: datetime | None = None
    topic: Topic
    evidence_type: EvidenceType = EvidenceType.OTHER
    source_scope: SourceScope
    pmid: str | None = None
    pmcid: str | None = None
    doi: str | None = None
    journal: str | None = None
    authors: tuple[str, ...] = ()
    selection_score: float = 0
    selection_reasons: tuple[str, ...] = ()

    @property
    def evidence_text(self) -> str:
        if self.full_text:
            return self.full_text
        return self.abstract

    @property
    def citation_label(self) -> str:
        parts = [self.journal or self.source_name]
        if self.published_at:
            parts.append(str(self.published_at.year))
        if self.pmid:
            parts.append(f"PMID {self.pmid}")
        return " · ".join(part for part in parts if part)


class SummaryFinding(StrictModel):
    candidate_id: str
    headline: str = Field(min_length=10, max_length=240)
    why_it_matters: str = Field(min_length=10, max_length=600)
    spoken_summary: str = Field(min_length=80, max_length=4500)
    limitations: str = Field(min_length=5, max_length=1000)
    source_scope: SourceScope
    pronunciation_notes: tuple[str, ...] = ()

    @field_validator("headline", "why_it_matters", "spoken_summary", "limitations")
    @classmethod
    def plain_text_only(cls, value: str) -> str:
        if any(marker in value for marker in ("```", "<script", "</script")):
            raise ValueError("unsafe or non-spoken markup is not allowed")
        return " ".join(value.split())


class EpisodeKind(StrEnum):
    OVERVIEW = "overview"
    PAPER = "paper"
    SYSTEM = "system"


class Episode(StrictModel):
    episode_id: str
    guid: str
    kind: EpisodeKind
    title: str
    description: str
    spoken_script: str
    audio_filename: str
    audio_size: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    published_at: datetime
    track_number: int = Field(ge=1)
    source_candidate_id: str | None = None
    source_url: str | None = None
    transcript_filename: str
    source_scope: SourceScope | None = None


class ReleaseManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    release_id: str
    generated_at: datetime
    period_start: date
    period_end: date
    briefing_type: Literal["daily", "weekly"]
    reviewed_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    nuclear_count: int = Field(ge=0)
    episodes: tuple[Episode, ...]
    candidates: tuple[Candidate, ...]


class SummaryEnvelope(StrictModel):
    findings: tuple[SummaryFinding, ...]
