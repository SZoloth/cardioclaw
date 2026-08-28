from datetime import UTC, datetime

import pytest

from cardioclaw.audio import (
    build_overview_script,
    build_paper_script,
    content_addressed_filename,
    episode_guid,
    make_episode,
)
from cardioclaw.models import (
    Candidate,
    EpisodeKind,
    EvidenceType,
    SourceKind,
    SourceScope,
    SummaryFinding,
    Topic,
)


def candidate(scope: SourceScope = SourceScope.ABSTRACT_ONLY) -> Candidate:
    return Candidate(
        candidate_id="pmid-123",
        title="Cardiac PET perfusion trial",
        abstract="A sufficiently detailed abstract with reported results and limitations.",
        full_text="Full methods and results." if scope == SourceScope.FULL_TEXT else None,
        source_kind=SourceKind.PUBMED,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        published_at=datetime(2026, 8, 28, tzinfo=UTC),
        topic=Topic.NUCLEAR_CARDIOLOGY,
        evidence_type=EvidenceType.RANDOMIZED_TRIAL,
        source_scope=scope,
        pmid="123",
        journal="Test Journal",
    )


def finding(scope: SourceScope = SourceScope.ABSTRACT_ONLY) -> SummaryFinding:
    return SummaryFinding(
        candidate_id="pmid-123",
        headline="Cardiac PET trial reported a clinically important perfusion result.",
        why_it_matters="The study addresses a core nuclear cardiology question.",
        spoken_summary=(
            "The study evaluated cardiac PET perfusion in a defined population. "
            "The source reports the design, population, principal result, and interpretation "
            "without adding information outside the supplied evidence boundary."
        ),
        limitations="The available source does not report every methodological detail.",
        source_scope=scope,
    )


def test_overview_script_announces_episode_count_and_headlines() -> None:
    script = build_overview_script(
        (finding(),),
        [candidate()],
        briefing_type="weekly",
        period_label="August 21 through August 28, 2026",
    )

    assert "1 paper episodes" in script
    assert "1 focused on nuclear cardiology" in script
    assert finding().headline in script
    assert "separate episodes" in script


@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        (SourceScope.FULL_TEXT, "accessible full text"),
        (SourceScope.ABSTRACT_ONLY, "Only the abstract was available"),
        (SourceScope.RSS_SNIPPET, "Only a journal or society feed snippet"),
    ],
)
def test_paper_script_states_source_scope(scope: SourceScope, expected: str) -> None:
    script = build_paper_script(finding(scope), candidate(scope), index=2, total=5)

    assert script.startswith("Paper 2 of 5")
    assert expected in script
    assert "Test Journal · 2026 · PMID 123" in script
    assert "Say next episode" in script


def test_content_addressed_names_and_guids_are_stable() -> None:
    first = content_addressed_filename("Paper One", "same script")
    second = content_addressed_filename("Paper One", "same script")
    changed = content_addressed_filename("Paper One", "different script")

    assert first == second
    assert first != changed
    assert first.endswith(".mp3")
    assert episode_guid("2026-08-21_2026-08-28", "pmid-123") == episode_guid(
        "2026-08-21_2026-08-28", "pmid-123"
    )


def test_make_episode_preserves_metadata() -> None:
    episode = make_episode(
        episode_id="week:paper",
        guid="urn:cardioclaw:test",
        kind=EpisodeKind.PAPER,
        title="01 · Test",
        description="Description",
        script="Spoken script",
        filename="paper.mp3",
        size=100,
        duration=60,
        published_at=datetime(2026, 8, 28, tzinfo=UTC),
        track_number=2,
        transcript_filename="paper.html",
        source_candidate_id="pmid-123",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        source_scope=SourceScope.ABSTRACT_ONLY,
    )

    assert episode.kind == EpisodeKind.PAPER
    assert episode.track_number == 2
    assert episode.source_scope == SourceScope.ABSTRACT_ONLY
