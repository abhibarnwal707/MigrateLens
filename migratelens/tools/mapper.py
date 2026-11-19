"""AWS -> GCP lookups from the curated allowlist in data/mapping.yaml. Never invents mappings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

MAPPING_PATH = Path(__file__).resolve().parent.parent / "data" / "mapping.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    with MAPPING_PATH.open() as fh:
        return yaml.safe_load(fh)["services"]


def aws_services() -> set[str]:
    return set(_load())


def gcp_resources() -> set[str]:
    """Every GCP product name the agent is allowed to cite."""
    return {name for row in _load().values() for name in row["gcp"]}


def map_service(aws_service: str) -> dict | None:
    """Return the mapping row for an AWS service, or None if it is not in the table."""
    row = _load().get(aws_service)
    return None if row is None else {"aws": aws_service, **row}


def map_inventory(inventory: dict) -> dict:
    """Split detected services into mapped rows and ones the table does not cover."""
    mapped, unmapped = [], []
    for svc in inventory["services"]:
        row = map_service(svc["service"])
        (mapped if row else unmapped).append(row or svc["service"])
    return {"mapped": mapped, "unmapped": unmapped}
