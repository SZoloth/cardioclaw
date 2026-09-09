import pytest

from cardioclaw.models import (
    Candidate,
    EvidenceType,
    SourceKind,
    SourceScope,
    SummaryEnvelope,
    SummaryFinding,
    Topic,
)
from cardioclaw.summarizer import _validate_findings


def source() -> Candidate:
    return Candidate(
        candidate_id="pmid-123",
        title="Trial with 1000 participants",
        abstract=(
            "The primary outcome occurred in 12.4 percent versus 14.5 percent. "
            "The hazard ratio was 0.83 with a 95 percent confidence interval "
            "from 0.74 to 0.93."
        ),
        source_kind=SourceKind.PUBMED,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        evidence_type=EvidenceType.RANDOMIZED_TRIAL,
        source_scope=SourceScope.ABSTRACT_ONLY,
        pmid="123",
    )


def finding(text: str) -> SummaryFinding:
    return SummaryFinding(
        candidate_id="pmid-123",
        headline="A trial reported a lower primary outcome rate.",
        why_it_matters="The finding may inform future nuclear cardiology practice.",
        spoken_summary=text,
        limitations="Only the abstract was available.",
        source_scope=SourceScope.ABSTRACT_ONLY,
    )


def test_validated_summary_preserves_selected_identity_and_numbers() -> None:
    result = _validate_findings(
        SummaryEnvelope(
            findings=(
                finding(
                    "The abstract reports rates of 12.4 percent and 14.5 percent, "
                    "with a hazard ratio of 0.83 and a 95 percent confidence "
                    "interval from 0.74 to 0.93."
                ),
            )
        ),
        [source()],
    )

    assert result[0].candidate_id == "pmid-123"


def test_summary_with_invented_number_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported numeric tokens"):
        _validate_findings(
            SummaryEnvelope(
                findings=(
                    finding(
                        "The abstract reports 12.4 percent versus 14.5 percent "
                        "and claims a number needed to treat of 27."
                    ),
                )
            ),
            [source()],
        )
