from __future__ import annotations

import time
from types import SimpleNamespace

from Bio import Entrez

from cardioclaw.config import Settings
from cardioclaw.models import Candidate, EvidenceType, SourceKind, SourceScope, Topic
from cardioclaw.sources import (
    PubMedSource,
    RSSSource,
    _candidate_id,
    _clean_text,
    _evidence_type,
    _is_nuclear,
    _normalize_doi,
    _rss_date,
)


class TaggedText(str):
    def __new__(cls, value: str, **attributes):
        instance = super().__new__(cls, value)
        instance.attributes = attributes
        return instance


class Handle:
    def __init__(self, payload=None):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.payload


def test_source_helpers_normalize_identifiers_and_classification() -> None:
    assert _clean_text("<b>Cardiac&nbsp;PET</b>") == "Cardiac PET"
    assert _normalize_doi("https://doi.org/10.1000/ABC") == "10.1000/abc"
    assert _normalize_doi(None) is None
    assert _candidate_id(
        pmid="123", doi=None, source_url="https://example.test", title="Title"
    ) == "pmid-123"
    assert _is_nuclear("Quantitative myocardial blood flow with cardiac PET") is True
    assert _is_nuclear("General hypertension trial") is False
    assert _evidence_type(["Randomized Controlled Trial"], "Trial") == (
        EvidenceType.RANDOMIZED_TRIAL
    )
    assert _evidence_type([], "Updated practice guideline") == EvidenceType.GUIDELINE
    assert _evidence_type([], "Ordinary article") == EvidenceType.OTHER


def test_rss_source_filters_society_news_and_classifies_nuclear(monkeypatch) -> None:
    relevant = {
        "title": "ASNC issues cardiac PET appropriate use statement",
        "summary": "Society guidance for myocardial blood flow.",
        "link": "https://example.test/asnc",
        "published_parsed": time.gmtime(0),
    }
    irrelevant = {
        "title": "Quarterly imaging company earnings report",
        "summary": "Revenue and staffing update for a commercial vendor.",
        "link": "https://example.test/irrelevant",
    }
    monkeypatch.setattr(
        "cardioclaw.sources.feedparser.parse",
        lambda *args, **kwargs: SimpleNamespace(entries=[relevant, irrelevant]),
    )
    source = RSSSource(Settings(_env_file=None, max_rss_items_per_feed=4))

    candidates = source.fetch(
        {"ASNC": "https://example.test/feed"},
        source_kind=SourceKind.SOCIETY_NEWS,
        default_topic=Topic.NUCLEAR_CARDIOLOGY,
    )

    assert len(candidates) == 1
    assert candidates[0].topic == Topic.NUCLEAR_CARDIOLOGY
    assert candidates[0].evidence_type == EvidenceType.SOCIETY_ANNOUNCEMENT
    assert candidates[0].source_scope == SourceScope.RSS_SNIPPET
    assert _rss_date(relevant) is not None
    assert _rss_date({}) is None


def test_pubmed_fetch_builds_structured_candidate(monkeypatch) -> None:
    record = {
        "MedlineCitation": {
            "PMID": "123",
            "Article": {
                "ArticleTitle": "Randomized cardiac PET perfusion trial",
                "Abstract": {
                    "AbstractText": [
                        TaggedText("Background text.", Label="BACKGROUND"),
                        TaggedText("Reported results.", Label="RESULTS"),
                    ]
                },
                "Journal": {
                    "Title": "Journal of Nuclear Cardiology",
                    "JournalIssue": {
                        "PubDate": {"Year": "2026", "Month": "Aug", "Day": "28"}
                    },
                },
                "AuthorList": [
                    {"ForeName": "Ada", "LastName": "Lovelace"},
                    {"CollectiveName": "PET Trial Group"},
                ],
                "PublicationTypeList": ["Randomized Controlled Trial"],
            },
        },
        "PubmedData": {
            "ArticleIdList": [TaggedText("10.1000/PET", IdType="doi")]
        },
    }
    monkeypatch.setattr(Entrez, "efetch", lambda **kwargs: Handle())
    monkeypatch.setattr(Entrez, "read", lambda handle: {"PubmedArticle": [record]})
    source = PubMedSource(Settings(_env_file=None, ncbi_email="operator@example.test"))
    monkeypatch.setattr(source, "_pause", lambda: None)

    candidates = source.fetch(["123"], topic=Topic.NUCLEAR_CARDIOLOGY)

    assert len(candidates) == 1
    result = candidates[0]
    assert result.pmid == "123"
    assert result.doi == "10.1000/pet"
    assert result.evidence_type == EvidenceType.RANDOMIZED_TRIAL
    assert result.authors == ("Ada Lovelace", "PET Trial Group")
    assert result.published_at is not None
    assert "BACKGROUND: Background text." in result.abstract


def test_pubmed_search_and_full_text_enrichment(monkeypatch) -> None:
    monkeypatch.setattr(Entrez, "esearch", lambda **kwargs: Handle())
    monkeypatch.setattr(Entrez, "read", lambda handle: {"IdList": ["123"]})
    source = PubMedSource(Settings(_env_file=None, ncbi_email="operator@example.test"))
    monkeypatch.setattr(source, "_pause", lambda: None)
    monkeypatch.setattr(source, "fetch", lambda pmids, topic: [pmids, topic])

    result = source.search(
        "cardiac PET",
        from_date="2026/08/21",
        to_date="2026/08/28",
        max_results=10,
        topic=Topic.NUCLEAR_CARDIOLOGY,
    )
    assert result[0] == ["123"]

    source = PubMedSource(Settings(_env_file=None, ncbi_email="operator@example.test"))
    item = Candidate(
        candidate_id="pmid-123",
        title="Cardiac PET study",
        abstract="Abstract evidence.",
        source_kind=SourceKind.PUBMED,
        source_name="PubMed",
        source_url="https://pubmed.ncbi.nlm.nih.gov/123/",
        topic=Topic.NUCLEAR_CARDIOLOGY,
        evidence_type=EvidenceType.OTHER,
        source_scope=SourceScope.ABSTRACT_ONLY,
        pmid="123",
    )
    monkeypatch.setattr(source, "_find_pmcid", lambda pmid: "PMC456")
    monkeypatch.setattr(source, "_fetch_pmc_text", lambda pmcid: "Full methods and results.")

    enriched = source.enrich_full_text(item)
    assert enriched.pmcid == "PMC456"
    assert enriched.source_scope == SourceScope.FULL_TEXT
    assert enriched.full_text == "Full methods and results."


def test_fetch_pmc_text_parses_section_titles_and_paragraphs(monkeypatch) -> None:
    xml = """
    <article><body><sec><title>Methods</title><p>Study design.</p></sec>
    <sec><title>Results</title><p>Reported result.</p></sec></body></article>
    """
    monkeypatch.setattr(Entrez, "efetch", lambda **kwargs: Handle(xml))
    source = PubMedSource(Settings(_env_file=None, ncbi_email="operator@example.test"))
    monkeypatch.setattr(source, "_pause", lambda: None)

    text = source._fetch_pmc_text("PMC456")

    assert text is not None
    assert "Methods" in text
    assert "Study design." in text
    assert "Results" in text
