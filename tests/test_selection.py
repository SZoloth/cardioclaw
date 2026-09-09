from datetime import UTC, datetime

from cardioclaw.config import Settings
from cardioclaw.models import (
    Candidate,
    EvidenceType,
    SourceKind,
    SourceScope,
    Topic,
)
from cardioclaw.selection import deduplicate, select_candidates


def candidate(
    identifier: str,
    *,
    topic: Topic,
    evidence_type: EvidenceType = EvidenceType.OTHER,
    source_kind: SourceKind = SourceKind.PUBMED,
    score_text: str = "Abstract with reported results.",
    pmid: str | None = None,
) -> Candidate:
    return Candidate(
        candidate_id=identifier,
        title=f"Candidate {identifier}",
        abstract=score_text,
        source_kind=source_kind,
        source_name="Test",
        source_url=f"https://example.test/{identifier}",
        published_at=datetime(2026, 8, 25, tzinfo=UTC),
        topic=topic,
        evidence_type=evidence_type,
        source_scope=SourceScope.ABSTRACT_ONLY,
        pmid=pmid,
    )


def test_selection_is_nuclear_first_and_does_not_pad_with_news() -> None:
    settings = Settings(
        _env_file=None,
        min_nuclear_findings=2,
        max_findings=3,
        min_selection_score=0,
    )
    candidates = [
        candidate("nuc-1", topic=Topic.NUCLEAR_CARDIOLOGY),
        candidate(
            "nuc-2",
            topic=Topic.NUCLEAR_CARDIOLOGY,
            evidence_type=EvidenceType.RANDOMIZED_TRIAL,
        ),
        candidate(
            "gen-1",
            topic=Topic.GENERAL_CARDIOLOGY,
            evidence_type=EvidenceType.GUIDELINE,
        ),
        candidate(
            "news",
            topic=Topic.NUCLEAR_CARDIOLOGY,
            source_kind=SourceKind.SOCIETY_NEWS,
        ),
    ]

    selected = select_candidates(candidates, settings)

    assert len(selected) == 3
    assert all(item.topic == Topic.NUCLEAR_CARDIOLOGY for item in selected[:2])
    assert selected[0].candidate_id == "nuc-2"


def test_dedupe_prefers_pubmed_for_same_pmid() -> None:
    primary = candidate(
        "pubmed",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        pmid="123",
    )
    duplicate = candidate(
        "rss",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        source_kind=SourceKind.JOURNAL_RSS,
        pmid="123",
    )

    result = deduplicate([duplicate, primary])

    assert len(result) == 1
    assert result[0].candidate_id == "pubmed"
