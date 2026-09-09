# Accessibility and podcast-control test plan

## Goal

Confirm that Andrew can receive and navigate the weekly briefing using Siri and standard podcast controls without depending on a custom application.

## Test clients

Test both:

- Apple Podcasts
- Overcast

Record iPhone model, iOS version, podcast-app version, AirPods/headphones, and whether VoiceOver is enabled.

## Setup

1. Follow the V5 feed by URL.
2. Enable automatic downloads.
3. Keep played episodes long enough for replay.
4. Enable continuous playback.
5. Configure headphone controls as Next/Previous if available.
6. Download the current release.
7. Put the phone in airplane mode for the offline portion.

## Critical tasks

The listener should complete these without sighted help:

1. Start the latest Cardiology Report
2. Hear that the first episode is an overview
3. Continue automatically to paper 1
4. Say “next episode” to skip paper 1
5. Say “previous episode” to return
6. Pause and resume
7. Rewind 30 seconds
8. Change playback speed
9. Resume after a phone call
10. Resume after the podcast app is terminated and reopened
11. Play the downloaded release in airplane mode
12. Identify current paper number from the spoken introduction
13. Replay a prior paper
14. Recognize abstract-only versus full-text status

## Success thresholds

- 100% completion of start, next, previous, pause, resume, and offline playback
- No dead air or broken feed after a failed generation
- No dependence on chapter navigation
- No confusion between the overview and paper episodes
- No episode titles that VoiceOver cannot distinguish
- No sighted help during routine weekly use after setup

## Questions after each release

- Were the selected papers worth hearing?
- Was nuclear cardiology sufficiently prioritized?
- Were any summaries too long or too short?
- Were the numbers understandable?
- Which terms were mispronounced?
- Did you want to ask a question during any paper?
- Was next/previous episode sufficient?
- Did continuous playback work?
- Did the natural voice remain comfortable for the full briefing?

## Decision after four weeks

Continue podcast-only if interaction requests are rare. Add a separate source-grounded question interface only if the listener repeatedly needs questions that rewind and show notes cannot answer.
