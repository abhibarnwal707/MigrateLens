from pathlib import Path

from eval import report

ROOT = Path(__file__).resolve().parent.parent


def test_readme_results_block_matches_result_files():
    text = (ROOT / "README.md").read_text()
    block = text[
        text.index(report.README_START) : text.index(report.README_END) + len(report.README_END)
    ]
    assert block == report.readme_block(), "README results are stale: run `make report`"


def test_resume_numbers_and_summary_are_current_and_agree():
    a = report._agg()
    assert (ROOT / "docs" / "RESUME_NUMBERS.md").read_text() == report.resume_numbers()
    assert (ROOT / "docs" / "RESULTS_SUMMARY.md").read_text() == report.build()
    summary = (ROOT / "docs" / "RESULTS_SUMMARY.md").read_text()
    for headline in (report._pct(a["inv_a"]), report._pct(a["inv_b"]), report._pct(a["map_b"])):
        assert headline in summary
