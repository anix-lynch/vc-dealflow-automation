#!/usr/bin/env python3
"""
enrich_batch.py — Batch contact enrichment via Apollo.io + Hunter.io

Reads a CSV of investor contacts, enriches each via Apollo.io People Match API,
verifies the email via Hunter.io, and outputs an enriched CSV.

Usage:
    python scripts/enrich_batch.py --input contacts.csv --output enriched_contacts.csv

Input CSV columns required:
    name, firm, email

Optional input columns (improve Apollo match quality):
    linkedin

Output CSV adds:
    title, industry, seniority, city, country, linkedin_url,
    email_verified, email_deliverability, email_score, enriched, error

Environment variables (set in ~/.config/secrets/global.env or export directly):
    APOLLO_API_KEY
    HUNTER_API_KEY

Author: Anix Lynch — gozeroshot.dev
"""

import argparse
import csv
import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "")

APOLLO_BASE_URL = "https://api.apollo.io/v1"
HUNTER_BASE_URL = "https://api.hunter.io/v2"

# Seconds between API calls — Apollo free tier: 50 req/min; paid: 300 req/min
RATE_LIMIT_DELAY = 1.0

OUTPUT_FIELDS = [
    "name", "firm", "email", "linkedin",
    "title", "industry", "seniority", "city", "country", "linkedin_url", "apollo_id",
    "email_verified", "email_deliverability", "email_score",
    "enriched", "error",
]


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _check_env() -> None:
    missing = []
    if not APOLLO_API_KEY:
        missing.append("APOLLO_API_KEY")
    if not HUNTER_API_KEY:
        missing.append("HUNTER_API_KEY")
    if missing:
        log.error(
            "Missing environment variables: %s\n"
            "Set them in ~/.config/secrets/global.env or export them before running.",
            ", ".join(missing),
        )
        sys.exit(1)


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _post(url: str, payload: dict) -> requests.Response:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    return response


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    reraise=True,
)
def _get(url: str, params: dict) -> requests.Response:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response


# ---------------------------------------------------------------------------
# Apollo enrichment
# ---------------------------------------------------------------------------

def enrich_apollo(name: str, firm: str, email: str, linkedin: Optional[str] = None) -> dict:
    """
    Call Apollo.io People Match API to enrich a contact.
    Docs: https://apolloio.github.io/apollo-api-docs/#people-match
    """
    parts = name.strip().split(" ") if name else [""]
    first_name = parts[0]
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    payload = {
        "api_key": APOLLO_API_KEY,
        "first_name": first_name,
        "last_name": last_name,
        "organization_name": firm,
        "reveal_personal_emails": True,
    }
    if email:
        payload["email"] = email
    if linkedin:
        payload["linkedin_url"] = linkedin

    result = {
        "title": "",
        "industry": "",
        "seniority": "",
        "city": "",
        "country": "",
        "linkedin_url": linkedin or "",
        "apollo_id": "",
        "enriched": False,
        "error": "",
    }

    try:
        resp = _post(f"{APOLLO_BASE_URL}/people/match", payload)
        data = resp.json()
        person = data.get("person") or {}

        if not person:
            result["error"] = "apollo:no_match"
            log.warning("Apollo: no match for %s at %s", name, firm)
            return result

        org = person.get("organization") or {}
        result.update({
            "title": person.get("title", ""),
            "industry": org.get("industry", ""),
            "seniority": person.get("seniority", ""),
            "city": person.get("city", ""),
            "country": person.get("country", ""),
            "linkedin_url": person.get("linkedin_url", linkedin or ""),
            "apollo_id": person.get("id", ""),
            "enriched": True,
        })
        apollo_email = person.get("email", "")
        if apollo_email and not email:
            result["_email_from_apollo"] = apollo_email

        log.info("Apollo enriched: %s | %s | %s", name, result["title"], result["industry"])

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 422:
            result["error"] = "apollo:insufficient_data"
            log.warning("Apollo: insufficient data for %s at %s", name, firm)
        elif status == 429:
            result["error"] = "apollo:rate_limited"
            log.warning("Apollo: rate limited — sleeping 60s")
            time.sleep(60)
        else:
            result["error"] = f"apollo:http_{status}"
            log.error("Apollo HTTP %s for %s: %s", status, name, exc)
    except Exception as exc:
        result["error"] = f"apollo:exception:{type(exc).__name__}"
        log.error("Apollo unexpected error for %s: %s", name, exc)

    return result


# ---------------------------------------------------------------------------
# Hunter email verification
# ---------------------------------------------------------------------------

