# ai/email_finder.py

import os
import uuid
import requests
from datetime import datetime, timezone
from pathlib import Path
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

if not os.getenv("GCP_PROJECT_ID"):
    os.environ["GCP_PROJECT_ID"] = "reachout-ai-496806"
    os.environ["BQ_DATASET"]     = "reachout"

PROJECT       = os.getenv("GCP_PROJECT_ID")
DATASET       = os.getenv("BQ_DATASET")
HUNTER_KEY    = os.getenv("HUNTER_API_KEY")
CONTACTS_TABLE = f"{PROJECT}.{DATASET}.outreach_log"

bq_client = bigquery.Client(project=PROJECT)


# ── Helper — get company domain ───────────────────────────

def find_domain(company_name: str) -> str:
    """
    Use Hunter.io domain search to find the company email domain.
    e.g. "Atlassian" → "atlassian.com"
    """
    url = "https://api.hunter.io/v2/domain-search"
    params = {
        "company": company_name,
        "api_key": HUNTER_KEY,
        "limit":   1,
    }
    response = requests.get(url, params=params)
    data     = response.json()

    if response.status_code != 200:
        raise Exception(f"Hunter.io error: {data}")

    domain = data.get("data", {}).get("domain")
    if not domain:
        raise Exception(f"No domain found for company: {company_name}")

    return domain


# ── Main — find email ─────────────────────────────────────

def find_email(first_name: str, last_name: str,
               domain: str) -> dict:
    """
    Use Hunter.io email finder to get verified email address.
    Returns dict with email, score, and verification status.
    """
    url = "https://api.hunter.io/v2/email-finder"
    params = {
        "domain":     domain,
        "first_name": first_name,
        "last_name":  last_name,
        "api_key":    HUNTER_KEY,
    }
    response = requests.get(url, params=params)
    data     = response.json()

    if response.status_code != 200:
        raise Exception(f"Hunter.io error: {data}")

    result = data.get("data", {})
    return {
        "email":    result.get("email"),
        "score":    result.get("score"),       # confidence 0-100
        "status":   result.get("status"),      # verified / guessed
        "domain":   domain,
        "sources":  len(result.get("sources", [])),
    }


# ── Fallback — guess email pattern ───────────────────────

def guess_email_patterns(first_name: str, last_name: str,
                          domain: str) -> list:
    """
    If Hunter.io cannot find a verified email,
    generate the most common patterns as fallbacks.
    """
    f = first_name.lower()
    l = last_name.lower()

    return [
        f"{f}.{l}@{domain}",
        f"{f}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{f}_{l}@{domain}",
    ]


# ── Check remaining Hunter credits ───────────────────────

def check_credits() -> dict:
    """Check how many Hunter.io searches you have left."""
    url = "https://api.hunter.io/v2/account"
    params = {"api_key": HUNTER_KEY}
    response = requests.get(url, params=params)
    data     = response.json()
    account  = data.get("data", {})
    return {
        "searches_used":      account.get("requests", {}).get("searches", {}).get("used", 0),
        "searches_available": account.get("requests", {}).get("searches", {}).get("available", 0),
    }


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ReachOut AI — Recruiter Email Finder ===\n")

    # Check credits first
    try:
        credits = check_credits()
        print(f"Hunter.io credits remaining: "
              f"{credits['searches_available']} searches\n")
    except Exception as e:
        print(f"Could not check credits: {e}\n")

    # Get input
    company    = input("Company name (e.g. Atlassian): ").strip()
    first_name = input("Recruiter first name: ").strip()
    last_name  = input("Recruiter last name: ").strip()

    # Step 1 — find domain
    print(f"\nFinding domain for {company}...")
    try:
        domain = find_domain(company)
        print(f"Domain found: {domain}")
    except Exception as e:
        print(f"Could not find domain: {e}")
        domain = input("Enter domain manually (e.g. atlassian.com): ").strip()

    # Step 2 — find email
    print(f"\nSearching for {first_name} {last_name} at {domain}...")
    try:
        result = find_email(first_name, last_name, domain)

        if result["email"]:
            print(f"\n✓ Email found!")
            print(f"  Email:    {result['email']}")
            print(f"  Score:    {result['score']}/100 confidence")
            print(f"  Status:   {result['status']}")
            print(f"  Sources:  {result['sources']} source(s) found")
        else:
            print("\nNo verified email found.")
            print("Generating likely email patterns as fallback:\n")
            patterns = guess_email_patterns(first_name, last_name, domain)
            for i, pattern in enumerate(patterns, 1):
                print(f"  {i}. {pattern}")
            print("\nTip: Try sending to the first pattern — "
                  "firstname.lastname is the most common format.")

    except Exception as e:
        print(f"Hunter.io search failed: {e}")
        print("\nFallback email patterns:")
        patterns = guess_email_patterns(first_name, last_name, domain)
        for i, pattern in enumerate(patterns, 1):
            print(f"  {i}. {pattern}")

    # Step 3 — offer to generate outreach message
    print()
    generate = input("Generate outreach email for this contact? (y/n): ").strip().lower()
    if generate == "y":
        print("\nRun this next:")
        print("  python ai\\message_generator.py")
        print(f"\nWhen asked for contact name enter: {first_name} {last_name}")
        if result.get("email"):
            print(f"Their email: {result['email']}")