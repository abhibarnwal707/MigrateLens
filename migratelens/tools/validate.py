"""Validate generated Terraform without credentials or any cloud resource.

Runs only `terraform init -backend=false` and `terraform validate`. Never `plan` or `apply`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


def terraform_validate(tf_dir: str | Path, timeout: int = 300) -> dict:
    tf = shutil.which("terraform")
    if not tf:
        return {"ok": False, "skipped": True, "errors": ["terraform not installed"]}
    try:
        return _validate(tf, str(tf_dir), timeout)
    finally:
        # `terraform init` downloads a ~750 MB provider into .terraform; do not leave it behind
        shutil.rmtree(Path(tf_dir) / ".terraform", ignore_errors=True)


def _validate(tf: str, cwd: str, timeout: int) -> dict:
    init = subprocess.run(
        [tf, "init", "-backend=false", "-input=false", "-no-color"],
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )  # fmt: skip
    if init.returncode != 0:
        return {"ok": False, "skipped": False, "errors": [init.stderr.strip()[-800:]]}
    val = subprocess.run(
        [tf, "validate", "-json", "-no-color"],
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )  # fmt: skip
    out = json.loads(val.stdout)
    errors = [d["summary"] + ": " + d.get("detail", "") for d in out.get("diagnostics", [])
              if d["severity"] == "error"]  # fmt: skip
    return {"ok": out["valid"], "skipped": False, "errors": errors}
