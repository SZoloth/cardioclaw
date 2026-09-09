from __future__ import annotations

import html
import json
import shutil
import tempfile
from pathlib import Path

from cardioclaw.config import Settings
from cardioclaw.feed import build_feed
from cardioclaw.models import Candidate, Episode, ReleaseManifest
from cardioclaw.util import atomic_write_json, atomic_write_text


class ReleasePublisher:
    """Build releases off-feed, promote them atomically, then switch the current pointer."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.settings.prepare_directories()

    def release_dir(self, release_id: str) -> Path:
        return self.settings.releases_dir / release_id

    def begin(self, release_id: str) -> Path:
        destination = self.release_dir(release_id)
        if destination.exists():
            raise FileExistsError(f"Release already exists: {release_id}")
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".staging-{release_id}-",
                dir=self.settings.releases_dir,
            )
        )
        (staging / "audio").mkdir()
        (staging / "transcripts").mkdir()
        return staging

    def discard(self, staging_dir: Path) -> None:
        """Remove an incomplete build without touching any published release."""

        if self._is_staging_dir(staging_dir):
            shutil.rmtree(staging_dir, ignore_errors=True)

    def write_transcript(
        self,
        release_dir: Path,
        episode: Episode,
        candidate: Candidate | None,
    ) -> None:
        source_html = ""
        if candidate:
            identifiers = []
            if candidate.pmid:
                identifiers.append(f"PMID {html.escape(candidate.pmid)}")
            if candidate.pmcid:
                identifiers.append(f"PMCID {html.escape(candidate.pmcid)}")
            if candidate.doi:
                identifiers.append(f"DOI {html.escape(candidate.doi)}")
            source_html = f"""
            <section>
              <h2>Source</h2>
              <p>{html.escape(candidate.citation_label)}</p>
              <p>Source scope: {html.escape(candidate.source_scope.value.replace("_", " "))}</p>
              <p>{html.escape(" · ".join(identifiers))}</p>
              <p><a href="{html.escape(candidate.source_url, quote=True)}">
              Open source record</a></p>
            </section>
            """

        document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(episode.title)}</title>
  <style>
    body {{ max-width: 48rem; margin: 2rem auto; padding: 0 1rem;
           font: 1.15rem/1.65 system-ui, sans-serif; color: #111; background: #fff; }}
    h1, h2 {{ line-height: 1.2; }}
    .notice {{ padding: 1rem; border: 2px solid #444; border-radius: .5rem; }}
    @media (prefers-color-scheme: dark) {{
      body {{ color: #f7f7f7; background: #111; }}
      a {{ color: #8ecbff; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(episode.title)}</h1>
    <p class="notice">Professional education only. This automated briefing is not
    patient-specific medical advice. Source scope and limitations are stated in the audio.</p>
    <h2>Transcript</h2>
    <p>{html.escape(episode.spoken_script)}</p>
    {source_html}
  </main>
</body>
</html>
"""
        atomic_write_text(
            release_dir / "transcripts" / episode.transcript_filename,
            document,
        )

    def finalize(self, manifest: ReleaseManifest, staging_dir: Path) -> Path:
        if not self._is_staging_dir(staging_dir):
            raise ValueError("finalize requires a release staging directory")

        destination = self.release_dir(manifest.release_id)
        if destination.exists():
            raise FileExistsError(f"Release already exists: {manifest.release_id}")

        history = self._history(
            excluding=manifest.release_id,
            limit=max(0, self.settings.release_retention - 1),
        )
        atomic_write_text(
            staging_dir / "feed.xml",
            build_feed(manifest, self.settings, history=history),
        )
        atomic_write_json(
            staging_dir / "manifest.json",
            manifest.model_dump(mode="json"),
        )
        self._validate_staged_release(manifest, staging_dir)

        # Rename within the releases directory so clients can never observe a partial release.
        staging_dir.replace(destination)

        # The pointer moves only after the complete immutable release is in its final location.
        atomic_write_json(
            self.settings.current_pointer,
            {
                "release_id": manifest.release_id,
                "generated_at": manifest.generated_at.isoformat(),
            },
        )
        self._prune(manifest.release_id)
        return destination

    def current_release_id(self) -> str | None:
        try:
            payload = json.loads(self.settings.current_pointer.read_text("utf-8"))
            return str(payload["release_id"])
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def current_release_dir(self) -> Path | None:
        release_id = self.current_release_id()
        if not release_id:
            return None
        destination = self.release_dir(release_id)
        return destination if destination.is_dir() else None

    def _history(
        self,
        *,
        excluding: str,
        limit: int,
    ) -> tuple[ReleaseManifest, ...]:
        if limit <= 0:
            return ()
        manifests: list[ReleaseManifest] = []
        for path in self.settings.releases_dir.iterdir():
            if not path.is_dir() or path.name == excluding or path.name.startswith("."):
                continue
            try:
                manifests.append(
                    ReleaseManifest.model_validate_json(
                        (path / "manifest.json").read_text("utf-8")
                    )
                )
            except (OSError, ValueError):
                continue
        manifests.sort(key=lambda item: item.generated_at, reverse=True)
        return tuple(manifests[:limit])

    def _prune(self, current_release_id: str) -> None:
        releases = sorted(
            (
                path
                for path in self.settings.releases_dir.iterdir()
                if path.is_dir()
                and not path.name.startswith(".")
                and path.name != current_release_id
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in releases[self.settings.release_retention - 1 :]:
            shutil.rmtree(path, ignore_errors=True)

    def _is_staging_dir(self, path: Path) -> bool:
        try:
            return (
                path.resolve().parent == self.settings.releases_dir.resolve()
                and path.name.startswith(".staging-")
            )
        except OSError:
            return False

    @staticmethod
    def _validate_staged_release(
        manifest: ReleaseManifest,
        staging_dir: Path,
    ) -> None:
        required = [staging_dir / "feed.xml", staging_dir / "manifest.json"]
        for episode in manifest.episodes:
            audio = staging_dir / "audio" / episode.audio_filename
            transcript = staging_dir / "transcripts" / episode.transcript_filename
            required.extend((audio, transcript))
            if audio.is_file() and audio.stat().st_size != episode.audio_size:
                raise RuntimeError(
                    f"Audio size mismatch for {episode.audio_filename}: "
                    f"{audio.stat().st_size} != {episode.audio_size}"
                )

        missing = [path.relative_to(staging_dir) for path in required if not path.is_file()]
        if missing:
            raise RuntimeError(
                "Release is incomplete: " + ", ".join(str(path) for path in missing)
            )
