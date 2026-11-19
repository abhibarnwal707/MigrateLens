# Free-tier notes

Checked: 2026-11-19. No billing account is attached and none will be.

## Model

Default: `gemini-3.5-flash-lite` (override with `MIGRATELENS_MODEL`).

Probed with the project's real AI Studio key on 2026-11-19 (`generate_content`, one tiny prompt each):

| Model | Result |
|---|---|
| `gemini-3.5-flash-lite` | works |
| `gemini-3.1-flash-lite` | works |
| `gemini-3.5-flash` | 503 "high demand" (transient) |
| `gemini-3.8-flash` | 503 "high demand" (transient) |
| `gemini-2.5-flash`, `gemini-2.5-flash-lite` | 404, "no longer available to new users" |

The code retries on 429, 500 and 503 with exponential backoff.

## Rate limits: NOT yet confirmed from an official source

Third-party articles disagree, and some report free-tier Flash as low as 5 requests per minute and 20 per day, while older guides say 10-15 RPM and 1,500 RPD. Limits are per project and change often.

**Source of truth:** the rate-limit panel for your project at https://aistudio.google.com/rate-limit and the docs at https://ai.google.dev/gemini-api/docs/rate-limits.

Until those numbers are filled in below, the code uses conservative defaults:

| Setting | Env var | Default |
|---|---|---|
| Requests per minute | `MIGRATELENS_RPM` | 5 |
| Requests per day (hard stop) | `MIGRATELENS_DAILY_LIMIT` | 15 |

Confirmed limits for `gemini-3.5-flash-lite` (fill in from AI Studio): RPM = ___, TPM = ___, RPD = ___

## Data

Free-tier prompts may be used by Google to improve its products, so only public repos and public data are ever sent. No employer code.

## How the limits are enforced in code

- `migratelens/cache.py`: SQLite cache keyed by (prompt, model, tool args); a repeated call costs no quota.
- `migratelens/throttle.py`: RPM throttle, backoff on retryable errors, and a persistent daily counter that raises before the limit.
- State lives in `.migratelens/` (git-ignored).
