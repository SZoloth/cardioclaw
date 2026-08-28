# Codex handoff: live V5 validation

Use this document when opening `SZoloth/cardioclaw` in the Codex app or Codex CLI. The repository implementation and CI are already green; this handoff covers the work that requires a real local environment, secrets, network access, podcast clients, and eventually server access.

## Recommended execution environment

Use the **Codex app or Codex CLI on a trusted Mac** for the first live validation. This keeps provider credentials in a local untracked `.env`, lets Codex run the repository and inspect generated audio, and avoids placing SSH credentials or private feed tokens in chat or GitHub.

Cloud Codex is suitable for code changes and ordinary tests, but local Codex is preferred for paid API calls, audio-file review, localhost feed testing, and SSH deployment.

## Inputs the operator must supply locally

Copy `.env.example` to `.env` and set:

- `CARDIOCLAW_NCBI_EMAIL`
- `CARDIOCLAW_NCBI_API_KEY` when available
- `CARDIOCLAW_ANTHROPIC_API_KEY`
- `CARDIOCLAW_OPENAI_API_KEY`
- A newly generated `CARDIOCLAW_FEED_TOKEN`
- Local development paths and URL values

Do not paste these values into Codex prompts, GitHub comments, issues, commits, or test logs. Let Codex read the local environment when running approved commands.

The Oracle SSH key is not required for the first four phases below. Provide server access only after the local feed passes.

## Codex starting prompt

```text
Open AGENTS.md and docs/CODEX_HANDOFF.md first. Work on feat/podcast-first-v5. Do not merge or deploy over V4. Validate the V5 pipeline in phases, stop on each failed gate, preserve all source-scope and atomic-publication checks, and report exact commands, outputs, generated artifact paths, costs where observable, and anything that still requires a person or iPhone.
```

## Phase 1 — environment and repository verification

```bash
git fetch origin
git switch feat/podcast-first-v5
git pull --ff-only

python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"

python -m compileall -q cardioclaw cardio_claw.py serve.py
ruff check .
pytest --cov=cardioclaw --cov-report=term-missing --cov-fail-under=75
```

Expected result: all repository checks pass before any paid call.

## Phase 2 — live source and selection plan

```bash
cardioclaw plan --type weekly
```

This should not call Claude or OpenAI TTS. Save the output to a private local file and review:

- Nuclear-cardiology-first ordering
- Official and PubMed sources ahead of weak RSS/news items
- No duplicate PMID, DOI, or normalized title
- Sensible evidence-type ranking
- Correct full-text, abstract-only, or RSS-snippet scope
- No suspiciously old or irrelevant items

Do not continue if the portfolio is poor. Fix and test deterministic discovery/selection first.

## Phase 3 — TTS voice audition

```bash
cardioclaw voice-sample --output voice-sample.mp3
```

Listen on the intended iPhone or headphones. Record:

- Naturalness over several minutes
- Nuclear-cardiology terminology
- Drug, investigator, trial, society, and journal pronunciation
- Percentages, confidence intervals, hazard ratios, dates, and abbreviations
- Pace and listening fatigue

Change only voice and speech instructions at this stage; do not alter evidence content to hide pronunciation problems.

## Phase 4 — first full local release

```bash
cardioclaw generate --type weekly
cardioclaw validate
cardioclaw serve
```

Verify locally:

```bash
curl -I "http://127.0.0.1:5000/feed/<local-feed-token>.xml"
curl "http://127.0.0.1:5000/feed/<local-feed-token>.xml" > /tmp/cardioclaw-feed.xml
```

Inspect the generated manifest, RSS, transcripts, and audio files. Confirm:

- One overview plus one episode per selected paper
- Overview-first publication ordering
- Stable unique GUIDs and unique enclosure URLs
- Accurate media sizes and durations
- Accessible transcript/source pages
- Explicit source-scope disclosure in each paper episode
- No unsupported numeric token
- Private token required for feed and media
- A deliberately failed generation does not move the current pointer

## Phase 5 — HTTPS and podcast-client pilot

Use a separate V5 hostname or server and a new private feed token. Do not reuse Andrew's V4 URL.

Test the private HTTPS feed in Apple Podcasts and Overcast:

- Feed subscribes successfully
- Artwork and episode metadata load
- Overview appears first
- Continuous play moves to paper 1, then paper 2
- “Next episode” moves between papers
- “Previous episode” returns to the prior paper
- HEAD, seeking, and byte-range playback work
- Episodes download and play in airplane mode
- Transcript/source links open with VoiceOver

## Phase 6 — no-screen listener test

Andrew should attempt, without sighted assistance:

1. Start the latest briefing with Siri
2. Pause and resume
3. Rewind 30 seconds
4. Advance to the next paper
5. Return to the previous paper
6. Change playback speed
7. Resume after a phone interruption
8. Download and listen offline
9. Identify the current paper from spoken episode metadata
10. Find a transcript or source link when needed

Record task completion, time, errors, and any sighted assistance. Do not infer success from simulator or helper operation.

## Phase 7 — parallel server deployment

Only after Phases 1–6 pass, provide Codex with access to a reviewed server environment. Follow `docs/DEPLOYMENT.md` and deploy V5 with separate:

- Hostname or external port
- Systemd service and timer names
- Data directory
- Environment file
- Feed token and URL
- Caddy configuration

Keep V4 running. Require two successful scheduled V5 releases before considering migration.

## Human-only approvals

Codex can execute and document the pipeline, but these decisions still require people:

- Andrew approves voice, pacing, usefulness, and independent operation
- Steve approves server migration and rollback
- Sam approves PR merge after all gates are evidenced

## Merge rule

Do not mark PR #1 ready or merge it merely because CI is green. Update the PR checklist with evidence from each completed phase. Merge only after the local provider run, podcast-client behavior, no-screen test, parallel scheduled runs, and Steve review are complete.