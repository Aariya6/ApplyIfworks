import csv
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGION_LINKS = ROOT / "config" / "region_links.csv"

REGIONS = {
    "ireland": {
        "label": "Ireland",
        "aliases": (
            "ireland",
            "republic of ireland",
            "dublin",
            "cork",
            "galway",
            "limerick",
            "waterford",
        ),
    },
    "italy": {
        "label": "Italy",
        "aliases": (
            "italy",
            "italia",
            "milan",
            "milano",
            "rome",
            "roma",
            "turin",
            "torino",
            "bologna",
            "naples",
            "napoli",
            "florence",
            "firenze",
            "venice",
            "venezia",
        ),
    },
}

INDIA_REMOTE_AUTH = {"REMOTE_WORLDWIDE", "CONTRACTOR_SUPPORTED", "EOR_SUPPORTED"}


def normalize_region(region: str) -> str:
    normalized = region.strip().casefold()
    if normalized not in REGIONS:
        raise ValueError(f"Unsupported country region: {region}")
    return normalized


def load_region_links(region: str) -> list[dict[str, str]]:
    key = normalize_region(region)
    if not REGION_LINKS.is_file():
        raise FileNotFoundError(f"Country reference list is missing: {REGION_LINKS}")
    with REGION_LINKS.open(encoding="utf-8-sig", newline="") as stream:
        return [
            row
            for row in csv.DictReader(stream)
            if row.get("country", "").casefold() == key
        ]


def job_matches_region(job: dict[str, Any], region: str) -> bool:
    key = normalize_region(region)
    region_data = REGIONS[key]
    country = str(job.get("country") or "").casefold()
    location = str(job.get("location") or "")
    if key == "ireland" and re.search(r"\bnorthern ireland\b", location, re.I):
        return False
    if country == key:
        return True
    return any(
        re.search(r"\b" + re.escape(alias) + r"\b", f"{country} {location}", re.I)
        for alias in region_data["aliases"]
    )


def job_remote_from_india(job: dict[str, Any]) -> bool:
    auth = str(job.get("work_auth") or "").upper()
    if auth not in INDIA_REMOTE_AUTH:
        return False
    wording = " ".join(
        str(job.get(field) or "")
        for field in ("remote", "work_auth", "description", "location")
    )
    return bool(re.search(r"\bremote\b|\bwork from anywhere\b|\bworldwide\b", wording, re.I))


def region_jobs(
    jobs: list[dict[str, Any]],
    region: str,
    mode: str = "all",
) -> list[dict[str, Any]]:
    if mode not in {"all", "remote-india"}:
        raise ValueError(f"Unsupported country-tab mode: {mode}")
    matches = [job for job in jobs if job_matches_region(job, region)]
    if mode == "remote-india":
        matches = [job for job in matches if job_remote_from_india(job)]
    return matches
