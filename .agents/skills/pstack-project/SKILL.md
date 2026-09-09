---
name: pstack-project
description: Apply pstack to Cardiology Claw V5 engineering while protecting the working V4 deployment and separating offline tests from paid generation and blind-listener acceptance.
---

# Cardiology Claw engineering

Read AGENTS.md and README.md before work. Use `/Users/samzoloth/.codex/skills/pstack-workflow/SKILL.md`. Preserve the current V4 service, source-scope rules and V5 branch boundaries.

## Verification routes

Use the existing project environment. Run `.venv/bin/python -m pytest --cov=cardioclaw --cov-report=term-missing --cov-fail-under=75` for the repository gate, plus the lint/compile checks listed in AGENTS.md. Use `.venv/bin/cardioclaw --help` for the installed CLI doctor. Help and imports are a doctor, not briefing proof.

| User workflow | Source route | Required evidence |
| --- | --- | --- |
| Select relevant source papers | `cardioclaw plan --type weekly`, only in an authorized live retrieval | Selection reasons, source depth and deduplicated paper identity. Offline fixtures do not prove current selection quality. |
| Generate and publish an immutable release | Existing generation/publication tests | Numeric reconciliation, artifact integrity and failure preservation; real model/TTS generation is separately paid and gated. |
| Listen through a private podcast client | AGENTS.md live validation sequence | Overview-first ordering, HEAD/ranges, continuous play, Siri controls and offline playback, verified in actual clients. |

Do not run `generate`, `voice-sample`, `serve`, Docker deployment or any V4 migration as a setup test. Preserve private feed tokens, URLs, audio and credentials. Save only synthetic test evidence, command results and the tested revision. No unit-test total establishes voice quality, provider compatibility, clinical correctness or intended-listener accessibility.
