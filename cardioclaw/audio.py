from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from mutagen.id3 import COMM, TALB, TIT2, TPE1, TRCK, ID3
from mutagen.mp3 import MP3
from openai import OpenAI

from cardioclaw.config import Settings
from cardioclaw.models import Candidate, Episode, EpisodeKind, SourceScope, SummaryFinding
from cardioclaw.util import slugify, stable_id


def build_overview_script(
    findings: tuple[SummaryFinding, ...],
    candidates: list[Candidate],
    *,
    briefing_type: str,
    period_label: str,
) -> str:
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    nuclear_count = sum(
        1
        for finding in findings
        if by_id[finding.candidate_id].topic.value == "nuclear_cardiology"
    )
    sentences = [
        f"Good morning. This is your {briefing_type} Cardiology Report for {period_label}.",
        (
            f"There are {len(findings)} paper episodes in this briefing, "
            f"including {nuclear_count} focused on nuclear cardiology."
        ),
        (
            "This overview gives the headlines. When it ends, your podcast app can "
            "continue to the first paper. Say next episode at any time to move to the "
            "next paper."
        ),
    ]
    for index, finding in enumerate(findings, start=1):
        sentences.append(f"Paper {index} of {len(findings)}. {finding.headline}")
    sentences.append(
        "That concludes the overview. The full paper briefings follow as separate episodes."
    )
    return " ".join(sentences)


def build_paper_script(
    finding: SummaryFinding,
    candidate: Candidate,
    *,
    index: int,
    total: int,
) -> str:
    scope = {
        "full_text": "The summary was prepared from accessible full text.",
        "abstract_only": (
            "Only the abstract was available. Details not reported in the abstract "
            "are treated as unavailable."
        ),
        "rss_snippet": (
            "Only a journal or society feed snippet was available. Treat this as an "
            "announcement, not a full paper review."
        ),
    }[candidate.source_scope.value]
    return " ".join(
        [
            f"Paper {index} of {total}.",
            finding.headline,
            f"Why it matters. {finding.why_it_matters}",
            finding.spoken_summary,
            f"Limitations. {finding.limitations}",
            scope,
            f"Source. {candidate.citation_label}.",
            "Say next episode to continue to the next paper, or previous episode to hear the prior paper.",
        ]
    )


class OpenAITTSRenderer:
    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key_value:
            raise RuntimeError("CARDIOCLAW_OPENAI_API_KEY is required")
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key_value)

    def render(
        self,
        text: str,
        destination: Path,
        *,
        title: str,
        track_number: int,
    ) -> tuple[int, int]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        speech = self.client.audio.speech
        streaming = getattr(speech, "with_streaming_response", None)
        if streaming is not None:
            with streaming.create(
                model=self.settings.openai_tts_model,
                voice=self.settings.openai_voice,
                input=text,
                instructions=self.settings.openai_tts_instructions,
                response_format="mp3",
            ) as response:
                response.stream_to_file(destination)
        else:
            response = speech.create(
                model=self.settings.openai_tts_model,
                voice=self.settings.openai_voice,
                input=text,
                instructions=self.settings.openai_tts_instructions,
                response_format="mp3",
            )
            response.stream_to_file(destination)

        audio = MP3(destination)
        duration = max(1, int(round(audio.info.length)))
        size = destination.stat().st_size
        self._tag(destination, title=title, track_number=track_number)
        return size, duration

    def _tag(self, path: Path, *, title: str, track_number: int) -> None:
        try:
            tags = ID3(path)
        except Exception:
            tags = ID3()
        for key in ("TIT2", "TALB", "TPE1", "TRCK", "COMM"):
            tags.delall(key)
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TALB(encoding=3, text=self.settings.show_title))
        tags.add(TPE1(encoding=3, text=self.settings.show_author))
        tags.add(TRCK(encoding=3, text=str(track_number)))
        tags.add(
            COMM(
                encoding=3,
                lang="eng",
                desc="Cardiology Claw",
                text="Automated professional education briefing; not patient-specific advice.",
            )
        )
        tags.save(path)


def content_addressed_filename(prefix: str, script: str) -> str:
    digest = hashlib.sha256(script.encode("utf-8")).hexdigest()[:12]
    return f"{slugify(prefix)}-{digest}.mp3"


def episode_guid(period_key: str, episode_key: str) -> str:
    return f"urn:cardioclaw:{period_key}:{stable_id(episode_key, length=24)}"


def make_episode(
    *,
    episode_id: str,
    guid: str,
    kind: EpisodeKind,
    title: str,
    description: str,
    script: str,
    filename: str,
    size: int,
    duration: int,
    published_at: datetime,
    track_number: int,
    transcript_filename: str,
    source_candidate_id: str | None = None,
    source_url: str | None = None,
    source_scope: SourceScope | None = None,
) -> Episode:
    return Episode(
        episode_id=episode_id,
        guid=guid,
        kind=kind,
        title=title,
        description=description,
        spoken_script=script,
        audio_filename=filename,
        audio_size=size,
        duration_seconds=duration,
        published_at=published_at.astimezone(UTC),
        track_number=track_number,
        transcript_filename=transcript_filename,
        source_candidate_id=source_candidate_id,
        source_url=source_url,
        source_scope=source_scope,
    )
