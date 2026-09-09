# Cardiology Report — iPhone setup

## For the listener’s helper

Cardiology Report is a private weekly podcast. Once it is configured, the listener should be able to use ordinary Siri and podcast controls without opening a custom application.

Each weekly release contains:

1. A short overview episode with all headlines
2. One separate episode per paper

“Next episode” skips the current paper. Continuous playback proceeds through the papers in order.

## Before you begin

Ask the operator for the private feed URL. It will resemble:

```text
https://cardio.example.com/feed/LONG_PRIVATE_TOKEN.xml
```

Treat the full URL as a password. Do not post it, email it broadly, or put it in a public issue.

## Apple Podcasts

1. Open **Podcasts**.
2. Open **Library**.
3. Tap the **More** button.
4. Tap **Follow a Show by URL**.
5. Paste the private feed URL.
6. Tap **Follow**.
7. Open **Cardiology Report** under Library → Shows.

Recommended settings:

- Automatically download new episodes
- Keep enough played episodes for replay
- Enable continuous playback
- Set headphone controls to Next/Previous where available

## Overcast

1. Install and open **Overcast**.
2. Tap **Add Podcast** or the plus button.
3. Choose **Add URL**.
4. Paste the private feed URL.
5. Add **Cardiology Report**.
6. Enable Voice Boost if it improves clarity.
7. Treat Smart Speed as optional; it may compress intentional pauses around numbers.

## Siri commands to test

Apple Podcasts:

```text
“Siri, play the latest episode of Cardiology Report.”
“Siri, play the next episode.”
“Siri, play the previous episode.”
“Siri, pause.”
“Siri, continue playing podcast.”
“Siri, rewind 30 seconds.”
“Siri, skip ahead two minutes.”
“Siri, play this at one and a half speed.”
```

Podcast-app-specific wording may vary. Test the exact phrases on the listener’s phone and record the phrases that work reliably.

## What the listener should hear

The overview identifies:

- Date range
- Number of paper episodes
- Number focused on nuclear cardiology
- A headline for every paper

Each paper episode announces:

- Paper number and total
- Headline
- Why it matters
- Structured summary
- Limitations
- Whether the source was full text, abstract only, or an RSS snippet
- Journal and identifiers when available
- A reminder that “next episode” moves to the next paper

## Offline test

1. Download the complete release.
2. Enable airplane mode.
3. Start the overview.
4. Confirm continuous playback.
5. Confirm next and previous episode.
6. Confirm pause, resume, and rewind.

Do not switch the listener away from the existing V4 feed until the V5 feed passes this test for at least two weekly releases.

## Troubleshooting

### The feed will not follow

- Confirm the entire tokenized URL was copied.
- Confirm it begins with `https://` in production.
- Open the URL in Safari and verify that XML loads.
- Ask the operator to check `/healthz`.

### An episode will not play

- Confirm the server supports HEAD and byte-range requests.
- Refresh the show.
- Confirm the episode enclosure URL is unique.
- Confirm the audio file exists in the active immutable release.

### “Next episode” does not move to the next paper

- Confirm the release contains separate paper episodes rather than one combined MP3.
- Enable continuous playback.
- Check podcast-app headphone-control settings.
- Test Apple Podcasts and Overcast separately.

### New episodes do not appear

- Pull down to refresh the show.
- Confirm the weekly generation succeeded.
- Confirm the feed’s current release pointer changed.
- Confirm GUIDs did not collide with a prior week.
