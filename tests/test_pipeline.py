import asyncio
import json
from pathlib import Path

from migratelens.agent import Stats, TurnResult
from migratelens.pipeline import run_migration

FX = Path(__file__).parent / "fixtures" / "py_app"
GOOD = "S3 (app.py:5) -> Cloud Storage; SQS (app.py:6) -> Pub/Sub. Artifacts: terraform/main.tf."
BAD = "The app uses S3 and also Amazon Kendra for search (app.py:5)."


class Hooks:
    stats = Stats()


class Scripted:
    """Fake agent session: returns canned drafts, records the revision prompts it receives."""

    hooks = Hooks()

    def __init__(self, drafts):
        self.drafts, self.prompts = list(drafts), []

    async def ask(self, message):
        self.prompts.append(message)
        return TurnResult(self.drafts.pop(0), "completed")


def run(drafts, tmp_path):
    s = Scripted(drafts)
    res = asyncio.run(run_migration(FX, tmp_path, s, validate_tf=False))
    return res, s


def test_clean_first_draft_is_verified_and_artifacts_written(tmp_path):
    res, _ = run([GOOD], tmp_path)
    assert (res.verdict, res.retries, res.first_draft_violations) == ("verified", 0, 0)
    assert (tmp_path / "terraform" / "main.tf").exists() and (tmp_path / "plan.md").exists()


def test_invented_service_is_rejected_then_revised(tmp_path):
    res, s = run([BAD, GOOD], tmp_path)
    assert res.verdict == "verified" and res.retries == 1
    assert res.first_draft_violations == 1 and res.rejections[0][0]["item"] == "Kendra"
    assert "Kendra" in s.prompts[1]  # the specific failure is sent back to the agent


def test_gives_up_after_two_retries_with_could_not_verify(tmp_path):
    res, s = run([BAD, BAD, BAD], tmp_path)
    assert res.verdict == "could_not_verify" and res.stop_reason == "guardrail_failed"
    assert res.retries == 2 and len(s.prompts) == 3 and len(res.rejections) == 3
    assert res.plan is None and not (tmp_path / "terraform").exists()
    assert (tmp_path / "plan.rejected.md").exists()
    assert json.loads((tmp_path / "result.json").read_text())["verdict"] == "could_not_verify"


def test_budget_stop_is_reported_not_raised(tmp_path):
    class Stopper(Scripted):
        async def ask(self, message):
            return TurnResult("", "budget_exhausted", "daily budget reached")

    res = asyncio.run(run_migration(FX, tmp_path, Stopper([]), validate_tf=False))
    assert (res.verdict, res.stop_reason) == ("stopped", "budget_exhausted")
