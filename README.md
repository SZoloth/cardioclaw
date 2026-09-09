# Cardiology Claw

Podcast-first, automated nuclear cardiology briefings for a blind retired cardiologist.

This repository is a fork of Steve Zoloth’s working V4 system. The original Oracle-server implementation is preserved in Git history and on the branch `archive/v4-oracle-baseline`. V5 keeps the proven workflow—PubMed, AI summarization, natural TTS, RSS delivery, Siri, and ordinary podcast controls—while making selection, source identity, episode navigation, publishing, and operations substantially more dependable.

## Product goal

The listener should need almost no new behavior:

> “Siri, play the latest episode of Cardiology Report.”

The podcast app handles play, pause, resume, rewind, speed, downloads, AirPods, lock screen, Apple Watch, CarPlay, and offline listening. Cardiology Claw focuses on the custom work:

```text
official sources
→ deterministic nuclear-cardiology-first selection
→ full-text lookup when legally available
→ source-constrained structured summaries
→ natural speech
→ overview episode + one episode per paper
→ private RSS feed
```

## V5 changes

### Navigable podcast structure

Each weekly release contains:

1. One short overview episode with every headline
2. One self-contained episode per selected paper

“Next episode” therefore skips the current paper rather than moving within one long MP3. Continuous playback can advance through the briefing in order.

### Deterministic selection

The language model no longer chooses which sources enter the briefing. Code:

- Deduplicates by PMID, DOI, or normalized title
- Scores official PubMed records above RSS and secondary news
- Prioritizes guidelines, randomized trials, and meta-analyses
- Reserves the first positions for nuclear cardiology when enough candidates exist
- Uses Google News only for relevant ASNC, SNMMI, regulatory, or society announcements
- Does not pad a weak week with low-quality items merely to reach eight

### Source-bounded summaries

Claude receives only the already selected source packets. Structured output requires each summary to point to a selected `candidate_id` and preserve its source scope.

Additional checks reject:

- Unknown or duplicated candidate IDs
- Omitted selected papers
- A full-text claim when only an abstract or RSS snippet was supplied
- Numeric tokens in the spoken summary that do not occur in the source evidence

### Full-text enrichment

For selected PubMed items, the pipeline checks PubMed Central. When accessible PMC text is available, the summary can use it and says so. Otherwise the episode explicitly says that only the abstract was available.

### Atomic publishing

A complete release is written to an immutable release directory. The public feed changes only after every audio file, transcript, manifest, and feed document succeeds. A failed run leaves the last valid release untouched. Retained prior releases remain in the active feed until pruned.

### Private delivery

The feed and media URLs include a long private token. Production configuration requires HTTPS. Audio filenames are content-addressed, while episode GUIDs remain stable for a given paper and briefing period.

## Quick start

Requirements:

- Python 3.11–3.13
- API credentials for Anthropic and OpenAI
- An operational NCBI contact email

```bash
git clone https://github.com/SZoloth/cardioclaw.git
cd cardioclaw
git switch feat/podcast-first-v5

python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

cp .env.example .env
# Edit .env with credentials and a long random feed token.

pytest
cardioclaw plan --type weekly
cardioclaw generate --type weekly
cardioclaw validate
cardioclaw serve
```

Local private feed:

```text
http://127.0.0.1:5000/feed/<your-token>.xml
```

## Commands

```bash
# Discover, score, and print proposed sources without paid AI or TTS calls.
cardioclaw plan --type weekly

# Generate an immutable weekly release.
cardioclaw generate --type weekly

# Generate a daily briefing using the prior day by default.
cardioclaw generate --type daily

# Validate every artifact in the current release.
cardioclaw validate

# Serve the current private feed.
cardioclaw serve

# Audition the configured TTS voice.
cardioclaw voice-sample --output voice-sample.mp3
```

The legacy Oracle commands still work:

```bash
python cardio_claw.py
gunicorn serve:app
```

They are now compatibility entrypoints into the V5 package. The original V4 files are also preserved under `legacy/` and on the archive branch.

## Configuration

All settings use `CARDIOCLAW_` environment variables. See `.env.example`.

Production invariants:

- `CARDIOCLAW_ENVIRONMENT=production`
- `CARDIOCLAW_PUBLIC_BASE_URL` must be HTTPS
- `CARDIOCLAW_FEED_TOKEN` must not use the development default
- `CARDIOCLAW_NCBI_EMAIL` must be an operational contact
- Secrets remain outside Git

Generate a feed token with:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

## Podcast compatibility

The generated feed follows RSS 2.0 and includes:

- Stable, unique GUIDs
- Unique enclosure URLs, lengths, and MIME types
- RFC 2822 publication dates
- iTunes episode numbers and durations
- An episodic show type, appropriate for a recurring news briefing
- Accessible HTML transcripts
- Tokenized media URLs
- HTTP HEAD and byte-range support through Flask

## Deployment

Do not replace the current Oracle service immediately. Run V4 and V5 side by side until:

- At least two scheduled V5 runs succeed
- The overview and all paper episodes appear in Apple Podcasts and Overcast
- “Next episode” moves between papers
- Continuous playback uses the intended order
- The feed survives a failed generation run
- Andrew can use the critical flow without sighted help

See:

- [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/ACCESSIBILITY_TEST_PLAN.md`](docs/ACCESSIBILITY_TEST_PLAN.md)
- [`docs/RESEARCH_DECISIONS.md`](docs/RESEARCH_DECISIONS.md)
- [`docs/V4_SOURCE_NOTES.md`](docs/V4_SOURCE_NOTES.md)
- [`UPSTREAM.md`](UPSTREAM.md)

## Safety and scope

Cardiology Claw is a professional current-awareness tool, not a clinical decision-support system.

- No patient data or PHI
- No patient-specific recommendations
- No paywall bypass
- No implication of full-text review when only an abstract was available
- No automatic publication when source identity, summary structure, or numeric checks fail
- Routine human curation is not required; the listener or helper may evaluate the product, but the weekly pipeline is autonomous

## Repository status

V5 is an implementation branch under active evaluation. It has not replaced Steve’s deployed V4 feed. The original V4 code and operational history remain recoverable.
