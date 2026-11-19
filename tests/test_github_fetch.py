import io
import tarfile

import pytest

from migratelens.tools.github_fetch import (
    MAX_DOWNLOAD_BYTES,
    FetchError,
    fetch_public_repo,
    parse_url,
)


def make_tar(members):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            else:
                info.type = tarfile.SYMTYPE
                info.linkname = data.decode()
                tar.addfile(info)
    return buf.getvalue()


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_url_validation():
    assert parse_url("https://github.com/aws-samples/some.repo.git") == ("aws-samples", "some.repo")
    bad_urls = [
        "http://github.com/a/b",
        "https://evil.com/a/b",
        "https://github.com/a",
        "https://github.com/a/b/tree/main",
        "file:///etc/passwd",
        "https://github.com/a/..",
    ]
    for bad in bad_urls:
        with pytest.raises(FetchError):
            parse_url(bad)


def test_fetch_extracts_files(tmp_path):
    data = make_tar([("repo-abc/app.py", b"import boto3\n", "file")])
    root = fetch_public_repo("https://github.com/o/r", tmp_path, opener=lambda u: Resp(data))
    assert (root / "app.py").read_text() == "import boto3\n"


def test_fetch_blocks_traversal_and_symlinks(tmp_path):
    for evil in ([("repo/../../escape.txt", b"x", "file")], [("repo/link", b"/etc/passwd", "sym")]):
        data = make_tar(evil + [("repo/ok.txt", b"ok", "file")])
        with pytest.raises(FetchError):
            fetch_public_repo(
                "https://github.com/o/r", tmp_path / "x", opener=lambda u, d=data: Resp(d)
            )
    assert not (tmp_path / "escape.txt").exists()


def test_fetch_enforces_download_cap(tmp_path):
    big = Resp(b"\0" * (MAX_DOWNLOAD_BYTES + 1))
    with pytest.raises(FetchError, match="10 MB"):
        fetch_public_repo("https://github.com/o/r", tmp_path, opener=lambda u: big)
