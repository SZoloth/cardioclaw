from __future__ import annotations

import html
import re
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree

import feedparser
from Bio import Entrez

from cardioclaw.config import Settings
from cardioclaw.models import Candidate, EvidenceType, SourceKind, SourceScope, Topic
from cardioclaw.util import stable_id

NUCLEAR_CARDIOLOGY_QUERY = (
    '"nuclear cardiology"[MeSH Terms] OR "cardiac PET" OR '
    '"myocardial perfusion imaging" OR "cardiac SPECT" OR '
    '"coronary flow reserve" OR "myocardial blood flow" OR '
    '"cardiac amyloid" OR "cardiac sarcoidosis" OR '
    '"radionuclide ventriculography" OR "PET myocardial" OR '
    'flurpiridaz OR radiotracer OR "cardiac molecular imaging"'
)

GENERAL_CARDIOLOGY_QUERY = (
    "cardiology AND (randomized controlled trial[pt] OR guideline[pt] OR "
    "meta-analysis[pt] OR practice guideline[pt])"
)

JOURNAL_FEEDS = {
    "Journal of Nuclear Medicine": "https://jnm.snmjournals.org/rss/ahead.xml",
    "BMJ Heart": "https://heart.bmj.com/rss/current.xml",
    "AHA Circulation": (
        "https://www.ahajournals.org/action/showFeed?type=etoc&feed=rss&jc=circ"
    ),
}

SOCIETY_NEWS_FEEDS = {
    "ASNC News": (
        "https://news.google.com/rss/search?"
        "q=ASNC+nuclear+cardiology&hl=en-US&gl=US&ceid=US:en"
    ),
    "SNMMI News": (
        "https://news.google.com/rss/search?"
        "q=SNMMI+cardiology&hl=en-US&gl=US&ceid=US:en"
    ),
}

NUCLEAR_KEYWORDS = {
    "nuclear cardiology", "cardiac pet", "pet/ct", "spect",
    "myocardial perfusion", "myocardial blood flow", "coronary flow reserve",
    "radiotracer", "radionuclide", "flurpiridaz", "cardiac amyloid",
    "cardiac sarcoidosis", "molecular imaging", "technetium", "rubidium-82",
    "n-13 ammonia", "fdg pet",
}

SOCIETY_OR_REGULATORY_KEYWORDS = {
    "asnc", "snmmi", "society", "guideline", "consensus", "appropriate use",
    "practice statement", "fda", "approval", "safety communication",
}


def _clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().lower()
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value)
    return value or None


def _candidate_id(*, pmid: str | None, doi: str | None, source_url: str, title: str) -> str:
    if pmid:
        return f"pmid-{pmid}"
    if doi:
        return f"doi-{stable_id(doi, length=24)}"
    return f"item-{stable_id(source_url, title, length=24)}"


def _is_nuclear(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in NUCLEAR_KEYWORDS)


def _evidence_type(publication_types: Iterable[str], title: str) -> EvidenceType:
    values = {value.lower() for value in publication_types}
    lowered = title.lower()
    if "guideline" in values or "practice guideline" in values or "guideline" in lowered:
        return EvidenceType.GUIDELINE
    if "randomized controlled trial" in values or "randomized" in lowered:
        return EvidenceType.RANDOMIZED_TRIAL
    if "meta-analysis" in values or "meta-analysis" in lowered:
        return EvidenceType.META_ANALYSIS
    if "systematic review" in values or "systematic review" in lowered:
        return EvidenceType.SYSTEMATIC_REVIEW
    if "observational study" in values:
        return EvidenceType.OBSERVATIONAL
    return EvidenceType.OTHER


def _parse_pubmed_date(article: dict[str, Any]) -> datetime | None:
    try:
        journal_issue = article["MedlineCitation"]["Article"]["Journal"]["JournalIssue"]
        pub_date = journal_issue.get("PubDate", {})
        year = int(str(pub_date.get("Year") or "")[:4])
        month_raw = str(pub_date.get("Month") or "1")
        day = int(str(pub_date.get("Day") or "1"))
        month_map = {
            name.lower(): index
            for index, name in enumerate(
                ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            )
        }
        month = int(month_raw) if month_raw.isdigit() else month_map.get(month_raw[:3].lower(), 1)
        return datetime(year, month, day, tzinfo=UTC)
    except (KeyError, TypeError, ValueError):
        return None


