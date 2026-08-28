# V5 architecture

## Product boundary

Cardiology Claw creates a private podcast. The podcast client, not a custom iOS application, owns playback and accessibility controls.

```text
PubMed / PMC / journal RSS / society news
                    ↓
           canonical candidates
                    ↓
      deterministic selection policy
                    ↓
        selected source packets only
                    ↓
       Claude structured summaries
                    ↓
  candidate identity + source-scope + numeric checks
                    ↓
       natural TTS per audio episode
                    ↓
overview + one episode per paper + transcripts
                    ↓
       immutable release + atomic pointer
                    ↓
      private HTTPS RSS and media routes
                    ↓
  Apple Podcasts / Overcast / Siri / AirPods
```

## Why one episode per paper

The V4 system generated a single combined MP3 even though its feed description and setup guide described separate findings. The result was linear listening: podcast clients could rewind or pause, but “next episode” could not skip the current paper.

V5 generates:

- Track 1: weekly overview
- Track 2: paper 1
- Track 3: paper 2
- …
- Final track: final paper

Each paper episode includes its headline, relevance, summary, limitations, source scope, and citation. This makes ordinary podcast controls the navigation interface.

## Candidate lifecycle

### Discovery

- PubMed nuclear-cardiology query
- PubMed high-impact general cardiology query
- Accessible journal RSS feeds
- Narrow society-news feeds

### Deduplication

Priority identifiers:

1. PMID
2. DOI
3. Normalized title

When multiple sources describe the same item, PubMed and more complete evidence scope win.

### Scoring and selection

Selection is code, not prompt language. Inputs include:

- Source authority
- Evidence type
- Nuclear-cardiology relevance
- Source completeness
- Recency
- Secondary-news penalty

The pipeline chooses up to the configured maximum and reserves the first positions for nuclear cardiology when enough eligible items exist.

### Enrichment

Selected PubMed candidates are checked for PMC full text. Full text is used only when available through PMC. Otherwise the abstract remains the evidence boundary.

### Summary

Claude receives the ordered source packets and a JSON Schema. It cannot add or select candidates. The application then validates:

- Every selected candidate is represented once
- No unknown candidate appears
- Source scope matches
- Scientific numeric values are written as digits and occur in the source evidence

### Audio

Each episode is rendered independently. No FFmpeg concatenation is needed. This reduces memory, temporary-file, chapter, and partial-output failures.

### Publication

A release contains:

```text
releases/<release-id>/
  audio/
  transcripts/
  feed.xml
  manifest.json
```

`current.json` points to the active release. The pointer changes only after the release is complete. The active feed includes retained prior releases, and old release directories are pruned according to configuration.

## Failure behavior

| Failure | Result |
|---|---|
| One source feed fails | Other sources continue |
| No eligible candidate | Generation fails; current feed stays unchanged |
| Claude returns malformed output | Generation fails; current feed stays unchanged |
| Claude invents a numeric token | Validation fails; current feed stays unchanged |
| TTS fails on one episode | Generation fails; current feed stays unchanged |
| Feed or transcript write fails | Pointer is not changed |
| Web service restarts | Last current release remains available |

## Future extensions

- Independent second-model claim audit
- Retraction and correction checks
- Evaluation corpus
- TTS provider bakeoff
- Optional weekly two-host journal-club renderer
- Separate live question line if the podcast pilot proves interaction is frequently needed
