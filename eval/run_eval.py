"""Run and score the agent and the no-tools baseline on the sample apps.

  python -m eval.run_eval --mode agent|baseline|both [--apps a,b] [--record]

Default is REPLAY-ONLY: every model response must already be in eval/cache.sqlite, so a run makes
zero API calls and is reproducible. `--record` allows live calls (still capped by the daily budget).
Per-app results land in eval/results/<mode>/<app>.json; `make report` builds the summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time

from eval import baseline
from eval.metrics import (
    EVAL_DIR,
    SCORING_NEUTRAL,
    app_names,
    invented_rate,
    inventory_text,
    load_truth,
    mapping_accuracy,
    prf,
    risk_coverage,
    services_named,
)  # fmt: skip
from migratelens import guardrail
from migratelens.agent import AgentSession, SessionConfig
from migratelens.cache import Cache
from migratelens.llm import LLM
from migratelens.pipeline import run_migration
from migratelens.throttle import DailyBudgetExceeded
from migratelens.tools.detector import detect_repo

CACHE_PATH = EVAL_DIR / "cache.sqlite"


def score(plan: str | None, truth: dict) -> dict:
    text = plan or ""
    neutral = SCORING_NEUTRAL | set(truth["services_out_of_scope"])
    pred = services_named(inventory_text(text), include_generic=True) - neutral
    sp = prf(pred, set(truth["services_in_scope"]) - SCORING_NEUTRAL)
    return {
        "service_precision": sp["precision"], "service_recall": sp["recall"],
        "service_fp": sp["fp"], "service_fn": sp["fn"],
        "mapping_accuracy": mapping_accuracy(text, truth)["accuracy"],
        "mapping_wrong": mapping_accuracy(text, truth)["wrong"],
        "risk_coverage": risk_coverage(text, truth)["coverage"],
        "risks_missed": risk_coverage(text, truth)["missed"],
    }  # fmt: skip


def _rate(violations: int, items: int) -> float:
    return violations / items if items else 0.0


def _previous(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


async def run_agent(app: str, record: bool) -> dict:
    truth, repo = load_truth(app), EVAL_DIR / "apps" / app
    out_dir = EVAL_DIR / "runs" / app
    path = EVAL_DIR / "results" / "agent" / f"{app}.json"
    cfg = SessionConfig(replay_only=not record)
    session = AgentSession(repo, cfg, cache=Cache(CACHE_PATH))
    try:
        res = await run_migration(repo, out_dir, session)
    finally:
        await session.close()
    row = {"app": app, "mode": "agent", "human_reviewed": truth["human_reviewed"],
           "verdict": res.verdict, "stop_reason": res.stop_reason, "retries": res.retries,
           "first_draft_violations": res.first_draft_violations,
           "first_draft_items": res.first_draft_items,
           "invented_rate": _rate(res.first_draft_violations, res.first_draft_items),
           "rejections": res.rejections, "llm_calls": res.llm_calls, "tokens": res.tokens,
           "terraform_ok": None if res.terraform is None else res.terraform["ok"],
           **score(res.plan, truth)}  # fmt: skip
    if record:
        row["wall_seconds"] = res.wall_seconds  # live timing only; replay is not a timing
        row["api_calls_in_recorded_run"] = res.api_calls
    else:
        old = _previous(path)
        row["wall_seconds"] = old.get("wall_seconds")
        row["api_calls_in_recorded_run"] = old.get("api_calls_in_recorded_run")
        row["replay_api_calls"] = res.api_calls
    return row


def run_baseline(app: str, record: bool) -> dict:
    truth, repo = load_truth(app), EVAL_DIR / "apps" / app
    path = EVAL_DIR / "results" / "baseline" / f"{app}.json"
    prompt, truncated = baseline.build_prompt(repo)
    llm = LLM(cache=Cache(CACHE_PATH), replay_only=not record)
    start = time.monotonic()
    r = llm.generate(prompt, tool_args={"purpose": "baseline"})
    inv = detect_repo(repo)
    g = guardrail.check_plan(r.text, inv, repo)
    row = {"app": app, "mode": "baseline", "human_reviewed": truth["human_reviewed"],
           "truncated": truncated, "tokens": r.tokens, "retries": 0, "llm_calls": 1,
           "first_draft_violations": len(g.violations), "first_draft_items": g.items_checked,
           "invented_rate": invented_rate(g.violations, g.items_checked),
           "violation_kinds": sorted({v.kind for v in g.violations}),
           "violations": [{"kind": v.kind, "item": v.item} for v in g.violations],
           **score(r.text, truth)}  # fmt: skip
    if record and not r.cached:
        row["wall_seconds"] = round(time.monotonic() - start, 2)
    else:
        row["wall_seconds"] = _previous(path).get("wall_seconds")
    return row


def _summary(row: dict) -> str:
    return (
        f"verdict={row.get('verdict', '-')} P={row['service_precision']:.2f} "
        f"R={row['service_recall']:.2f} map={row['mapping_accuracy']:.2f} "
        f"risk={row['risk_coverage']:.2f} invented={row['invented_rate']:.2f}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["agent", "baseline", "both"], default="both")
    ap.add_argument("--apps", default="")
    ap.add_argument("--record", action="store_true", help="allow live API calls")
    a = ap.parse_args()
    apps = a.apps.split(",") if a.apps else app_names()
    modes = ["agent", "baseline"] if a.mode == "both" else [a.mode]
    for mode in modes:
        (EVAL_DIR / "results" / mode).mkdir(parents=True, exist_ok=True)
        for app in apps:
            path = EVAL_DIR / "results" / mode / f"{app}.json"
            try:
                row = (
                    asyncio.run(run_agent(app, a.record))
                    if mode == "agent"
                    else run_baseline(app, a.record)
                )
            except DailyBudgetExceeded as exc:
                print(f"[{mode}] {app}: STOPPED, {exc}")
                break
            except RuntimeError as exc:
                if "replay_only" in str(exc):
                    print(f"[{mode}] {app}: not recorded yet (run with --record)")
                    continue
                raise
            if row.get("stop_reason") in ("budget_exhausted", "error", "timeout", "llm_call_limit"):
                print(f"[{mode}] {app}: stopped ({row['stop_reason']}); not saved as a result")
                if row["stop_reason"] == "budget_exhausted":
                    break
                continue
            path.write_text(json.dumps(row, indent=2))
            print(f"[{mode}] {app}: {_summary(row)}")


if __name__ == "__main__":
    main()
