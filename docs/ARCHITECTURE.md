# Architecture and reuse guide

MigrateLens is one agent (AWS → Google Cloud migration planning) built on a small set of components that
another team could reuse for a different agent. This document says which parts are reusable as-is, which need
a small refactor, and which are specific to migration. The code snippets below are executed by
`tests/test_docs_snippets.py`, so they cannot silently rot.

## Request flow

1. `repo_reader` lists and reads files from the target repo. It is read-only, size-capped (5 MB of text),
   skips binaries, and blocks symlinks and path traversal. Repo content is treated as data, never instructions.
2. `detector` finds AWS usage deterministically (no LLM) and returns `{service, evidence: [{file, line, snippet}], confidence}`.
3. `mapper` looks services up in `data/mapping.yaml`, the single source of truth for allowed AWS → GCP pairs.
4. The ADK agent (`agent.py`) calls those tools **through an MCP server** (`mcp_server.py`) and drafts a plan.
5. The guardrail (`guardrail.py`) checks the draft in code. On failure, `pipeline.py` sends the specific
   violations back for a revision (at most 2). If it still fails, the result is `could_not_verify` with every
   rejection listed, and no artifacts are written.
6. For a verified plan, `generators.py` writes Terraform, a Dockerfile and a CI file from templates (the model
   only fills app-specific values such as port and start command), and `validate.py` runs
   `terraform init -backend=false` and `terraform validate`. Nothing is applied.

The loop is bounded: model calls per turn, total tokens and wall time are capped, and every run ends with an
explicit `stop_reason`. A JSONL trace and `result.json` are written per run.

## What is reusable

| Component | Status | Notes |
|---|---|---|
| `cache.py`: SQLite response cache keyed by (prompt, model, tool args) | Reusable as-is | Knows nothing about migration. |
| `throttle.py`: RPM throttle, exponential backoff, persistent daily budget | Reusable as-is | Works with any rate-limited API. |
| `agent.ModelHooks`: cache + budget + throttle as ADK model callbacks | Reusable for any ADK agent | Sequential use only (one pending request at a time). |
| `tools/repo_reader.py`, `tools/toolset.py`, `mcp_server.py`: read-only tools served over MCP | Reusable pattern | `make_tools(root)` returns plain functions that back both MCP and direct calls. |
| `guardrail.py` result types (`Violation`, `GuardrailResult`) | Reusable as-is | The checks inside `check_plan` are migration-specific. |
| `pipeline.py` bounded draft → check → revise loop | Needs a small refactor | The shape is generic, but it is currently coupled to `detect_repo` and the generators. |
| `eval/metrics.py`: `prf`, `bootstrap_ci`, `mean` | Reusable as-is | The service, mapping and risk scorers are migration-specific. |
| `eval/run_eval.py` replay-only runner | Reusable pattern | Default is zero API calls from a committed cache; `--record` allows live calls. |
| `data/mapping.yaml`, `detector.py`, `generators.py` | Migration-specific | This is where another agent's domain logic would go. |

## Reusing the cache, throttle and budget around any model call

```python
from migratelens.cache import Cache, make_key
from migratelens.throttle import DailyBudget, RetryableError, RpmThrottle, with_backoff

cache = Cache(".state/cache.sqlite")
throttle = RpmThrottle(rpm=20)
budget = DailyBudget(limit=500, path=".state/budget.json")


def my_api(prompt):  # stand-in for any rate-limited API
    return prompt.upper()


def call_model(prompt):
    key = make_key(prompt, model="my-model")
    if (hit := cache.get(key)) is not None:
        return hit["text"]
    budget.consume()  # raises DailyBudgetExceeded before the real limit
    throttle.wait()  # blocks to stay under the requests-per-minute limit
    text = with_backoff(
        lambda: my_api(prompt), is_retryable=lambda e: isinstance(e, RetryableError)
    )
    cache.set(key, {"text": text})
    return text


assert call_model("hi") == "HI"
assert call_model("hi") == "HI"  # second call is served from the cache
assert cache.hits == 1
```

## Writing a guardrail for a different agent

Keep the checks in code and return the shared result type. The retry loop only needs `result.ok` and
`result.feedback()`.

```python
from migratelens.guardrail import GuardrailResult, Violation


def check_report(text: str, allowed_terms: set[str]) -> GuardrailResult:
    mentioned = {t for t in ("Alpha", "Beta") if t in text}
    violations = [
        Violation("unknown_term", t, "not in the allowlist") for t in mentioned - allowed_terms
    ]
    return GuardrailResult(violations, items_checked=len(mentioned))


result = check_report("Alpha and Beta", {"Alpha"})
assert not result.ok and "Beta" in result.feedback()
```

## Exposing read-only tools over MCP

```python
from mcp.server.mcpserver import MCPServer

from migratelens.tools.toolset import make_tools

server = MCPServer("my-repo-tools")
for fn in make_tools(".").values():
    server.tool()(fn)
```

For a different domain, replace `make_tools` with your own functions (plain Python with type hints and
docstrings) and keep the pattern: the repo root is fixed when the server starts, so a client cannot read outside it.

## Evaluation harness pattern

- Ground truth is hand-written JSON per case with a `human_reviewed` flag; results are only reported as final once it is true.
- `eval/run_eval.py` runs the agent and a no-tools baseline on the same cases, writes one JSON per case, and
  `eval/report.py` builds every table and the README results block from those files, so the numbers cannot be
  typed by hand.
- Runs replay from `eval/cache.sqlite` by default, so anyone can reproduce the tables with zero API calls.
- Report small-sample caveats: `bootstrap_ci` gives wide intervals at n=7, and the report says so.

## Free-tier protections

See [`FREE_TIER.md`](FREE_TIER.md). In short: cache first, then daily budget, then RPM throttle, then SDK-level
backoff on 429/503. The Streamlit demo adds a per-session cap and a whole-app daily cap on live runs.
