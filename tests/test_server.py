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
from cardioclaw.server import create_app


def seeded_app(tmp_path: Path):
    cover = tmp_path / "cover.png"
    cover.write_bytes(b"png")
    settings = Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        cover_path=cover,
        feed_token="private-token",
        public_base_url="https://audio.example.test",
    )
    publisher = ReleasePublisher(settings)
    release_dir = publisher.begin("release-1")
    audio = release_dir / "audio" / "episode.mp3"
    audio.write_bytes(b"0123456789")

    episode = Episode(
        episode_id="e1",
        guid="urn:test:e1",
        kind=EpisodeKind.OVERVIEW,
        title="Overview",
        description="Description",
        spoken_script="Transcript",
        audio_filename=audio.name,
        audio_size=audio.stat().st_size,
        duration_seconds=1,
        published_at=datetime(2026, 8, 28, tzinfo=UTC),
        track_number=1,
        transcript_filename="overview.html",
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
    return create_app(settings)


def test_private_feed_and_range_audio(tmp_path: Path) -> None:
    client = seeded_app(tmp_path).test_client()

    assert client.get("/feed/wrong.xml").status_code == 404
    feed = client.get("/feed/private-token.xml")
    assert feed.status_code == 200
    assert feed.mimetype == "application/rss+xml"

    response = client.get(
        "/media/private-token/release-1/episode.mp3",
        headers={"Range": "bytes=0-3"},
    )
    assert response.status_code == 206
    assert response.data == b"0123"
    assert response.headers["Accept-Ranges"] == "bytes"
