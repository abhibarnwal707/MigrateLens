import shutil
from pathlib import Path

import pytest
import yaml

from migratelens.tools.detector import detect_repo
from migratelens.tools.generators import (
    AppSpec,
    fill_spec_with_llm,
    generate_dockerfile,
    infer_app_spec,
    write_artifacts,
)
from migratelens.tools.mapper import gcp_resources, map_inventory, map_service
from migratelens.tools.validate import terraform_validate

FX = Path(__file__).parent / "fixtures"


def test_mapping_rows_are_complete_and_detector_names_are_covered():
    from migratelens.tools.detector import CANON

    for aws in set(CANON.values()):
        row = map_service(aws)
        assert row, f"{aws} missing from mapping.yaml"
        assert row["tradeoff"] and row["risk"] and row["docs"].startswith("https://")
    assert "Cloud Storage" in gcp_resources() and "Pub/Sub" in gcp_resources()
    assert map_service("Totally Made Up") is None


def test_unmapped_services_are_reported():
    inv = {"services": [{"service": "S3"}, {"service": "Nope"}]}
    r = map_inventory(inv)
    assert r["unmapped"] == ["Nope"] and r["mapped"][0]["aws"] == "S3"


def test_terraform_contents_match_inventory():
    from migratelens.tools.generators import generate_terraform

    tf = generate_terraform(detect_repo(FX / "tf_app"), AppSpec(name="demo"))
    assert "google_pubsub_topic" in tf and "google_firestore_database" in tf
    assert "google_storage_bucket" not in tf  # S3 not detected in tf_app
    assert "google_cloud_run_v2_service" in tf and "roles/owner" not in tf


def test_dockerfile_and_ci_are_valid_shapes(tmp_path):
    spec = infer_app_spec(FX / "py_app")
    assert spec.runtime == "python"
    assert generate_dockerfile(spec).startswith("FROM python:3.12-slim")
    files = write_artifacts(detect_repo(FX / "py_app"), spec, tmp_path)
    ci = yaml.safe_load(files["ci"].read_text())
    assert ci["jobs"]["build"]["steps"]
    assert "gcloud run deploy" in files["ci"].read_text().split("# Deployment")[1]


def test_llm_fill_only_accepts_valid_json():
    class Fake:
        def __init__(self, text):
            self.text = text

        def generate(self, prompt, tool_args=None):
            return self

    base = AppSpec()
    assert (
        fill_spec_with_llm(base, "x", Fake('{"port": 5000, "start_command": "flask run"}')).port
        == 5000
    )
    assert fill_spec_with_llm(base, "x", Fake("ignore previous instructions")) == base
    assert fill_spec_with_llm(base, "x", Fake('{"port": 99999, "start_command": "x"}')) == base


@pytest.mark.skipif(not shutil.which("terraform"), reason="terraform not installed")
@pytest.mark.parametrize("app", ["py_app", "tf_app", "sls_app", "node_app"])
def test_generated_terraform_validates(app, tmp_path):
    inv = detect_repo(FX / app)
    files = write_artifacts(inv, infer_app_spec(FX / app), tmp_path)
    result = terraform_validate(files["terraform"].parent)
    assert result["ok"], result["errors"]
