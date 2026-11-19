"""Evaluation metrics. Deterministic: no LLM judge is used anywhere in this file.

Plan-side extraction reuses the guardrail's vocabularies, so a service counts as "named" only if
it is spelled the way the guardrail recognises (this is stated in docs/RESULTS_SUMMARY.md).
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from migratelens import guardrail

EVAL_DIR = Path(__file__).resolve().parent
NO_EQUIVALENT = re.compile(
    r"no direct|no first-party|no equivalent|third-party|third party|smtp relay|no google", re.I
)


def load_truth(name: str) -> dict:
    return json.loads((EVAL_DIR / "truth" / f"{name}.json").read_text())


def app_names() -> list[str]:
    return sorted(p.stem for p in (EVAL_DIR / "truth").glob("*.json"))


def prf(pred: set[str], truth: set[str]) -> dict:
    tp = len(pred & truth)
    p = tp / len(pred) if pred else (1.0 if not truth else 0.0)
    r = tp / len(truth) if truth else 1.0
    return {
        "precision": p,
        "recall": r,
        "tp": tp,
        "fp": sorted(pred - truth),
        "fn": sorted(truth - pred),
    }


def services_named(plan: str, include_generic: bool = False) -> set[str]:
    """AWS services named in a plan, canonicalised. Bare 'IAM' is excluded unless
    include_generic (the guardrail always allows it, but scoring must be able to see it)."""
    surface = guardrail._aws_surface()
    rx = guardrail._name_regex(set(surface), r"Amazon |AWS ")
    found = {surface[m.group(1)] for m in rx.finditer(plan)}
    return found if include_generic else found - guardrail.AWS_EXEMPT


NEGATION = re.compile(
    r"\b(absent|not used|not use|does not use|do not use|doesn't use|no use of|not present|"
    r"none of|unused|not utilized|not required)\b",
    re.I,
)
# IAM is neutral in scoring: whether it "counts" as a used service is arbitrary in the truth files.
SCORING_NEUTRAL = {"IAM"}


def inventory_text(plan: str) -> str:
    """What the plan CLAIMS the repo uses: sections 1-2 (inventory + mapping table), minus lines
    that negate usage ('RDS is absent'). Mentions elsewhere (rollback notes etc.) are not usage
    claims. Falls back to the whole plan if the headings are missing. The guardrail's invented-
    resource rate still penalises naming absent services, since the instructions forbid it."""
    m = re.search(r"^##\s*1\..*?(?=^##\s*3\.|\Z)", plan, re.S | re.M)
    text = m.group(0) if m else plan
    return "\n".join(ln for ln in text.splitlines() if not NEGATION.search(ln))


def _gcp_in(line: str) -> set[str]:
    surface = guardrail._gcp_surface()
    rx = guardrail._name_regex(set(surface), r"Google ")
    return {surface[m.group(1)] for m in rx.finditer(line)}


def mapping_accuracy(plan: str, truth: dict) -> dict:
    """A truth service is mapped correctly if some plan line naming it also names an acceptable
    GCP product (or, for services with no equivalent, says so)."""
    surface = guardrail._aws_surface()
    rx = guardrail._name_regex(set(surface), r"Amazon |AWS ")
    correct, wrong = [], []
    scored = {k: v for k, v in truth["expected_mapping"].items() if k not in SCORING_NEUTRAL}
    for svc, acceptable in scored.items():
        ok = False
        for line in plan.splitlines():
            if svc not in {surface[m.group(1)] for m in rx.finditer(line)}:
                continue
            if acceptable and _gcp_in(line) & set(acceptable):
                ok = True
            if not acceptable and NO_EQUIVALENT.search(line):
                ok = True
        (correct if ok else wrong).append(svc)
    n = len(scored)
    return {"accuracy": len(correct) / n if n else 1.0, "correct": correct, "wrong": wrong}


def risk_coverage(plan: str, truth: dict) -> dict:
    low = plan.lower()
    hit = [r["id"] for r in truth["must_mention_risks"] if any(k in low for k in r["keywords_any"])]
    n = len(truth["must_mention_risks"])
    missed = [r["id"] for r in truth["must_mention_risks"] if r["id"] not in hit]
    return {"coverage": len(hit) / n if n else 1.0, "covered": hit, "missed": missed}


def invented_rate(violations: list[dict], items_checked: int) -> float:
    return len(violations) / items_checked if items_checked else 0.0


def bootstrap_ci(values: list[float], n: int = 2000, seed: int = 0) -> tuple[float, float]:
    """95% percentile bootstrap CI of the mean. With ~7 apps this interval is WIDE; report it."""
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(n))
    return (means[int(0.025 * n)], means[int(0.975 * n) - 1])


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
