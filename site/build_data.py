"""Build site/data.json from recorded eval runs, the detector, mapping.yaml and computed results.

Every number on the website comes from this file. Usage: uv run python site/build_data.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval import report  # noqa: E402
from migratelens.tools import mapper  # noqa: E402
from migratelens.tools.detector import detect_repo  # noqa: E402
from migratelens.tools.repo_reader import list_files  # noqa: E402


def app_styles() -> dict[str, str]:
    rows = (ROOT / "eval" / "apps" / "README.md").read_text().splitlines()
    out = {}
    for r in rows:
        m = re.match(r"\| `([a-z0-9-]+)` \|.*\| ([^|]+) \|\s*$", r)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def build() -> dict:
    styles = app_styles()
    apps = []
    for run_dir in sorted((ROOT / "eval" / "runs").iterdir()):
        name = run_dir.name
        res = json.loads((run_dir / "result.json").read_text())
        repo = ROOT / "eval" / "apps" / name
        inv = detect_repo(repo)
        services = []
        for s in inv["services"]:
            row = mapper.map_service(s["service"]) or {}
            services.append({
                "aws": s["service"], "confidence": s["confidence"],
                "evidence": [f"{e['file']}:{e['line']}" for e in s["evidence"][:3]],
                "evidence_count": len(s["evidence"]),
                "gcp": row.get("gcp", []), "direct": row.get("direct", False),
            })  # fmt: skip
        rejected = sorted(
            {v["item"] for rej in res["rejections"] for v in rej if v["kind"] == "aws_service"}
        )
        tf = run_dir / "terraform" / "main.tf"
        apps.append({
            "name": name, "style": styles.get(name, ""), "synthetic": name == "java-synthetic-orders",
            "files": len(list_files(repo)), "verdict": res["verdict"], "retries": res["retries"],
            "llm_calls": res["llm_calls"], "tokens": res["tokens"],
            "items_checked": res["first_draft_items"],
            "first_draft_violations": res["first_draft_violations"],
            "rejected_names": rejected, "drafts_rejected": len(res["rejections"]),
            "terraform_ok": (res.get("terraform") or {}).get("ok"),
            "terraform_resources": len(re.findall(r'^resource "', tf.read_text(), re.M)) if tf.exists() else 0,
            "services": services,
        })  # fmt: skip
    a = report._agg()
    mapping = [{"aws": k, "gcp": v["gcp"], "direct": v["direct"]}
               for k, v in mapper._load().items()]  # fmt: skip
    return {
        "apps": apps,
        "mapping": mapping,
        "results": {
            "n_apps": a["n_apps"],
            "n_real": a["n_real"],
            "n_synth": a["n_synth"],
            "invented_agent": round(100 * a["inv_a"], 1),
            "invented_baseline": round(100 * a["inv_b"], 1),
            "verified": len(a["ver"]),
            "tf_ok": a["tf_ok"],
            "tf_n": a["tf_n"],
            "recall_agent": round(100 * a["rec_a_all"], 1),
            "recall_baseline": round(100 * a["rec_b"], 1),
            "mapping_verified": round(100 * a["map_a_ver"], 1),
            "calls_agent": round(a["calls_a"], 1),
            "calls_baseline": round(a["calls_b"], 1),
            "reviewed": a["reviewed"],
        },  # fmt: skip
    }


if __name__ == "__main__":
    data = build()
    (ROOT / "site" / "data.json").write_text(json.dumps(data, indent=1) + "\n")
    # data.js lets the page work from file:// too (fetch() of a local file is blocked by browsers)
    (ROOT / "site" / "data.js").write_text("window.ML_DATA = " + json.dumps(data) + ";\n")
    print("wrote site/data.json and site/data.js")