class PubMedSource:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        Entrez.email = settings.ncbi_email
        Entrez.tool = settings.ncbi_tool
        Entrez.api_key = settings.ncbi_api_key_value

    def _pause(self) -> None:
        time.sleep(0.12 if self.settings.ncbi_api_key_value else 0.36)

    def search(
        self,
        query: str,
        *,
        from_date: str,
        to_date: str,
        max_results: int,
        topic: Topic,
    ) -> list[Candidate]:
        full_query = f"({query}) AND {from_date}:{to_date}[Publication Date]"
        with Entrez.esearch(db="pubmed", term=full_query, retmax=max_results, sort="pub date") as handle:
            result = Entrez.read(handle)
        self._pause()
        return self.fetch(list(result.get("IdList", [])), topic=topic)

    def fetch(self, pmids: list[str], *, topic: Topic) -> list[Candidate]:
        if not pmids:
            return []
        with Entrez.efetch(db="pubmed", id=",".join(pmids), retmode="xml") as handle:
            records = Entrez.read(handle)
        self._pause()

        candidates: list[Candidate] = []
        for record in records.get("PubmedArticle", []):
            medline = record.get("MedlineCitation", {})
            article = medline.get("Article", {})
            pmid = str(medline.get("PMID", "")).strip() or None
            title = _clean_text(article.get("ArticleTitle", ""))
            if not title:
                continue

            abstract_parts = []
            for part in article.get("Abstract", {}).get("AbstractText", []):
                label = str(getattr(part, "attributes", {}).get("Label", "")).strip()
                text = _clean_text(part)
                abstract_parts.append(f"{label}: {text}" if label else text)
            abstract = "\n".join(part for part in abstract_parts if part)
            journal = _clean_text(article.get("Journal", {}).get("Title", ""))

            authors = []
            for author in article.get("AuthorList", []):
                collective = _clean_text(author.get("CollectiveName", ""))
                if collective:
                    authors.append(collective)
                    continue
                given = _clean_text(author.get("ForeName", ""))
                family = _clean_text(author.get("LastName", ""))
                name = " ".join(part for part in (given, family) if part)
                if name:
                    authors.append(name)

            doi = None
            for identifier in record.get("PubmedData", {}).get("ArticleIdList", []):
                if str(getattr(identifier, "attributes", {}).get("IdType", "")) == "doi":
                    doi = _normalize_doi(str(identifier))
                    break

            publication_types = [_clean_text(item) for item in article.get("PublicationTypeList", [])]
            source_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            candidate_topic = (
                Topic.NUCLEAR_CARDIOLOGY
                if topic == Topic.NUCLEAR_CARDIOLOGY or _is_nuclear(f"{title} {abstract}")
                else Topic.GENERAL_CARDIOLOGY
            )
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id(pmid=pmid, doi=doi, source_url=source_url, title=title),
                    title=title,
                    abstract=abstract,
                    source_kind=SourceKind.PUBMED,
                    source_name="PubMed",
                    source_url=source_url,
                    published_at=_parse_pubmed_date(record),
                    topic=candidate_topic,
                    evidence_type=_evidence_type(publication_types, title),
                    source_scope=SourceScope.ABSTRACT_ONLY,
                    pmid=pmid,
                    doi=doi,
                    journal=journal or None,
                    authors=tuple(authors[:12]),
                )
            )
        return candidates

    def enrich_full_text(self, candidate: Candidate) -> Candidate:
        if not self.settings.full_text_enabled or not candidate.pmid:
            return candidate
        pmcid = self._find_pmcid(candidate.pmid)
        if not pmcid:
            return candidate
        full_text = self._fetch_pmc_text(pmcid)
        if not full_text:
            return candidate
        return candidate.model_copy(
            update={
                "pmcid": pmcid,
                "full_text": full_text[: self.settings.max_full_text_characters],
                "source_scope": SourceScope.FULL_TEXT,
            }
        )

    def _find_pmcid(self, pmid: str) -> str | None:
        try:
            with Entrez.elink(dbfrom="pubmed", db="pmc", id=pmid) as handle:
                records = Entrez.read(handle)
            self._pause()
            for record in records:
                for database in record.get("LinkSetDb", []):
                    if database.get("DbTo") != "pmc":
                        continue
                    links = database.get("Link", [])
                    if links:
                        return f"PMC{links[0]['Id']}"
        except Exception:
            return None
        return None

    def _fetch_pmc_text(self, pmcid: str) -> str | None:
        try:
            with Entrez.efetch(db="pmc", id=pmcid, retmode="xml") as handle:
                payload = handle.read()
            self._pause()
            root = ElementTree.fromstring(payload)
            paragraphs: list[str] = []
            for section in root.findall(".//body//sec"):
                title = _clean_text(section.findtext("title", default=""))
                if title:
                    paragraphs.append(title)
                for paragraph in section.findall("./p"):
                    text = _clean_text("".join(paragraph.itertext()))
                    if text:
                        paragraphs.append(text)
            return "\n\n".join(paragraphs) or None
        except Exception:
            return None


