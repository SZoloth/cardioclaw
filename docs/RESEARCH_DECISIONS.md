# Research decisions

**Reviewed:** August 28, 2026

## Use the podcast platform rather than rebuilding playback

Apple Podcasts supports following a valid show by URL, automatic downloads, offline listening, Siri playback controls, playback speed, and next-episode behavior. The product should therefore invest in evidence selection and audio quality rather than duplicating mature media controls.

Official references:

- Apple Podcasts RSS requirements: https://podcasters.apple.com/support/823-podcast-requirements
- Add a show by URL: https://support.apple.com/guide/iphone/find-podcasts-iph19bb8e705/ios
- Siri podcast controls: https://support.apple.com/guide/iphone/play-music-and-podcasts-with-siri-iph905254b46/ios
- Episode ordering: https://podcasters.apple.com/support/3143-how-to-set-the-order-of-podcast-episodes
- Stable episode GUID guidance: https://podcasters.apple.com/support/3965-how-to-change-hosting-providers

## Feed requirements implemented

Apple’s current requirements emphasize:

- RSS 2.0
- Publicly addressable feed URL
- HTTP HEAD and byte-range support
- Unique enclosure URL per episode
- Stable, globally unique GUID
- RFC 2822 dates
- Artwork
- ASCII-safe filenames and URLs

V5 uses a long token in an otherwise publicly reachable HTTPS URL rather than HTTP Basic authentication, which podcast clients handle inconsistently. The feed is marked episodic because it is a recurring news briefing; distinct publication times order the overview first and the paper episodes after it.

## Structured summaries

Anthropic structured outputs constrain JSON to a supplied schema through `output_config.format`. V5 uses structured output to require identity, source scope, headline, spoken summary, limitations, and pronunciation fields.

Reference:

- https://platform.claude.com/docs/en/build-with-claude/structured-outputs

Structured output guarantees shape, not factual correctness. V5 separately checks candidate identity, source-scope consistency, omission/duplication, and numeric-token support.

## TTS

V5 retains OpenAI `gpt-4o-mini-tts` because the existing system already produces acceptable natural audio and the model supports speech-generation instructions. The provider is isolated behind a renderer so a future blind listening bakeoff can compare other voices.

Reference:

- https://developers.openai.com/api/docs/models/gpt-4o-mini-tts

## Why no NotebookLM dependency

Notebook-style audio is useful as a benchmark or optional weekly format, but the primary briefing needs deterministic ordering, exact source scope, stable per-paper episodes, and explicit validation before publication. The canonical pipeline therefore generates its own verified script before TTS.
