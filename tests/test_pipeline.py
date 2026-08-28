from datetime import UTC, datetime
from pathlib import Path

from cardioclaw.config import Settings
from cardioclaw.models import (
    Candidate,
    EvidenceType,
    SourceKind,
    SourceScope,
    SummaryFinding,
    Topic,
)
from cardioclaw.pipeline import CardiologyClawPipeline


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


def test_pipeline_publishes_overview_plus_one_episode_per_paper(tmp_path: Path) -> None:
    settings = Settings(
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
    candidates = [
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

    manifest = CardiologyClawPipeline(
        settings,
        summarizer=FakeSummarizer(),
        renderer=FakeRenderer(),
    ).run(
        now=datetime(2026, 8, 28, tzinfo=UTC),
        supplied_candidates=candidates,
    )

    assert len(manifest.episodes) == 3
    assert manifest.episodes[0].kind == "overview"
    assert [episode.track_number for episode in manifest.episodes] == [1, 2, 3]
    assert (settings.releases_dir / manifest.release_id / "feed.xml").is_file()
    assert settings.current_pointer.is_file()
