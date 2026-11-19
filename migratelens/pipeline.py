"""End-to-end run: agent drafts a plan -> code-level guardrail -> up to 2 revisions -> artifacts.

Outcome is explicit: verdict 'verified' or 'could_not_verify' (with every rejection listed), plus a
stop_reason. Artifacts are generated and Terraform validated only for a verified plan.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from migratelens.guardrail import GuardrailResult, check_plan
from migratelens.tools.detector import detect_repo
from migratelens.tools.generators import infer_app_spec, write_artifacts
from migratelens.tools.validate import terraform_validate

MAX_RETRIES = 2


class Session(Protocol):
    hooks: object

    async def ask(self, message: str): ...


@dataclass
class RunResult:
    verdict: str  # verified | could_not_verify | stopped
    stop_reason: str
    plan: str | None
    retries: int
    first_draft_violations: int
    first_draft_items: int
    rejections: list[list[dict]] = field(default_factory=list)  # violations per attempt
    llm_calls: int = 0
    api_calls: int = 0
    cache_hits: int = 0
    tokens: int = 0
    wall_seconds: float = 0.0
    terraform: dict | None = None
    artifacts: dict[str, str] = field(default_factory=dict)


def _violations(g: GuardrailResult) -> list[dict]:
    return [asdict(v) for v in g.violations]


async def run_migration(
    repo_root: str | Path, out_dir: str | Path, session: Session, validate_tf: bool = True
) -> RunResult:
    repo_root, out = Path(repo_root), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    inventory = detect_repo(repo_root)  # deterministic ground for the guardrail
    trace = (out / "trace.jsonl").open("w")

    def log(**kw):
        trace.write(json.dumps(kw) + "\n")

    def finish(verdict, stop, plan, retries, first, rejections, **kw) -> RunResult:
        s = session.hooks.stats
        res = RunResult(
            verdict, stop, plan, retries, len(first.violations), first.items_checked,
            rejections, s.calls, s.api_calls, s.cache_hits, s.tokens,
            round(time.monotonic() - start, 2), **kw,
        )  # fmt: skip
        log(event="finish", **{k: v for k, v in asdict(res).items() if k != "plan"})
        trace.close()
        (out / "result.json").write_text(json.dumps(asdict(res), indent=2))
        return res

    message = (
        "Create the migration plan for this repository. Start by calling detect_aws, then follow "
        "your rules exactly."
    )
    rejections: list[list[dict]] = []
    first: GuardrailResult | None = None
    for attempt in range(MAX_RETRIES + 1):
        turn = await session.ask(message)
        log(event="turn", attempt=attempt, stop_reason=turn.stop_reason, error=turn.error)
        if turn.stop_reason != "completed" or not turn.text.strip():
            empty = first or GuardrailResult([], 0)
            reason = turn.stop_reason if turn.stop_reason != "completed" else "empty_response"
            return finish("stopped", reason, None, attempt, empty, rejections)
        g = check_plan(turn.text, inventory, repo_root)
        first = first or g
        log(event="guardrail", attempt=attempt, ok=g.ok, violations=_violations(g))
        if g.ok:
            (out / "plan.md").write_text(turn.text)
            spec = infer_app_spec(repo_root)
            files = write_artifacts(inventory, spec, out)
            tf = terraform_validate(files["terraform"].parent) if validate_tf else None
            return finish(
                "verified", "completed", turn.text, attempt, first, rejections,
                terraform=tf, artifacts={k: str(v) for k, v in files.items()},
            )  # fmt: skip
        rejections.append(_violations(g))
        message = (
            "Your draft was rejected by the evidence checker for these reasons:\n"
            f"{g.feedback()}\n\nRevise the whole plan. Remove or fix every item above, using only "
            "evidence from the tools. Do not mention the rejected names again."
        )
    (out / "plan.rejected.md").write_text(turn.text)
    return finish("could_not_verify", "guardrail_failed", None, MAX_RETRIES, first, rejections)


def main() -> None:
    from migratelens.agent import AgentSession, SessionConfig

    if len(sys.argv) < 3:
        sys.exit(
            "usage: python -m migratelens.pipeline <repo_path> <out_dir> [--no-mcp] [--replay]"
        )
    cfg = SessionConfig(use_mcp="--no-mcp" not in sys.argv, replay_only="--replay" in sys.argv)

    async def go():
        session = AgentSession(sys.argv[1], cfg)
        try:
            return await run_migration(sys.argv[1], sys.argv[2], session)
        finally:
            await session.close()

    r = asyncio.run(go())
    print(
        f"verdict={r.verdict} stop={r.stop_reason} retries={r.retries} calls={r.llm_calls} "
        f"api={r.api_calls} cached={r.cache_hits} tokens={r.tokens} wall={r.wall_seconds}s"
    )
    if r.terraform:
        print("terraform validate:", "ok" if r.terraform["ok"] else r.terraform["errors"])


if __name__ == "__main__":
    main()
