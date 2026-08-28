# V4 source notes

These notes preserve the product framing from Steve Zoloth’s July 22, 2026 project summary without copying live credentials or the old public feed address.

## Original product

Cardiology Claw V4 was an automated weekly nuclear cardiology audio briefing for Andrew, a blind retired cardiologist.

The working system:

- Ran from a small Oracle Cloud Ubuntu instance
- Used a Python script on a Monday cron schedule
- Queried PubMed for nuclear and general cardiology
- Read a limited set of journal and Google News RSS feeds
- Used Claude Sonnet 4.6 for headline and abstract-style summaries
- Used OpenAI `gpt-4o-mini-tts` with the `nova` voice
- Combined audio with FFmpeg
- Served an RSS feed through Flask and gunicorn
- Delivered the briefing through Overcast and Apple Podcasts
- Included backup/restore behavior and optional email alerts

## Validated strengths

- Weekly automation worked
- PubMed retrieval worked
- Natural TTS was acceptable
- The RSS feed was subscribable
- Existing podcast and Siri controls were usable
- Backup/restore protected the listener from an empty feed

## Problems identified by the original project

1. Nuclear cardiology was not reliably prioritized.
2. One combined MP3 prevented useful next/previous navigation.
3. Several journal sites blocked the Oracle datacenter IP.
4. The 503 MB Oracle instance was unstable.
5. The model returned a variable number of findings.
6. Email alerts were not fully configured.
7. PMC full-text retrieval was not implemented.
8. A server migration might be required.

## V5 response

| V4 problem | V5 response |
|---|---|
| Model selected the mix | Deterministic code selects and orders candidates |
| One combined MP3 | Overview plus one episode per paper |
| Blocked journal sites | PubMed is primary; RSS is supplemental |
| Server instability | No FFmpeg assembly; containerized deployment; immutable releases |
| Variable findings | Publish only eligible quality items up to the maximum |
| Fragile model formatting | Claude structured JSON output |
| Abstract/full-text ambiguity | Explicit source scope and optional PMC enrichment |
| Failed run could disrupt feed | Atomic current-release pointer |
| Hardcoded IP and paths | Environment-driven HTTPS deployment |

The V4 Oracle baseline remains preserved in branch `archive/v4-oracle-baseline`.
