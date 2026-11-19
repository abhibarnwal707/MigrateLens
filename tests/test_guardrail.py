from pathlib import Path

from migratelens.guardrail import check_plan
from migratelens.tools.detector import detect_repo

FX = Path(__file__).parent / "fixtures" / "py_app"
INV = detect_repo(FX)  # S3 + SQS (app.py lines 5-6)


def kinds(result):
    return {(v.kind, v.item) for v in result.violations}


def test_clean_plan_passes():
    plan = (
        "S3 is used at app.py:5 and moves to Cloud Storage; SQS (app.py:6) moves to Pub/Sub. "
        "Artifacts: terraform/main.tf, Dockerfile, .github/workflows/ci.yml. "
        "Grant least-privilege IAM roles to the Service Accounts."
    )
    r = check_plan(plan, INV, FX)
    assert r.ok, r.feedback()
    assert r.items_checked >= 6


def test_rejects_invented_aws_service():
    r = check_plan("The app also uses Amazon Kendra and DynamoDB for search.", INV, FX)
    assert ("aws_service", "Kendra") in kinds(r)
    assert ("aws_service", "DynamoDB") in kinds(r)
    assert not r.ok and "Kendra" in r.feedback()


def test_rejects_gcp_product_not_in_mapping():
    r = check_plan("S3 data goes to BigQuery and runs on Compute Engine.", INV, FX)
    assert {("gcp_resource", "BigQuery"), ("gcp_resource", "Compute Engine")} <= kinds(r)


def test_rejects_missing_file_and_bad_line():
    r = check_plan("See app.py:99 and handlers/worker.py:3 for S3 use.", INV, FX)
    assert ("line", "app.py:99") in kinds(r)
    assert ("file", "handlers/worker.py") in kinds(r)


def test_rejects_dollar_amounts_but_not_node_js_mentions():
    r = check_plan("S3 will cost about $50 per month on node.js hosts.", INV, FX)
    assert kinds(r) == {("cost", "dollar amount")}


def test_prefix_forms_and_aliases_count_as_the_same_service():
    r = check_plan(
        "Amazon S3 and AWS Simple Queue Service become Cloud Storage and Pub/Sub.", INV, FX
    )
    assert r.ok, r.feedback()
