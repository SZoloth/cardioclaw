from datetime import UTC, date, datetime
from xml.etree import ElementTree

from cardioclaw.config import Settings
from cardioclaw.feed import build_feed
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


def test_feed_has_stable_required_episode_fields() -> None:
    settings = Settings(
        _env_file=None,
        public_base_url="https://audio.example.test",
        feed_token="secret-token",
    )
    episode = Episode(
        episode_id="week:paper",
        guid="urn:cardioclaw:week:paper",
        kind=EpisodeKind.PAPER,
        title="01 · Test paper",
        description="A source-bounded briefing.",
        spoken_script="Spoken text.",
        audio_filename="paper-a1.mp3",
        audio_size=1234,
        duration_seconds=95,
        published_at=datetime(2026, 8, 28, tzinfo=UTC),
        track_number=2,
        source_candidate_id="paper",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        transcript_filename="01-paper.html",
        source_scope=SourceScope.ABSTRACT_ONLY,
    )
    candidate = Candidate(
        candidate_id="paper",
        title="Test paper",
        abstract="Abstract.",
        source_kind=SourceKind.PUBMED,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        evidence_type=EvidenceType.OTHER,
        source_scope=SourceScope.ABSTRACT_ONLY,
        pmid="123",
    )
    manifest = ReleaseManifest(
        release_id="release-1",
        generated_at=datetime(2026, 8, 28, tzinfo=UTC),
        period_start=date(2026, 8, 21),
        period_end=date(2026, 8, 28),
        briefing_type="weekly",
        reviewed_count=10,
        selected_count=1,
        nuclear_count=1,
        episodes=(episode,),
        candidates=(candidate,),
    )

    xml = build_feed(manifest, settings)
    root = ElementTree.fromstring(xml)
    item = root.find("./channel/item")

    assert item is not None
    assert item.findtext("guid") == episode.guid
    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert enclosure.attrib["url"].startswith(
        "https://audio.example.test/media/secret-token/release-1/"
    )
    assert enclosure.attrib["length"] == "1234"
    assert "secret-token" in root.findtext("./channel/link", default="")
    assert (
        root.findtext("./channel/{http://www.itunes.com/dtds/podcast-1.0.dtd}type")
        == "episodic"
    )
