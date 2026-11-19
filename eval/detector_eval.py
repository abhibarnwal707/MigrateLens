"""Score the deterministic detector (no LLM, no API) against hand-written ground truth.

Usage: python -m eval.detector_eval [--label TEXT]   (also writes eval/results/detector.json)
Scores in-scope services only: out-of-scope services (not in mapping.yaml) cannot be reported.
"""

from __future__ import annotations

import json
import sys

from eval.metrics import EVAL_DIR, app_names, bootstrap_ci, load_truth, mean, prf
from migratelens.tools.detector import detect_repo


def run() -> dict:
    rows = {}
    for name in app_names():
        truth = load_truth(name)
        pred = {s["service"] for s in detect_repo(EVAL_DIR / "apps" / name)["services"]}
        rows[name] = prf(pred, set(truth["services_in_scope"]))
        rows[name]["human_reviewed"] = truth["human_reviewed"]
    ps, rs = [r["precision"] for r in rows.values()], [r["recall"] for r in rows.values()]
    tp = sum(r["tp"] for r in rows.values())
    fp = sum(len(r["fp"]) for r in rows.values())
    fn = sum(len(r["fn"]) for r in rows.values())
    return {
        "apps": rows,
        "macro_precision": mean(ps), "macro_recall": mean(rs),
        "macro_precision_ci95": bootstrap_ci(ps), "macro_recall_ci95": bootstrap_ci(rs),
        "micro_precision": tp / (tp + fp) if tp + fp else 0.0,
        "micro_recall": tp / (tp + fn) if tp + fn else 0.0,
        "n_apps": len(rows),
    }  # fmt: skip


def main() -> None:
    res = run()
    label = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else ""
    (EVAL_DIR / "results").mkdir(exist_ok=True)
    out = EVAL_DIR / "results" / f"detector{('_' + label) if label else ''}.json"
    out.write_text(json.dumps(res, indent=2))
    for n, r in res["apps"].items():
        print(f"{n:24} P={r['precision']:.2f} R={r['recall']:.2f}  FP={r['fp']}  FN={r['fn']}")
    print(
        f"macro P={res['macro_precision']:.3f} R={res['macro_recall']:.3f} | "
        f"micro P={res['micro_precision']:.3f} R={res['micro_recall']:.3f} | n={res['n_apps']}"
    )
    print("wrote", out)


if __name__ == "__main__":
    main()
