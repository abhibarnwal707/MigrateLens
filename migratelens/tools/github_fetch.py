"""Fetch a PUBLIC GitHub repository as data for analysis. Nothing from it is ever executed.

Strict by design: github.com URLs only, a hard cap on bytes downloaded, and tar extraction with
Python's `data` filter (blocks absolute paths, `..`, links and special files).
"""

from __future__ import annotations

import io
import re
import tarfile
import urllib.request
from pathlib import Path

URL_RE = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024  # compressed; the 5 MB text cap is enforced afterwards
USER_AGENT = "migratelens-demo"


class FetchError(ValueError):
    pass


def parse_url(url: str) -> tuple[str, str]:
    m = URL_RE.match(url.strip())
    if not m or m.group(2) in (".", ".."):
        raise FetchError("Enter a public repository URL like https://github.com/owner/repo")
    return m.group(1), m.group(2)


def _open(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=30)  # noqa: S310 - fixed https host


def fetch_public_repo(url: str, dest: str | Path, opener=_open) -> Path:
    """Download the default branch tarball into dest and return the extracted repo root."""
    owner, repo = parse_url(url)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        resp = opener(f"https://codeload.github.com/{owner}/{repo}/tar.gz/HEAD")
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"Could not download {owner}/{repo} (is it public?): {exc}") from exc
    buf = io.BytesIO()
    with resp:
        while chunk := resp.read(64 * 1024):
            buf.write(chunk)
            if buf.tell() > MAX_DOWNLOAD_BYTES:
                raise FetchError("Repository download is over the 10 MB limit")
    buf.seek(0)
    try:
        with tarfile.open(fileobj=buf, mode="r:gz") as tar:
            tar.extractall(dest, filter="data")
    except (tarfile.TarError, OSError) as exc:
        raise FetchError(f"Could not unpack the repository safely: {exc}") from exc
    roots = [p for p in dest.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise FetchError("Unexpected archive layout")
    return roots[0]
