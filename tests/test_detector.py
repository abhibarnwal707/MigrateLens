from pathlib import Path

import pytest

from migratelens.tools.detector import detect_repo
from migratelens.tools.repo_reader import RepoTooLarge, UnsafePath, list_files, read_file

FX = Path(__file__).parent / "fixtures"


def by_service(result):
    return {s["service"]: s for s in result["services"]}


def test_python_boto3_with_line_evidence():
    s = by_service(detect_repo(FX / "py_app"))
    assert {"S3", "SQS"} <= set(s)
    assert "Kinesis" not in s  # commented-out line ignored
    assert s["S3"]["confidence"] == "high"
    assert {"file": "app.py", "line": 5, "snippet": 's3 = boto3.client("s3")'} in s["S3"][
        "evidence"
    ]


def test_env_var_is_low_confidence_and_secret_is_not_echoed():
    r = detect_repo(FX / "py_app")
    assert any(e["line"] == 8 for e in by_service(r)["S3"]["evidence"])
    assert r["possible_secrets"] == [
        {"file": "app.py", "line": 9, "note": "possible secret in file app.py"}
    ]
    assert "AKIAABCDEFGHIJKLMNOP" not in str(r)
    assert any(sig["signal"] == "dockerfile" for sig in r["signals"])


def test_terraform_resources():
    assert {"SNS", "DynamoDB"} == set(by_service(detect_repo(FX / "tf_app")))


def test_serverless_and_cloudformation():
    s = by_service(detect_repo(FX / "sls_app"))
    assert {"Lambda", "SQS", "S3"} <= set(s)
    assert s["Lambda"]["evidence"][0]["line"] == 5


def test_node_sdk_v3():
    assert {"S3", "Secrets Manager"} == set(by_service(detect_repo(FX / "node_app")))


def test_reader_blocks_traversal_and_symlinks(tmp_path):
    (tmp_path / "repo").mkdir()
    (tmp_path / "secret.txt").write_text("x")
    (tmp_path / "repo" / "ok.txt").write_text("hi")
    (tmp_path / "repo" / "link.txt").symlink_to(tmp_path / "secret.txt")
    with pytest.raises(UnsafePath):
        read_file(tmp_path / "repo", "../secret.txt")
    with pytest.raises(UnsafePath):
        read_file(tmp_path / "repo", "link.txt")
    assert list_files(tmp_path / "repo") == ["ok.txt"]


def test_reader_skips_binaries_and_rejects_big_repos(tmp_path, monkeypatch):
    (tmp_path / "a.bin").write_bytes(b"\0\1\2")
    (tmp_path / "a.txt").write_text("hello")
    assert list_files(tmp_path) == ["a.txt"]
    monkeypatch.setattr("migratelens.tools.repo_reader.MAX_TOTAL_BYTES", 3)
    with pytest.raises(RepoTooLarge):
        list_files(tmp_path)


def test_sam_resources_and_event_types():
    s = by_service(detect_repo(FX / "sam_app"))
    assert {"Lambda", "SQS", "API Gateway", "DynamoDB"} == set(s)
    assert s["Lambda"]["evidence"][0]["line"] == 4


def test_cdk_python_imports_map_to_services():
    s = by_service(detect_repo(FX / "cdk_app"))
    assert {"Lambda", "S3", "CloudWatch"} == set(s)
