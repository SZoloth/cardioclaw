from __future__ import annotations

import json
import re

from anthropic import Anthropic

from cardioclaw.config import Settings
from cardioclaw.models import Candidate, SourceScope, SummaryEnvelope, SummaryFinding


def _summary_schema(max_findings: int) -> dict:
    finding = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "candidate_id",
            "headline",
            "why_it_matters",
            "spoken_summary",
            "limitations",
            "source_scope",
            "pronunciation_notes",
        ],
        "properties": {
            "candidate_id": {"type": "string"},
            "headline": {"type": "string", "minLength": 10, "maxLength": 240},
            "why_it_matters": {"type": "string", "minLength": 10, "maxLength": 600},
            "spoken_summary": {"type": "string", "minLength": 80, "maxLength": 4500},
            "limitations": {"type": "string", "minLength": 5, "maxLength": 1000},
            "source_scope": {
                "type": "string",
                "enum": [scope.value for scope in SourceScope],
            },
            "pronunciation_notes": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 20,
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["findings"],
        "properties": {
            "findings": {
                "type": "array",
                "minItems": 1,
                "maxItems": max_findings,
                "items": finding,
            }
        },
    }


def _source_packet(candidate: Candidate) -> dict:
    return {
        "candidate_id": candidate.candidate_id,
        "title": candidate.title,
        "authors": list(candidate.authors),
        "journal": candidate.journal,
        "publication_date": candidate.published_at.isoformat() if candidate.published_at else None,
        "pmid": candidate.pmid,
        "pmcid": candidate.pmcid,
        "doi": candidate.doi,
        "source_url": candidate.source_url,
        "source_scope": candidate.source_scope.value,
        "evidence_type": candidate.evidence_type.value,
        "topic": candidate.topic.value,
        "selection_score": candidate.selection_score,
        "selection_reasons": list(candidate.selection_reasons),
        "evidence_text": candidate.evidence_text,
    }


def _numeric_tokens(value: str) -> set[str]:
    return set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?", value.replace(",", "")))


def _validate_numbers(finding: SummaryFinding, candidate: Candidate) -> None:
    output = " ".join(
        [finding.headline, finding.why_it_matters, finding.spoken_summary, finding.limitations]
    )
    source = " ".join([candidate.title, candidate.abstract, candidate.full_text or ""])
    unsupported = _numeric_tokens(output) - _numeric_tokens(source)
    if unsupported:
        raise ValueError(
            f"{candidate.candidate_id} introduced unsupported numeric tokens: "
            + ", ".join(sorted(unsupported))
        )


def _validate_findings(
    envelope: SummaryEnvelope,
    candidates: list[Candidate],
) -> tuple[SummaryFinding, ...]:
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    seen: set[str] = set()
    validated: list[SummaryFinding] = []

    for finding in envelope.findings:
        candidate = by_id.get(finding.candidate_id)
        if not candidate:
            raise ValueError(f"Model referenced an unselected candidate: {finding.candidate_id}")
        if finding.candidate_id in seen:
            raise ValueError(f"Duplicate summary: {finding.candidate_id}")
        if finding.source_scope != candidate.source_scope:
            raise ValueError(
                f"Source-scope mismatch for {finding.candidate_id}: "
                f"{finding.source_scope} != {candidate.source_scope}"
            )
        _validate_numbers(finding, candidate)
        seen.add(finding.candidate_id)
        validated.append(finding)

    missing = [candidate.candidate_id for candidate in candidates if candidate.candidate_id not in seen]
    if missing:
        raise ValueError("Model omitted selected candidates: " + ", ".join(missing))

    order = {candidate.candidate_id: index for index, candidate in enumerate(candidates)}
    validated.sort(key=lambda finding: order[finding.candidate_id])
    return tuple(validated)


class ClaudeSummarizer:
    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key_value:
            raise RuntimeError("CARDIOCLAW_ANTHROPIC_API_KEY is required")
        self.settings = settings
        self.client = Anthropic(api_key=settings.anthropic_api_key_value)

    def summarize(self, candidates: list[Candidate]) -> tuple[SummaryFinding, ...]:
        if not candidates:
            return ()
        packets = [_source_packet(candidate) for candidate in candidates]
        prompt = (
            "You are producing a private audio briefing for a blind retired nuclear "
            "cardiologist. Summarize every supplied candidate and no others. The candidates "
            "have already been selected and ordered by deterministic policy; preserve that "
            "order. Use only the supplied evidence_text and metadata. Do not use background "
            "knowledge to add facts. Do not invent sample sizes, percentages, effect sizes, "
            "confidence intervals, dates, or conclusions. When source_scope is abstract_only "
            "or rss_snippet, explicitly describe that limitation.\n\n"
            "For each candidate:\n"
            "- headline: one sentence, at most 30 words.\n"
            "- why_it_matters: one or two clinically literate sentences.\n"
            "- spoken_summary: 180 to 300 words of professional spoken prose covering the "
            "question, design, population, reported results, safety when available, and "
            "interpretation. Read numbers naturally.\n"
            "- limitations: the most important evidence and access limitations.\n"
            "- pronunciation_notes: only genuinely difficult names or terms, written as "
            "'term = phonetic guidance'.\n"
            "- Write every scientific numeric value as digits, not number words, so the "
            "application can validate it against the source before speech generation.\n\n"
            "Never call an association causal. Never imply full-text review when only an "
            "abstract or RSS snippet was supplied. If the source lacks a requested detail, "
            "say it was not available rather than filling it in.\n\n"
            "SELECTED CANDIDATES:\n" + json.dumps(packets, ensure_ascii=False)
        )
        response = self.client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=8_000,
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "format": {"type": "json_schema", "schema": _summary_schema(len(candidates))}
            },
        )
        text_blocks = [
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ]
        if not text_blocks:
            raise RuntimeError("Claude returned no text output")
        envelope = SummaryEnvelope.model_validate_json("".join(text_blocks))
        return _validate_findings(envelope, candidates)
