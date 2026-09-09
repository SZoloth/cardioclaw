# V5 implementation status

**Status date:** August 28, 2026  
**Branch:** `feat/podcast-first-v5`  
**Live deployment:** unchanged V4 Oracle service

## Implemented on the V5 branch

- Upstream V4 history and an explicit archive branch
- Typed candidate, summary, episode, and release contracts
- Structured PubMed retrieval rather than concatenated plain-text abstracts
- Supplemental journal RSS and narrowly filtered society news
- PMID, DOI, and title deduplication
- Deterministic nuclear-cardiology-first selection
- Optional PubMed Central full-text enrichment
- Claude JSON-schema output restricted to selected sources
- Candidate identity, source-scope, omission, duplicate, and numeric-token checks
- One natural-TTS overview episode plus one episode per paper
- Content-addressed audio filenames and stable period/paper GUIDs
- Accessible HTML transcripts and source pages
- Private tokenized RSS, media, transcript, and artwork routes
- HEAD and byte-range support through Flask
- Immutable release directories and an atomic current-release pointer
- Retained prior releases in the active feed
- CLI commands for plan, generate, validate, serve, and voice audition
- Docker, systemd, Caddy, CI, tests, and deployment documentation
- Compatibility wrappers for the existing V4 cron and gunicorn commands

## Not yet validated

- A real paid Claude structured-output call against the current account
- A real OpenAI TTS run with the pinned voice/model configuration
- A full weekly run against live PubMed, PMC, and RSS sources
- Apple Podcasts ordering and continuous playback on Andrew’s phone
- Overcast next/previous episode behavior
- Voice and medical-term pronunciation comfort
- Two consecutive scheduled parallel releases
- Migration from Oracle or replacement of the current feed

## Explicitly not implemented

- Paywall or institutional-proxy automation
- Patient data or patient-specific clinical advice
- Independent second-model claim audit
- Retraction/correction monitoring
- Figure and complex-table understanding
- Live conversational questions
- Custom iOS playback software

## Merge and deployment gates

1. GitHub CI passes on all supported Python versions.
2. `cardioclaw plan` returns a sensible nuclear-first portfolio.
3. A real generation produces valid audio, transcripts, manifest, and feed.
4. Feed validates and supports HEAD/range requests over HTTPS.
5. Apple Podcasts and Overcast preserve overview → paper 1 → paper 2 order.
6. Andrew completes start, next, previous, pause, resume, rewind, and offline playback without sighted help.
7. Two weekly V5 runs succeed beside the untouched V4 feed.
8. Steve reviews operational migration and rollback instructions.

Until these gates pass, V5 is an evaluation build rather than the production briefing.
