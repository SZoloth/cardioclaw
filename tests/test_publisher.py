from datetime import UTC, date, datetime
from pathlib import Path

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


def test_finalize_atomically_switches_current_release(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        public_base_url="https://audio.example.test",
        feed_token="token",
    )
    publisher = ReleasePublisher(settings)
    release_dir = publisher.begin("release-1")
    (release_dir / "audio" / "one.mp3").write_bytes(b"fake")
    episode = Episode(
        episode_id="e1",
        guid="urn:test:e1",
        kind=EpisodeKind.OVERVIEW,
        title="Overview",
        description="Description",
        spoken_script="Transcript",
        audio_filename="one.mp3",
        audio_size=4,
        duration_seconds=1,
        published_at=datetime(2026, 8, 28, tzinfo=UTC),
        track_number=1,
        transcript_filename="one.html",
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
    manifest = ReleaseManifest(
        release_id="release-1",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        period_start=date(2026, 8, 21),
        period_end=date(2026, 8, 28),
        briefing_type="weekly",
        reviewed_count=1,
        selected_count=1,
        nuclear_count=1,
        episodes=(episode,),
        candidates=(candidate,),
    )
    publisher.write_transcript(release_dir, episode, None)
    publisher.finalize(manifest, release_dir)

    assert publisher.current_release_id() == "release-1"
    assert (release_dir / "feed.xml").is_file()
    assert (release_dir / "manifest.json").is_file()


def test_current_feed_retains_prior_releases(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path,
        public_base_url="https://audio.example.test",
        feed_token="token",
        release_retention=3,
    )
    publisher = ReleasePublisher(settings)

    def publish(release_id: str, guid: str, generated_at: datetime) -> None:
        release_dir = publisher.begin(release_id)
        filename = f"{release_id}.mp3"
        (release_dir / "audio" / filename).write_bytes(b"fake")
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
        manifest = ReleaseManifest(
            release_id=release_id,
            generated_at=generated_at,
            period_start=generated_at.date(),
            period_end=generated_at.date(),
            briefing_type="weekly",
            reviewed_count=1,
            selected_count=1,
            nuclear_count=1,
            episodes=(episode,),
            candidates=(),
        )
        publisher.write_transcript(release_dir, episode, None)
        publisher.finalize(manifest, release_dir)

    publish("release-1", "urn:test:release-1", datetime(2026, 8, 21, tzinfo=UTC))
    publish("release-2", "urn:test:release-2", datetime(2026, 8, 28, tzinfo=UTC))

    current = publisher.current_release_dir()
    assert current is not None
    feed = (current / "feed.xml").read_text("utf-8")
    assert "urn:test:release-2" in feed
    assert "urn:test:release-1" in feed
