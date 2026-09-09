from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

from cardioclaw.audio import OpenAITTSRenderer
from cardioclaw.config import Settings, get_settings
from cardioclaw.pipeline import resolve_period, run_with_alerts
from cardioclaw.publisher import ReleasePublisher
from cardioclaw.selection import select_candidates
from cardioclaw.server import create_app
from cardioclaw.sources import discover_candidates


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        prog="cardioclaw",
        description="Generate and serve a private, podcast-first cardiology briefing.",
    )
    subparsers = command.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate and publish a briefing")
    generate.add_argument("--type", choices=("weekly", "daily"), default="weekly", dest="briefing_type")
    generate.add_argument("--lookback-days", type=int)
    plan = subparsers.add_parser("plan", help="Discover and select sources without paid AI or TTS")
    plan.add_argument("--type", choices=("weekly", "daily"), default="weekly", dest="briefing_type")
    plan.add_argument("--lookback-days", type=int)
    serve = subparsers.add_parser("serve", help="Serve the private RSS feed")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    subparsers.add_parser("validate", help="Validate the current immutable release")
    voice = subparsers.add_parser("voice-sample", help="Render the configured TTS voice")
    voice.add_argument("--output", default="voice-sample.mp3")
    voice.add_argument(
        "--text",
        default=(
            "Cardiac PET measured myocardial blood flow and coronary flow reserve. "
            "The hazard ratio was zero point eight three, with a ninety-five percent "
            "confidence interval from zero point seven four to zero point nine three."
        ),
    )
    return command


def _date(value) -> str:
    return value.strftime("%Y/%m/%d")


def plan(settings: Settings, briefing_type: str, lookback_days: int | None) -> int:
    if not settings.ncbi_email:
        raise RuntimeError("CARDIOCLAW_NCBI_EMAIL is required for PubMed access")
    period = resolve_period(
        datetime.now(UTC),
        briefing_type=briefing_type,
        lookback_days=lookback_days,
    )
    candidates = discover_candidates(
        settings,
        from_date=_date(period.start),
        to_date=_date(period.end),
    )
    selected = select_candidates(candidates, settings)
    print(
        json.dumps(
            {
                "period": period.key,
                "reviewed": len(candidates),
                "selected": [
                    {
                        "position": index,
                        "candidate_id": candidate.candidate_id,
                        "title": candidate.title,
                        "topic": candidate.topic,
                        "evidence_type": candidate.evidence_type,
                        "source_scope": candidate.source_scope,
                        "score": candidate.selection_score,
                        "reasons": candidate.selection_reasons,
                        "source_url": candidate.source_url,
                    }
                    for index, candidate in enumerate(selected, start=1)
                ],
            },
            indent=2,
            default=str,
        )
    )
    return 0


def validate_current(settings: Settings) -> int:
    publisher = ReleasePublisher(settings)
    current = publisher.current_release_dir()
    if not current:
        raise RuntimeError("No current release exists")
    feed = current / "feed.xml"
    manifest = current / "manifest.json"
    if not feed.is_file() or not manifest.is_file():
        raise RuntimeError("Current release is missing feed.xml or manifest.json")
    ElementTree.parse(feed)
    payload = json.loads(manifest.read_text("utf-8"))
    for episode in payload["episodes"]:
        for relative in (
            Path("audio") / episode["audio_filename"],
            Path("transcripts") / episode["transcript_filename"],
        ):
            if not (current / relative).is_file():
                raise RuntimeError(f"Missing release artifact: {relative}")
    print(json.dumps({"valid": True, "release_id": current.name, "episode_count": len(payload["episodes"])}, indent=2))
    return 0


def voice_sample(settings: Settings, text: str, output: str) -> int:
    destination = Path(output).expanduser().resolve()
    size, duration = OpenAITTSRenderer(settings).render(
        text,
        destination,
        title="Cardiology Claw voice sample",
        track_number=1,
    )
    print(f"Wrote {destination} ({size} bytes, {duration} seconds)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    settings = get_settings()
    if args.command == "generate":
        manifest = run_with_alerts(
            settings,
            briefing_type=args.briefing_type,
            lookback_days=args.lookback_days,
        )
        print(manifest.model_dump_json(indent=2))
        return 0
    if args.command == "plan":
        return plan(settings, args.briefing_type, args.lookback_days)
    if args.command == "serve":
        app = create_app(settings)
        app.run(host=args.host or settings.server_host, port=args.port or settings.server_port)
        return 0
    if args.command == "validate":
        return validate_current(settings)
    if args.command == "voice-sample":
        return voice_sample(settings, args.text, args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
