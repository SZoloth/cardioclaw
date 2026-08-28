# Deployment and migration

## Principle

Do not modify the working Oracle deployment in place until V5 has run successfully in parallel. The current listener must never lose the last valid feed.

## Recommended target

The existing 503 MB Oracle instance is below the preferred operating margin. V5 no longer needs FFmpeg for routine generation, but modern Python SDKs and generation workloads still benefit from at least:

- 1 GB RAM minimum
- 2–4 GB RAM preferred
- Ubuntu 24.04 or later
- Python 3.12
- HTTPS domain
- Persistent disk for releases

A small Hetzner, DigitalOcean, Fly.io, Render, or similar host is sufficient. The repository does not require Kubernetes.

## Parallel migration

1. Preserve the live V4 machine and feed.
2. Deploy V5 to a new hostname, for example `cardio-v5.example.com`.
3. Configure a new private feed token.
4. Subscribe a test phone to the V5 feed without removing V4.
5. Generate at least two complete weekly releases.
6. Test Apple Podcasts and Overcast.
7. Only then move Andrew to the V5 feed.

## Docker deployment

```bash
cp .env.example .env
# Set production, HTTPS URL, credentials, token, email, and cover path.

docker compose build
docker compose up -d

docker compose exec cardioclaw cardioclaw plan --type weekly
docker compose exec cardioclaw cardioclaw generate --type weekly
docker compose exec cardioclaw cardioclaw validate
```

Place Caddy, nginx, or a managed load balancer in front of the service. Bind the container only to localhost, as the provided Compose file does.

Example Caddy configuration:

```caddy
cardio.example.com {
    reverse_proxy 127.0.0.1:5000
}
```

## systemd deployment

Examples are under `deploy/systemd`.

```bash
sudo cp deploy/systemd/cardioclaw-* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cardioclaw-web.service
sudo systemctl enable --now cardioclaw-generate.timer
```

Set `CARDIOCLAW_DATA_DIR=/var/lib/cardioclaw` in `/etc/cardioclaw.env`. Set the server timezone to `America/New_York` or adjust the timer deliberately.

## Feed compatibility requirements

Before production:

```bash
curl -I "https://HOST/feed/TOKEN.xml"
curl -I "https://HOST/media/TOKEN/RELEASE/FILE.mp3"
curl -H "Range: bytes=0-1023" -I \
  "https://HOST/media/TOKEN/RELEASE/FILE.mp3"
```

Expected:

- HTTPS
- 200 for HEAD
- 206 for byte-range request
- Correct `Content-Length`
- `audio/mpeg`
- Valid XML
- Stable GUIDs
- Unique enclosure URLs

## Scheduling

The V5 systemd timer runs weekly. A successful generation atomically updates `current.json`. If generation fails, the current release does not change.

## Rollback

To return to the original source baseline in this fork:

```bash
git switch archive/v4-oracle-baseline
```

Do not point the new V5 data directory at the old V4 output directory. The formats differ.

To roll back the active V5 release, change `data/current.json` to a retained release ID using an atomic file replacement, then restart the web service.

## Secrets

Never commit:

- Anthropic key
- OpenAI key
- NCBI API key
- Gmail app password
- Private feed token
- Institutional proxy credentials

The feed token is a bearer secret embedded in subscriber URLs. Access logging is disabled in the provided gunicorn service to avoid recording it. Rotate it only with a planned resubscription.
