from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cardioclaw.config import Settings
from cardioclaw.models import (
    Candidate,
    EvidenceType,
    SourceKind,
    SourceScope,
    SummaryFinding,
    Topic,
)
from cardioclaw.pipeline import CardiologyClawPipeline, resolve_period


class FakeSummarizer:
    def summarize(self, candidates):
        return tuple(
            SummaryFinding(
                candidate_id=candidate.candidate_id,
                headline=f"{candidate.title} reported a clinically relevant result.",
                why_it_matters="It is directly relevant to nuclear cardiology.",
                spoken_summary=(
                    "The abstract describes the study question, population, methods, "
                    "reported result, and interpretation without adding unsupported facts."
                ),
                limitations="Only the abstract was available.",
                source_scope=candidate.source_scope,
            )
            for candidate in candidates
        )


class FakeRenderer:
    def render(self, text, destination, *, title, track_number):
        destination.write_bytes(b"ID3fake")
        return destination.stat().st_size, 60


class FailingRenderer:
    def render(self, text, destination, *, title, track_number):
        raise RuntimeError("synthetic TTS failure")


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        anthropic_api_key="test",
        openai_api_key="test",
        ncbi_email="operator@example.test",
        feed_token="test-token",
        public_base_url="https://audio.example.test",
        full_text_enabled=False,
        min_nuclear_findings=1,
        max_findings=2,
        min_selection_score=0,
    )


def _candidates() -> list[Candidate]:
    return [
        Candidate(
            candidate_id=f"pmid-{index}",
            title=f"Nuclear paper {index}",
            abstract="Abstract with a clinically relevant result.",
            source_kind=SourceKind.PUBMED,
            source_name="PubMed",
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{index}/",
            published_at=datetime(2026, 8, 27, tzinfo=UTC),
            topic=Topic.NUCLEAR_CARDIOLOGY,
            evidence_type=EvidenceType.OTHER,
            source_scope=SourceScope.ABSTRACT_ONLY,
            pmid=str(index),
        )
        for index in (1, 2)
    ]


def test_weekly_period_is_seven_inclusive_calendar_dates() -> None:
    period = resolve_period(datetime(2026, 8, 28, 12, tzinfo=UTC), briefing_type="weekly")

    assert period.start == date(2026, 8, 22)
    assert period.end == date(2026, 8, 28)


def test_daily_period_defaults_to_previous_calendar_date() -> None:
    period = resolve_period(datetime(2026, 8, 28, 12, tzinfo=UTC), briefing_type="daily")

    assert period.start == date(2026, 8, 27)
    assert period.end == date(2026, 8, 27)


def test_explicit_lookback_is_inclusive() -> None:
    period = resolve_period(
        datetime(2026, 8, 28, 12, tzinfo=UTC),
        briefing_type="weekly",
        lookback_days=3,
    )

    assert period.start == date(2026, 8, 26)
    assert period.end == date(2026, 8, 28)


def test_pipeline_publishes_overview_plus_one_episode_per_paper(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    manifest = CardiologyClawPipeline(
        settings,
        summarizer=FakeSummarizer(),
        renderer=FakeRenderer(),
    ).run(
        now=datetime(2026, 8, 28, tzinfo=UTC),
        supplied_candidates=_candidates(),
    )

    assert len(manifest.episodes) == 3
    assert manifest.episodes[0].kind == "overview"
    assert [episode.track_number for episode in manifest.episodes] == [1, 2, 3]
    assert (settings.releases_dir / manifest.release_id / "feed.xml").is_file()
    assert settings.current_pointer.is_file()
    assert not any(path.name.startswith(".staging-") for path in settings.releases_dir.iterdir())


def test_failed_render_discards_staging_and_leaves_no_pointer(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    with pytest.raises(RuntimeError, match="synthetic TTS failure"):
        CardiologyClawPipeline(
            settings,
            summarizer=FakeSummarizer(),
            renderer=FailingRenderer(),
        ).run(
            now=datetime(2026, 8, 28, tzinfo=UTC),
            supplied_candidates=_candidates(),
        )

    assert not settings.current_pointer.exists()
    assert list(settings.releases_dir.iterdir()) == []