class RSSSource:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch(self, feeds: dict[str, str], *, source_kind: SourceKind, default_topic: Topic) -> list[Candidate]:
        candidates: list[Candidate] = []
        for source_name, feed_url in feeds.items():
            parsed = feedparser.parse(
                feed_url,
                request_headers={
                    "User-Agent": (
                        "CardiologyClaw/5.0 "
                        f"(contact: {self.settings.ncbi_email or 'not-configured'})"
                    )
                },
            )
            for item in parsed.entries[: self.settings.max_rss_items_per_feed]:
                title = _clean_text(item.get("title", ""))
                summary = _clean_text(item.get("summary", item.get("description", "")))
                source_url = str(item.get("link", feed_url))
                if not title:
                    continue
                combined = f"{title} {summary}"
                topic = Topic.NUCLEAR_CARDIOLOGY if _is_nuclear(combined) else default_topic
                if source_kind == SourceKind.SOCIETY_NEWS and not any(
                    keyword in combined.lower() for keyword in SOCIETY_OR_REGULATORY_KEYWORDS
                ):
                    continue
                evidence_type = (
                    EvidenceType.SOCIETY_ANNOUNCEMENT
                    if source_kind == SourceKind.SOCIETY_NEWS
                    else _evidence_type([], title)
                )
                candidates.append(
                    Candidate(
                        candidate_id=_candidate_id(
                            pmid=None, doi=None, source_url=source_url, title=title
                        ),
                        title=title,
                        abstract=summary,
                        source_kind=source_kind,
                        source_name=source_name,
                        source_url=source_url,
                        published_at=_rss_date(item),
                        topic=topic,
                        evidence_type=evidence_type,
                        source_scope=SourceScope.RSS_SNIPPET,
                    )
                )
        return candidates


def _rss_date(item: Any) -> datetime | None:
    parsed = item.get("published_parsed") or item.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime(*parsed[:6], tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def discover_candidates(settings: Settings, *, from_date: str, to_date: str) -> list[Candidate]:
    pubmed = PubMedSource(settings)
    rss = RSSSource(settings)
    return [
        *pubmed.search(
            NUCLEAR_CARDIOLOGY_QUERY,
            from_date=from_date,
            to_date=to_date,
            max_results=settings.max_nuclear_candidates,
            topic=Topic.NUCLEAR_CARDIOLOGY,
        ),
        *pubmed.search(
            GENERAL_CARDIOLOGY_QUERY,
            from_date=from_date,
            to_date=to_date,
            max_results=settings.max_general_candidates,
            topic=Topic.GENERAL_CARDIOLOGY,
        ),
        *rss.fetch(
            JOURNAL_FEEDS,
            source_kind=SourceKind.JOURNAL_RSS,
            default_topic=Topic.GENERAL_CARDIOLOGY,
        ),
        *rss.fetch(
            SOCIETY_NEWS_FEEDS,
            source_kind=SourceKind.SOCIETY_NEWS,
            default_topic=Topic.NUCLEAR_CARDIOLOGY,
        ),
    ]
