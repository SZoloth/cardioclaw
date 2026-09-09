from datetime import UTC, datetime
from pathlib import Path

import pytest

from cardioclaw.config import Settings
from cardioclaw.models import (
    Candidate,
    Episode,
    EpisodeKind,
    EvidenceType,
    ReleaseManifest,
    SourceKind,
    SourceScope,
    Topic,
)
from cardioclaw.publisher import ReleasePublisher


def _manifest(
    *,
    release_id: str,
    guid: str,
    generated_at: datetime,
    filename: str,
) -> ReleaseManifest:
    episode = Episode(
        episode_id=guid,
        guid=guid,
        kind=EpisodeKind.OVERVIEW,
        title=release_id,
        description="Description",
        spoken_script="Transcript",
        audio_filename=filename,
        audio_size=4,
        duration_seconds=1,
        published_at=generated_at,
        track_number=1,
        transcript_filename=f"{release_id}.html",
    )
    candidate = Candidate(
        candidate_id="candidate-1",
        title="Candidate",
        abstract="Abstract",
        source_kind=SourceKind.PUBMED,
        source_name="PubMed",
        source_url="https://example.test",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        evidence_type=EvidenceType.OTHER,
        source_scope=SourceScope.ABSTRACT_ONLY,
    )
    return ReleaseManifest(
        release_id=release_id,
        generated_at=generated_at,
        period_start=generated_at.date(),
        period_end=generated_at.date(),
        briefing_type="weekly",
        reviewed_count=1,
        selected_count=1,
        nuclear_count=1,
        episodes=(episode,),
        candidates=(candidate,),
    )


def _stage_complete_release(
    publisher: ReleasePublisher,
    manifest: ReleaseManifest,
) -> Path:
    staging = publisher.begin(manifest.release_id)
    episode = manifest.episodes[0]
    (staging / "audio" / episode.audio_filename).write_bytes(b"fake")
    publisher.write_transcript(staging, episode, None)
    return staging


def test_finalize_promotes_complete_staging_then_switches_pointer(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        public_base_url="https://audio.example.test",
        feed_token="token",
    )
    publisher = ReleasePublisher(settings)
    manifest = _manifest(
        release_id="release-1",
        guid="urn:test:e1",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        filename="one.mp3",
    )
    staging = _stage_complete_release(publisher, manifest)
    destination = publisher.release_dir(manifest.release_id)

    assert staging.name.startswith(".staging-release-1-")
    assert not destination.exists()
    assert publisher.current_release_id() is None

    promoted = publisher.finalize(manifest, staging)

    assert promoted == destination
    assert not staging.exists()
    assert publisher.current_release_id() == "release-1"
    assert (destination / "feed.xml").is_file()
    assert (destination / "manifest.json").is_file()


def test_incomplete_release_cannot_replace_current_pointer(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        public_base_url="https://audio.example.test",
        feed_token="token",
    )
    publisher = ReleasePublisher(settings)
    first = _manifest(
        release_id="release-1",
        guid="urn:test:release-1",
        generated_at=datetime(2026, 8, 21, tzinfo=UTC),
        filename="release-1.mp3",
    )
    publisher.finalize(first, _stage_complete_release(publisher, first))

    second = _manifest(
        release_id="release-2",
        guid="urn:test:release-2",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        filename="missing.mp3",
    )
    staging = publisher.begin(second.release_id)
    publisher.write_transcript(staging, second.episodes[0], None)

    with pytest.raises(RuntimeError, match="Release is incomplete"):
        publisher.finalize(second, staging)

    assert publisher.current_release_id() == "release-1"
    assert not publisher.release_dir("release-2").exists()
    publisher.discard(staging)
    assert not staging.exists()


def test_current_feed_retains_prior_releases(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        public_base_url="https://audio.example.test",
        feed_token="token",
        release_retention=3,
    )
    publisher = ReleasePublisher(settings)

    first = _manifest(
        release_id="release-1",
        guid="urn:test:release-1",
        generated_at=datetime(2026, 8, 21, tzinfo=UTC),
        filename="release-1.mp3",
    )
    second = _manifest(
        release_id="release-2",
        guid="urn:test:release-2",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        filename="release-2.mp3",
    )
    publisher.finalize(first, _stage_complete_release(publisher, first))
    publisher.finalize(second, _stage_complete_release(publisher, second))

    current = publisher.current_release_dir()
    assert current is not None
    feed = (current / "feed.xml").read_text("utf-8")
    assert "urn:test:release-2" in feed
    assert "urn:test:release-1" in feed
