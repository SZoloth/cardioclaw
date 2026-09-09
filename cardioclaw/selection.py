from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime

from cardioclaw.config import Settings
from cardioclaw.models import Candidate, EvidenceType, SourceKind, SourceScope, Topic


EVIDENCE_WEIGHTS = {
    EvidenceType.GUIDELINE: 35,
    EvidenceType.RANDOMIZED_TRIAL: 30,
    EvidenceType.META_ANALYSIS: 28,
    EvidenceType.SYSTEMATIC_REVIEW: 22,
    EvidenceType.OBSERVATIONAL: 12,
    EvidenceType.SOCIETY_ANNOUNCEMENT: 10,
    EvidenceType.REGULATORY_NEWS: 16,
    EvidenceType.OTHER: 5,
}

SOURCE_WEIGHTS = {
    SourceKind.PUBMED: 30,
    SourceKind.JOURNAL_RSS: 12,
    SourceKind.SOCIETY_NEWS: 6,
}

SCOPE_WEIGHTS = {
    SourceScope.FULL_TEXT: 20,
    SourceScope.ABSTRACT_ONLY: 12,
    SourceScope.RSS_SNIPPET: 0,
}


def _normalized_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _dedupe_key(candidate: Candidate) -> str:
    if candidate.pmid:
        return f"pmid:{candidate.pmid}"
    if candidate.doi:
        return f"doi:{candidate.doi.lower()}"
    return f"title:{_normalized_title(candidate.title)}"


def _recency_score(candidate: Candidate, now: datetime) -> float:
    if not candidate.published_at:
        return 0
    published = candidate.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=UTC)
    age_days = max(0, (now - published).days)
    if age_days <= 7:
        return 12
    if age_days <= 30:
        return 8
    if age_days <= 90:
        return 3
    return 0


def score_candidate(candidate: Candidate, now: datetime | None = None) -> Candidate:
    now = now or datetime.now(UTC)
    score = 0.0
    reasons: list[str] = []

    source_score = SOURCE_WEIGHTS[candidate.source_kind]
    score += source_score
    reasons.append(f"{candidate.source_kind.value} source +{source_score}")

    evidence_score = EVIDENCE_WEIGHTS[candidate.evidence_type]
    score += evidence_score
    reasons.append(f"{candidate.evidence_type.value} +{evidence_score}")

    scope_score = SCOPE_WEIGHTS[candidate.source_scope]
    score += scope_score
    reasons.append(f"{candidate.source_scope.value} +{scope_score}")

    if candidate.topic == Topic.NUCLEAR_CARDIOLOGY:
        score += 45
        reasons.append("nuclear cardiology +45")

    recency = _recency_score(candidate, now)
    if recency:
        score += recency
        reasons.append(f"recent +{recency:g}")

    if candidate.source_kind == SourceKind.SOCIETY_NEWS:
        score -= 18
        reasons.append("secondary news penalty -18")

    if not candidate.abstract.strip():
        score -= 25
        reasons.append("missing evidence text -25")

    return candidate.model_copy(
        update={
            "selection_score": score,
            "selection_reasons": tuple(reasons),
        }
    )


def deduplicate(candidates: list[Candidate]) -> list[Candidate]:
    groups: dict[str, list[Candidate]] = defaultdict(list)
    for candidate in candidates:
        groups[_dedupe_key(candidate)].append(candidate)

    result: list[Candidate] = []
    for group in groups.values():
        scored = [score_candidate(candidate) for candidate in group]
        scored.sort(
            key=lambda candidate: (
                candidate.selection_score,
                candidate.source_scope == SourceScope.FULL_TEXT,
                candidate.source_kind == SourceKind.PUBMED,
            ),
            reverse=True,
        )
        result.append(scored[0])
    return result


def select_candidates(candidates: list[Candidate], settings: Settings) -> list[Candidate]:
    """Select a high-quality, nuclear-first portfolio deterministically."""

    scored = [
        score_candidate(candidate)
        for candidate in deduplicate(candidates)
        if candidate.abstract.strip()
    ]
    eligible = [
        candidate
        for candidate in scored
        if candidate.selection_score >= settings.min_selection_score
    ]

    nuclear = sorted(
        (candidate for candidate in eligible if candidate.topic == Topic.NUCLEAR_CARDIOLOGY),
        key=lambda item: (
            item.selection_score,
            item.published_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    general = sorted(
        (candidate for candidate in eligible if candidate.topic == Topic.GENERAL_CARDIOLOGY),
        key=lambda item: (
            item.selection_score,
            item.published_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )

    selected: list[Candidate] = []
    selected.extend(nuclear[: settings.min_nuclear_findings])

    remaining_nuclear = nuclear[settings.min_nuclear_findings :]
    pool = sorted(
        [*remaining_nuclear, *general],
        key=lambda item: (
            item.topic == Topic.NUCLEAR_CARDIOLOGY,
            item.selection_score,
            item.published_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    for candidate in pool:
        if len(selected) >= settings.max_findings:
            break
        if candidate.candidate_id not in {item.candidate_id for item in selected}:
            selected.append(candidate)

    return selected[: settings.max_findings]
