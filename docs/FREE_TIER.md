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

## Pricing page (confirmed from a screenshot of ai.google.dev/pricing, 2026-11-19)

For `gemini-3.5-flash-lite` on the Standard tab: input and output tokens are "Free of charge" on the free tier; context caching and Google Search/Maps grounding are not available on the free tier; "Used to improve our products": **Yes**. The screenshot did not show request limits.

## Rate limits (reported by the project owner from Google AI Studio, 2026-11-19)

Free tier, `gemini-3.5-flash-lite`: **200 requests per minute, 10,000 requests per day.**

Tokens per minute is reported inconsistently: one place says 10,000,000 TPM and a table says
50,000 TPM. It was not confirmed from an official page. A single 88,654-token baseline request
succeeded on 2026-11-19, so 50,000 is probably not enforced per request, but treat it as unknown.
Source of truth: https://aistudio.google.com/rate-limit and
https://ai.google.dev/gemini-api/docs/rate-limits.

MigrateLens deliberately runs far below the stated request limits:

| Setting | Env var | Default | Stated limit |
|---|---|---|---|
| Requests per minute | `MIGRATELENS_RPM` | 20 | 200 |
| Requests per day (hard stop) | `MIGRATELENS_DAILY_LIMIT` | 500 | 10,000 |

There is no tokens-per-minute guard; a 429 is handled by exponential backoff.

## Data

Free-tier prompts may be used by Google to improve its products, so only public repos and public data are ever sent. No employer code.

## How the limits are enforced in code

- `migratelens/cache.py`: SQLite cache keyed by (prompt, model, tool args); a repeated call costs no quota.
- `migratelens/throttle.py`: RPM throttle, backoff on retryable errors, and a persistent daily counter that raises before the limit.
- State lives in `.migratelens/` (git-ignored).
