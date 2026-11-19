import re
from pathlib import Path

import pytest

DOC = Path(__file__).resolve().parent.parent / "docs" / "ARCHITECTURE.md"
BLOCKS = re.findall(r"```python\n(.*?)```", DOC.read_text(), re.S)


def test_doc_has_snippets():
    assert len(BLOCKS) == 3


@pytest.mark.parametrize("block", BLOCKS, ids=["cache-throttle", "guardrail", "mcp-tools"])
def test_doc_snippet_runs(block, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".state").mkdir()
    exec(compile(block, "ARCHITECTURE.md", "exec"), {})
