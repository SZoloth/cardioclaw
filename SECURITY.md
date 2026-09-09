# Security policy

Cardiology Claw is a private-feed professional education tool. Do not report security issues in a public issue if they involve feed tokens, credentials, server addresses, or source-access details.

## Sensitive values

Never commit:

- Anthropic or OpenAI keys
- NCBI API keys
- Private feed tokens
- SMTP credentials
- Institutional proxy or library credentials
- Production `.env` files
- Podcast subscriber URLs
- Downloaded copyrighted full text

## Feed-token model

The private RSS URL is a bearer credential. Anyone who knows the full URL can retrieve the feed, audio, and transcripts.

Mitigations:

- Use at least 32 random bytes
- Use HTTPS
- Do not expose the token in logs
- Return 404 rather than 401 for invalid tokens
- Rotate only with a planned subscriber migration
- Keep the content free of PHI and patient-specific information

## Reporting

Report vulnerabilities privately to the repository owner. Include:

- Affected commit
- Reproduction steps
- Potential impact
- Whether any credential or feed URL was exposed

## Scope boundary

The repository must not ingest patient data, produce patient-specific recommendations, bypass publisher access controls, or silently publish source-unsupported medical claims.
