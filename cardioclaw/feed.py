from __future__ import annotations

from datetime import UTC
from email.utils import format_datetime
from xml.etree import ElementTree as ET

from cardioclaw.config import Settings
from cardioclaw.models import Episode, ReleaseManifest
from cardioclaw.util import join_url

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT = "http://purl.org/rss/1.0/modules/content/"
ATOM = "http://www.w3.org/2005/Atom"
PODCAST = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes", ITUNES)
ET.register_namespace("content", CONTENT)
ET.register_namespace("atom", ATOM)
ET.register_namespace("podcast", PODCAST)


def _tag(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _duration(value: int) -> str:
    hours, remainder = divmod(value, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def feed_url(settings: Settings) -> str:
    return join_url(settings.public_base_url, "feed", f"{settings.feed_token_value}.xml")


def media_url(settings: Settings, *, release_id: str, filename: str) -> str:
    return join_url(
        settings.public_base_url,
        "media",
        settings.feed_token_value,
        release_id,
        filename,
    )


def transcript_url(settings: Settings, *, release_id: str, filename: str) -> str:
    return join_url(
        settings.public_base_url,
        "transcripts",
        settings.feed_token_value,
        release_id,
        filename,
    )


def cover_url(settings: Settings) -> str:
    return join_url(
        settings.public_base_url,
        "assets",
        settings.feed_token_value,
        settings.cover_filename,
    )


def build_feed(
    manifest: ReleaseManifest,
    settings: Settings,
    *,
    history: tuple[ReleaseManifest, ...] = (),
) -> str:
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = settings.show_title
    ET.SubElement(channel, "link").text = feed_url(settings)
    ET.SubElement(channel, "description").text = settings.show_description
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(
        manifest.generated_at.astimezone(UTC)
    )
    ET.SubElement(
        channel,
        _tag(ATOM, "link"),
        {"href": feed_url(settings), "rel": "self", "type": "application/rss+xml"},
    )
    ET.SubElement(channel, _tag(ITUNES, "author")).text = settings.show_author
    ET.SubElement(channel, _tag(ITUNES, "explicit")).text = "false"
    # This is a recurring news briefing, not one narrative series. Distinct publication
    # times keep each release ordered overview-first, followed by its paper episodes.
    ET.SubElement(channel, _tag(ITUNES, "type")).text = "episodic"
    ET.SubElement(channel, _tag(ITUNES, "image"), {"href": cover_url(settings)})
    ET.SubElement(channel, _tag(ITUNES, "category"), {"text": "Health & Fitness"})

    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = cover_url(settings)
    ET.SubElement(image, "title").text = settings.show_title
    ET.SubElement(image, "link").text = feed_url(settings)

    for release in (manifest, *history):
        for episode in release.episodes:
            _append_item(
                channel,
                episode,
                release_id=release.release_id,
                settings=settings,
            )

    ET.indent(rss, space="  ")
    xml = ET.tostring(rss, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n"


def _append_item(
    channel: ET.Element,
    episode: Episode,
    *,
    release_id: str,
    settings: Settings,
) -> None:
    item = ET.SubElement(channel, "item")
    audio = media_url(settings, release_id=release_id, filename=episode.audio_filename)
    transcript = transcript_url(
        settings,
        release_id=release_id,
        filename=episode.transcript_filename,
    )
    description = f"{episode.description}\n\nAccessible transcript and sources: {transcript}"

    ET.SubElement(item, "title").text = episode.title
    ET.SubElement(item, "description").text = description
    ET.SubElement(item, "link").text = transcript
    ET.SubElement(item, "pubDate").text = format_datetime(
        episode.published_at.astimezone(UTC)
    )
    ET.SubElement(
        item,
        "enclosure",
        {"url": audio, "length": str(episode.audio_size), "type": "audio/mpeg"},
    )
    guid = ET.SubElement(item, "guid", {"isPermaLink": "false"})
    guid.text = episode.guid
    ET.SubElement(item, _tag(ITUNES, "author")).text = settings.show_author
    ET.SubElement(item, _tag(ITUNES, "explicit")).text = "false"
    ET.SubElement(item, _tag(ITUNES, "episode")).text = str(episode.track_number)
    ET.SubElement(item, _tag(ITUNES, "episodeType")).text = "full"
    ET.SubElement(item, _tag(ITUNES, "duration")).text = _duration(episode.duration_seconds)
    ET.SubElement(item, _tag(CONTENT, "encoded")).text = description
    ET.SubElement(
        item,
        _tag(PODCAST, "transcript"),
        {"url": transcript, "type": "text/html", "rel": "captions"},
    )
