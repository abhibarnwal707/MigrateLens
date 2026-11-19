import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "site"))

import build_data  # noqa: E402


def test_site_data_matches_eval_results():
    on_disk = json.loads((ROOT / "site" / "data.json").read_text())
    assert on_disk == json.loads(json.dumps(build_data.build())), (
        "site data is stale: run `make site`"
    )
    js = (ROOT / "site" / "data.js").read_text()
    assert json.loads(js[len("window.ML_DATA = ") : -2]) == on_disk


def test_site_references_only_existing_local_files():
    html = (ROOT / "site" / "index.html").read_text() + (ROOT / "site" / "main.js").read_text()
    html += (ROOT / "site" / "style.css").read_text()
    refs = set(re.findall(r'(?:src|href|poster)="((?:img|media)/[^"#]+|[a-z]+\.(?:js|css))"', html))
    refs |= set(re.findall(r"url\(((?:img|media)/[^)]+)\)", html))
    refs |= set(re.findall(r'"(media/[^"#]+)#', html))
    assert refs, "no local references found"
    for ref in refs:
        assert (ROOT / "site" / ref).exists(), ref
