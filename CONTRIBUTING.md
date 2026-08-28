# Contributing

## Product invariants

1. Routine weekly publication is autonomous; no hidden human editor is required.
2. Nuclear cardiology prioritization is deterministic and inspectable.
3. Language models summarize only selected source packets.
4. Full text, abstract-only, and RSS-snippet scopes remain distinct.
5. Unsupported numbers cause failure, not publication.
6. A failed run cannot replace the last valid feed.
7. Every paper remains independently navigable as a podcast episode.
8. No patient data, patient-specific guidance, or paywall bypass.
9. The upstream V4 history remains preserved.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
make check
```

Tests must not make live model calls. Use injected fake summarizers and audio renderers.

## Pull requests

State:

- Listener outcome
- Selection-policy changes
- Source-scope implications
- Podcast-order or GUID changes
- Failure and rollback behavior
- Tests added
- Whether the V4 deployment is affected

Do not merge a feed-format or episode-order change without testing in both Apple Podcasts and Overcast.
