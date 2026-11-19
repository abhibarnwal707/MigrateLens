from eval.metrics import (
    bootstrap_ci,
    load_truth,
    mapping_accuracy,
    prf,
    risk_coverage,
    services_named,
)


def test_prf_counts_and_lists_errors():
    r = prf({"S3", "SQS", "SNS"}, {"S3", "SQS", "Lambda"})
    assert (r["tp"], r["fp"], r["fn"]) == (2, ["SNS"], ["Lambda"])
    assert round(r["precision"], 3) == round(2 / 3, 3) and round(r["recall"], 3) == round(2 / 3, 3)
    assert prf(set(), set())["recall"] == 1.0


def test_services_named_ignores_generic_iam_and_canonicalises():
    plan = "Amazon S3 and AWS Simple Queue Service use IAM roles; also Fargate."
    assert services_named(plan) == {"S3", "SQS", "ECS"}


def test_mapping_accuracy_needs_service_and_gcp_on_same_line_and_handles_no_equivalent():
    truth = load_truth("priority-mailer-ses")
    plan = (
        "| S3 | Cloud Storage |\n| SQS | Pub/Sub |\nSES has no direct equivalent on Google Cloud.\n"
    )
    m = mapping_accuracy(plan, truth)
    assert {"S3", "SQS", "SES"} <= set(m["correct"])
    assert "Lambda" in m["wrong"]  # never mapped in this plan


def test_risk_coverage_keyword_rubric():
    truth = load_truth("sqs-max-concurrency")
    r = risk_coverage("Concurrency limits differ; rebuild the dashboard.", truth)
    assert r["covered"] == ["r1", "r4"] and r["missed"] == ["r2", "r3"]


def test_bootstrap_ci_brackets_the_mean_and_is_deterministic():
    vals = [0.2, 0.4, 0.6, 0.8, 1.0, 0.5, 0.7]
    lo, hi = bootstrap_ci(vals)
    assert lo <= sum(vals) / len(vals) <= hi and (lo, hi) == bootstrap_ci(vals)
    assert bootstrap_ci([0.5, 0.5, 0.5]) == (0.5, 0.5)


def test_every_truth_file_is_well_formed_and_unreviewed_until_confirmed():
    from eval.metrics import app_names

    for name in app_names():
        t = load_truth(name)
        assert t["services_in_scope"] and 3 <= len(t["must_mention_risks"]) <= 6
        assert set(t["expected_mapping"]) == set(t["services_in_scope"])
        assert t["synthetic"] is (name == "java-synthetic-orders")
        assert (t["commit"] is None) == t["synthetic"]


def test_inventory_text_ignores_absent_mentions_and_sees_iam():
    from eval.metrics import inventory_text

    plan = (
        "## 1. Architecture inventory\n- S3 (a.py:1)\n- IAM roles\n"
        "## 3. Target\nRDS is absent.\n## 5. Rollback\nRevert to ECS.\n"
    )
    named = services_named(inventory_text(plan), include_generic=True)
    assert named == {"S3", "IAM"}
    assert "IAM" not in services_named(plan)  # default keeps the guardrail's exemption


def test_negated_lines_are_not_usage_claims():
    from eval.metrics import inventory_text

    plan = "## 1. Inventory\n- S3 (a.py:1)\nNote: RDS and ECS are absent from this repo.\n## 3. x\n"
    assert services_named(inventory_text(plan)) == {"S3"}