def verify_hunter(email: str) -> dict:
    """
    Call Hunter.io Email Verifier API.
    Docs: https://hunter.io/api-documentation/v2#email-verifier
    """
    result = {
        "email_verified": False,
        "email_deliverability": "unknown",
        "email_score": 0,
    }

    if not email or "@" not in email:
        result["email_deliverability"] = "invalid_format"
        return result

    try:
        resp = _get(
            f"{HUNTER_BASE_URL}/email-verifier",
            params={"email": email, "api_key": HUNTER_API_KEY},
        )
        data = resp.json().get("data", {})
        deliverability = data.get("result", "unknown")
        score = data.get("score", 0)
        result.update({
            "email_deliverability": deliverability,
            "email_score": score,
            "email_verified": deliverability not in ("undeliverable", "unknown"),
        })
        log.info("Hunter: %s → %s (score: %s)", email, deliverability, score)

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        if status == 429:
            log.warning("Hunter: rate limited — sleeping 60s")
            time.sleep(60)
            result["email_deliverability"] = "rate_limited"
        else:
            log.error("Hunter HTTP %s for %s: %s", status, email, exc)
            result["email_deliverability"] = f"http_error_{status}"
    except Exception as exc:
        log.error("Hunter unexpected error for %s: %s", email, exc)
        result["email_deliverability"] = f"exception:{type(exc).__name__}"

    return result


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def enrich_contact(row: dict) -> dict:
    """Enrich a single contact: Apollo -> Hunter. Returns merged output dict."""
    name = row.get("name", "").strip()
    firm = row.get("firm", "").strip()
    email = row.get("email", "").strip()
    linkedin = row.get("linkedin", "").strip()

    output = {
        "name": name, "firm": firm, "email": email, "linkedin": linkedin,
        "title": "", "industry": "", "seniority": "", "city": "", "country": "",
        "linkedin_url": linkedin, "apollo_id": "",
        "email_verified": False, "email_deliverability": "not_checked", "email_score": 0,
        "enriched": False, "error": "",
    }

    # Step 1: Apollo
    apollo_result = enrich_apollo(name, firm, email, linkedin)
    output.update({k: v for k, v in apollo_result.items() if not k.startswith("_")})

    # Use Apollo-surfaced email if none provided
    if not email and apollo_result.get("_email_from_apollo"):
        output["email"] = apollo_result["_email_from_apollo"]
        email = output["email"]

    # Step 2: Hunter
    if output["email"]:
        hunter_result = verify_hunter(output["email"])
        output.update(hunter_result)
    else:
        output["email_deliverability"] = "no_email"
        log.warning("No email for %s at %s — skipping Hunter", name, firm)

    return output


def load_csv(path: str) -> list:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k.strip().lower(): v.strip() for k, v in row.items()})
    return rows


def write_csv(rows: list, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch enrich investor contacts via Apollo.io + Hunter.io",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/enrich_batch.py --input contacts.csv --output enriched_contacts.csv
  python scripts/enrich_batch.py --input data/investors.csv --delay 2.0

Input CSV required headers: name, firm, email
Optional header: linkedin
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Input CSV path")
    parser.add_argument("--output", "-o", default="enriched_contacts.csv", help="Output CSV path")
    parser.add_argument("--delay", "-d", type=float, default=RATE_LIMIT_DELAY, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Parse input without calling APIs")
    args = parser.parse_args()

    _check_env()

    if not Path(args.input).exists():
        log.error("Input file not found: %s", args.input)
        sys.exit(1)

    contacts = load_csv(args.input)
    total = len(contacts)
    log.info("Loaded %d contacts from %s", total, args.input)

    if args.dry_run:
        log.info("Dry run — first 3 rows:")
        for row in contacts[:3]:
            log.info("  %s", row)
        log.info("Dry run complete. No API calls made.")
        return

    enriched = []
    for i, contact in enumerate(contacts, 1):
        log.info("Processing %d / %d: %s at %s", i, total, contact.get("name", "?"), contact.get("firm", "?"))
        enriched.append(enrich_contact(contact))
        if i < total:
            time.sleep(args.delay)

    write_csv(enriched, args.output)

    success_count = sum(1 for r in enriched if r["enriched"])
    verified_count = sum(1 for r in enriched if r["email_verified"])
    log.info(
        "Done. %d/%d enriched | %d/%d emails verified | output: %s",
        success_count, total, verified_count, total, args.output,
    )
    if (total - success_count) > 0:
        log.warning("%d contacts not enriched. Check 'error' column in output CSV.", total - success_count)


if __name__ == "__main__":
    main()
