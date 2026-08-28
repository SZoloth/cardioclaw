# AGENTS.md

## Mission

Cardiology Claw is a podcast-first, automated nuclear-cardiology briefing for a blind retired cardiologist. Preserve Steve Zoloth's working V4 deployment while validating V5 in parallel. The listener outcome is more important than technical novelty: a private feed that works reliably through Siri, Apple Podcasts or Overcast, AirPods, lock-screen controls, downloads, and offline playback.

## Branch and safety rules

- Work on `feat/podcast-first-v5` or a child branch. Do not push directly to `main`.
- Do not merge PR #1 until its documented live, paid-API, podcast-client, accessibility, and parallel-deployment gates pass.
- Do not modify or deploy over Steve's existing Oracle V4 service.
- Never commit `.env`, API keys, feed tokens, SSH keys, generated private audio, feed URLs, server IP changes, institutional credentials, or copyrighted full text.
- Do not add patient data, PHI, patient-specific recommendations, paywall bypass, or institutional-proxy automation.
- Do not weaken source-scope, candidate-identity, numeric-token, atomic-publication, or private-feed checks to make a demo pass.
- Prefer fewer defensible papers over padding the briefing to a target count.

## Repository setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Real credentials belong only in the untracked local `.env` or a managed secret store.

## Required validation after code changes

```bash
python -m compileall -q cardioclaw cardio_claw.py serve.py
ruff check .
pytest --cov=cardioclaw --cov-report=term-missing --cov-fail-under=75
cardioclaw --help
docker build -t cardioclaw-local .
docker compose --env-file .env.example config --quiet
```

Run the smallest relevant test first, then the complete suite before handing off.

## Live validation sequence

These steps require network access and, after planning, paid provider credentials:

```bash
# No paid AI or TTS call. Inspect selection quality first.
cardioclaw plan --type weekly

# Paid TTS call. Review medical pronunciation and listening quality.
cardioclaw voice-sample --output voice-sample.mp3

# Paid Claude and OpenAI calls. Generates a staged immutable release.
cardioclaw generate --type weekly

# Verify every current-release artifact.
cardioclaw validate

# Serve the private feed locally or behind reviewed HTTPS.
cardioclaw serve
```

Do not expose the local development feed publicly. Production configuration must use HTTPS and a newly generated long feed token.

## Evaluation expectations

For a live weekly plan, record:

- Selected title, journal, date, PMID/PMCID/DOI, evidence type, topic, source scope, score, and selection reasons
- Whether nuclear cardiology leads appropriately
- Whether any duplicated study reports appear
- Whether any RSS or secondary-news item displaced stronger PubMed evidence
- Whether every numerical statement in generated scripts is present in the supplied evidence text

For podcast validation, record:

- Overview-first ordering
- Paper 1 → paper 2 progression
- HEAD and byte-range behavior
- Apple Podcasts continuous play
- Overcast next/previous episode behavior
- Siri start, pause, resume, rewind, next, and previous commands
- Airplane-mode playback after download
- Any sighted assistance required

## Deployment rules

- Deploy V5 at a separate hostname, port, service name, data directory, and private feed URL.
- Keep V4 running and untouched through at least two successful scheduled V5 releases.
- Back up the V4 code, environment, generated feed metadata, and service definitions before any migration.
- Use the deployment and rollback steps in `docs/DEPLOYMENT.md`.
- A failed V5 generation must leave the prior V5 feed and all of V4 unchanged.

## Completion boundary

A green CI run proves repository behavior only. It does not prove provider compatibility, feed-client ordering, voice quality, Siri accessibility, or production reliability. Report each unverified boundary explicitly.