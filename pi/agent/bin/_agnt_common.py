"""Shared helpers for agnt and agent-instructions.

Single source for the simple frontmatter parser and the model-family catalog
(catalog.json). Keep this dependency-free and small.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

AGENT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = AGENT_ROOT / "catalog.json"


def parse_simple_yaml(raw: str) -> Dict[str, Any]:
    """Parse the small frontmatter subset used by tasks, roles, and skills."""
    data: Dict[str, Any] = {}
    current_key: str | None = None
    for original in raw.splitlines():
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-") and current_key:
            value = stripped[1:].strip().strip("\"'")
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(value)
            continue
        if ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            if not value:
                data[key] = []
            elif value.lower() in {"true", "false"}:
                data[key] = value.lower() == "true"
            elif value.startswith("[") and value.endswith("]"):
                data[key] = [
                    item.strip().strip("\"'")
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
            else:
                data[key] = value.strip("\"'")
    return data


def split_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    return parse_simple_yaml(text[4:end]), text[end + 5 :]


def parse_frontmatter_file(path: Path) -> Tuple[Dict[str, Any], str]:
    return split_frontmatter(path.read_text(encoding="utf-8"))


_CATALOG_CACHE: Dict[str, Dict[str, Any]] = {}


def load_catalog(path: Path | None = None) -> Dict[str, Any]:
    catalog_path = path or CATALOG_PATH
    key = str(catalog_path)
    if key in _CATALOG_CACHE:
        return _CATALOG_CACHE[key]
    catalog: Dict[str, Any] = {"families": {}, "defaults": {}}
    if catalog_path.is_file():
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                catalog["families"] = data.get("families") or {}
                catalog["defaults"] = data.get("defaults") or {}
        except (OSError, json.JSONDecodeError):
            pass
    _CATALOG_CACHE[key] = catalog
    return catalog


def _venues(
    catalog: Dict[str, Any],
) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    rows = []
    for family_id, family in (catalog.get("families") or {}).items():
        if not isinstance(family, dict):
            continue
        for venue in family.get("venues") or []:
            if isinstance(venue, dict) and venue.get("target"):
                rows.append((str(family_id), family, venue))
    return rows


def family_for_target(target: str, catalog: Dict[str, Any] | None = None) -> str | None:
    catalog = catalog or load_catalog()
    for family_id, _family, venue in _venues(catalog):
        if venue["target"] == target:
            return family_id
    return None


def venue_info(
    target: str, catalog: Dict[str, Any] | None = None
) -> Dict[str, Any] | None:
    catalog = catalog or load_catalog()
    for family_id, _family, venue in _venues(catalog):
        if venue["target"] == target:
            info = dict(venue)
            info["family"] = family_id
            return info
    return None


def proxy_for_target(
    target: str, catalog: Dict[str, Any] | None = None
) -> Dict[str, str] | None:
    """OpenRouter venue standing in for a local target, for opportunity-cost pricing."""
    catalog = catalog or load_catalog()
    info = venue_info(target, catalog)
    if not info:
        return None
    family = (catalog.get("families") or {}).get(info["family"]) or {}
    for venue in family.get("venues") or []:
        if not isinstance(venue, dict):
            continue
        proxy_target = str(venue.get("target") or "")
        if proxy_target != target and proxy_target.startswith("openrouter-localish/"):
            return {
                "target": proxy_target,
                "quality": str(venue.get("equivalence") or "exact-family"),
            }
    return None


def opportunity_rates(
    target: str, catalog: Dict[str, Any] | None = None
) -> Dict[str, float] | None:
    """Family-level OpenRouter list rates for subscription-backed venues."""
    catalog = catalog or load_catalog()
    info = venue_info(target, catalog)
    if not info:
        return None
    family = (catalog.get("families") or {}).get(info["family"]) or {}
    rates = family.get("openrouterRates")
    if not isinstance(rates, dict):
        return None
    return {
        "input": float(rates.get("input") or 0.0),
        "output": float(rates.get("output") or 0.0),
        "cacheRead": float(rates.get("cacheRead") or 0.0),
        "cacheWrite": float(rates.get("cacheWrite") or 0.0),
    }


def provider_gpu_watts(
    provider: str, catalog: Dict[str, Any] | None = None
) -> float | None:
    catalog = catalog or load_catalog()
    watts = (catalog.get("defaults") or {}).get("providerGpuWatts") or {}
    value = watts.get(provider)
    return float(value) if value is not None else None


def default_electricity_usd_per_kwh(
    catalog: Dict[str, Any] | None = None,
) -> float | None:
    catalog = catalog or load_catalog()
    value = (catalog.get("defaults") or {}).get("electricityUsdPerKwh")
    return float(value) if value is not None else None
