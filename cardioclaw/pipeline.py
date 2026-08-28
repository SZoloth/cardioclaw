from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from cardioclaw.alerts import send_alert
from cardioclaw.audio import (
    OpenAITTSRenderer,
    build_overview_script,
    build_paper_script,
    content_addressed_filename,
    episode_guid,
    make_episode,
)
from cardioclaw.config import Settings
from cardioclaw.models import (
    Candidate,
    Episode,
    EpisodeKind,
    ReleaseManifest,
    SummaryFinding,
    Topic,
)
from cardioclaw.publisher import ReleasePublisher
from cardioclaw.selection import select_candidates
from cardioclaw.sources import PubMedSource, discover_candidates
from cardioclaw.summarizer import ClaudeSummarizer
from cardioclaw.util import slugify, stable_id


class Summarizer(Protocol):
    def summarize(self, candidates: list[Candidate]) -> tuple[SummaryFinding, ...]: ...


class Renderer(Protocol):
    def render(
        self,
        text: str,
        destination: Path,
        *,
        title: str,
        track_number: int,
    ) -> tuple[int, int]: ...


@dataclass(frozen=True)
class Period:
    briefing_type: str
    start: date
    end: date

    @property
    def label(self) -> str:
        if self.start == self.end:
            return f"{self.end.strftime('%B')} {self.end.day}, {self.end.year}"
        return (
            f"{self.start.strftime('%B')} {self.start.day} through "
            f"{self.end.strftime('%B')} {self.end.day}, {self.end.year}"
        )

    @property
    def key(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"


def resolve_period(
    now: datetime,
    *,
    briefing_type: str = "weekly",
    lookback_days: int | None = None,
) -> Period:
    """Resolve inclusive publication-date boundaries.

    Weekly defaults to seven calendar dates ending today. Daily defaults to the
    previous calendar date, avoiding an ambiguous two-day "daily" label.
    """

    if briefing_type not in {"weekly", "daily"}:
        raise ValueError(f"Unsupported briefing type: {briefing_type}")

    today = now.astimezone(UTC).date()
    if lookback_days is not None:
        days = max(1, lookback_days)
        end = today
        start = end - timedelta(days=days - 1)
    elif briefing_type == "weekly":
        end = today
        start = end - timedelta(days=6)
    else:
        end = today - timedelta(days=1)
        start = end
    return Period(briefing_type=briefing_type, start=start, end=end)


def _pubmed_date(value: date) -> str:
    return value.strftime("%Y/%m/%d")


class CardiologyClawPipeline:
    def __init__(
        self,
        settings: Settings,
        *,
        summarizer: Summarizer | None = None,
        renderer: Renderer | None = None,
        publisher: ReleasePublisher | None = None,
    ) -> None:
        self.settings = settings
        self.summarizer = summarizer
        self.renderer = renderer
        self.publisher = publisher or ReleasePublisher(settings)

    def run(
        self,
        *,
        now: datetime | None = None,
        briefing_type: str = "weekly",
        lookback_days: int | None = None,
        supplied_candidates: list[Candidate] | None = None,
    ) -> ReleaseManifest:
        self.settings.require_generation_credentials()
        self.settings.prepare_directories()
        now = (now or datetime.now(UTC)).astimezone(UTC)
        period = resolve_period(now, briefing_type=briefing_type, lookback_days=lookback_days)
        if supplied_candidates is not None:
            discovered = supplied_candidates
        else:
            discovered = discover_candidates(
                self.settings,
                from_date=_pubmed_date(period.start),
                to_date=_pubmed_date(period.end),
            )
        selected = select_candidates(discovered, self.settings)
        if not selected:
            raise RuntimeError("No eligible cardiology sources were selected")

        selected = self._enrich(selected)
        findings = (self.summarizer or ClaudeSummarizer(self.settings)).summarize(selected)
        if len(findings) != len(selected):
            raise RuntimeError(f"Expected {len(selected)} summaries; received {len(findings)}")

        release_id = self._release_id(period, selected, now)
        staging_dir = self.publisher.begin(release_id)
        try:
            episodes = self._render_episodes(
                self.renderer or OpenAITTSRenderer(self.settings),
                release_dir=staging_dir,
                period=period,
                candidates=selected,
                findings=findings,
                generated_at=now,
            )
            manifest = ReleaseManifest(
                release_id=release_id,
                generated_at=now,
                period_start=period.start,
                period_end=period.end,
                briefing_type=period.briefing_type,
                reviewed_count=len(discovered),
                selected_count=len(selected),
                nuclear_count=sum(
                    1 for item in selected if item.topic == Topic.NUCLEAR_CARDIOLOGY
                ),
                episodes=tuple(episodes),
                candidates=tuple(selected),
            )

            by_id = {candidate.candidate_id: candidate for candidate in selected}
            for episode in episodes:
                candidate = (
                    by_id.get(episode.source_candidate_id)
                    if episode.source_candidate_id
                    else None
                )
                self.publisher.write_transcript(staging_dir, episode, candidate)
            self.publisher.finalize(manifest, staging_dir)
        except Exception:
            self.publisher.discard(staging_dir)
            raise

        send_alert(
            self.settings,
            f"Published {len(episodes)} episodes",
            (
                f"Release {release_id} published successfully.\n"
                f"Reviewed: {len(discovered)}\nSelected: {len(selected)}\n"
                f"Nuclear cardiology: {manifest.nuclear_count}\n"
                "Feed path: /feed/<private-token>.xml"
            ),
        )
        return manifest

    def _enrich(self, candidates: list[Candidate]) -> list[Candidate]:
        if not self.settings.full_text_enabled:
            return candidates
        pubmed = PubMedSource(self.settings)
        return [
            pubmed.enrich_full_text(candidate)
            if candidate.source_kind.value == "pubmed"
            else candidate
            for candidate in candidates
        ]

    def _release_id(self, period: Period, candidates: list[Candidate], now: datetime) -> str:
        digest = stable_id(period.key, *(item.candidate_id for item in candidates), length=10)
        return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{digest}"

    def _render_episodes(
        self,
        renderer: Renderer,
        *,
        release_dir: Path,
        period: Period,
        candidates: list[Candidate],
        findings: tuple[SummaryFinding, ...],
        generated_at: datetime,
    ) -> list[Episode]:
        by_id = {candidate.candidate_id: candidate for candidate in candidates}
        episodes: list[Episode] = []
        overview_script = build_overview_script(
            findings,
            candidates,
            briefing_type=period.briefing_type,
            period_label=period.label,
        )
        overview_title = f"00 · {period.briefing_type.title()} Overview — {period.label}"
        overview_filename = content_addressed_filename(
            f"00-overview-{period.end.isoformat()}", overview_script
        )
        size, duration = renderer.render(
            overview_script,
            release_dir / "audio" / overview_filename,
            title=overview_title,
            track_number=1,
        )
        episodes.append(
            make_episode(
                episode_id=f"{period.key}:overview",
                guid=episode_guid(period.key, "overview"),
                kind=EpisodeKind.OVERVIEW,
                title=overview_title,
                description=(
                    f"Headlines for {len(findings)} selected cardiology papers. "
                    "Full paper briefings follow as separate episodes."
                ),
                script=overview_script,
                filename=overview_filename,
                size=size,
                duration=duration,
                published_at=generated_at,
                track_number=1,
                transcript_filename="00-overview.html",
            )
        )

        for index, finding in enumerate(findings, start=1):
            candidate = by_id[finding.candidate_id]
            script = build_paper_script(finding, candidate, index=index, total=len(findings))
            title = f"{index:02d} · {finding.headline.rstrip('.')}"
            filename = content_addressed_filename(
                f"{index:02d}-{candidate.candidate_id}", script
            )
            size, duration = renderer.render(
                script,
                release_dir / "audio" / filename,
                title=title,
                track_number=index + 1,
            )
            episodes.append(
                make_episode(
                    episode_id=f"{period.key}:{candidate.candidate_id}",
                    guid=episode_guid(period.key, candidate.candidate_id),
                    kind=EpisodeKind.PAPER,
                    title=title,
                    description=(
                        f"{finding.why_it_matters} Source scope: "
                        f"{candidate.source_scope.value.replace('_', ' ')}. "
                        f"{candidate.citation_label}."
                    ),
                    script=script,
                    filename=filename,
                    size=size,
                    duration=duration,
                    published_at=generated_at - timedelta(minutes=index),
                    track_number=index + 1,
                    transcript_filename=(
                        f"{index:02d}-{slugify(candidate.title, max_length=56)}.html"
                    ),
                    source_candidate_id=candidate.candidate_id,
                    source_url=candidate.source_url,
                    source_scope=candidate.source_scope,
                )
            )
        return episodes


def run_with_alerts(settings: Settings, **kwargs) -> ReleaseManifest:
    try:
        return CardiologyClawPipeline(settings).run(**kwargs)
    except Exception as exc:
        send_alert(
            settings,
            "Generation failed",
            f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}",
        )
        raise
