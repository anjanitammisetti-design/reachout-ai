# ingestion/parse_jd.py

import uuid
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from google.cloud import bigquery
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# If dotenv doesn't work, set directly
if not os.getenv("GCP_PROJECT_ID"):
    os.environ["GCP_PROJECT_ID"] = "reachout-ai-496806"
    os.environ["BQ_DATASET"] = "reachout"

client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))
TABLE = f"{os.getenv('GCP_PROJECT_ID')}.{os.getenv('BQ_DATASET')}.raw_jobs"


def fetch_text_from_url(url: str) -> str:
    """Fetch and extract readable text from a job posting URL."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["nav", "header", "footer", "script", "style"]):
        tag.decompose()
    return soup.get_text(separator=" ", strip=True)


def parse_jd(url: str = None, raw_text: str = None, source: str = "manual") -> dict:
    """
    Accept either a URL or raw pasted text.
    Returns a dict ready to insert into BigQuery.
    """
    if url:
        description_raw = fetch_text_from_url(url)
    elif raw_text:
        description_raw = raw_text
    else:
        raise ValueError("Provide either a URL or raw_text")

    lines = [l.strip() for l in description_raw.split("\n") if l.strip()]
    title = lines[0] if lines else "Unknown"

    job = {
        "job_id":          str(uuid.uuid4()),
        "title":           title[:200],
        "company":         "",
        "location":        "",
        "salary_raw":      "",
        "description_raw": description_raw[:50000],
        "url":             url or "",
        "source":          source,
        "ingested_at":     datetime.now(timezone.utc).isoformat(),
    }
    return job


def insert_job(job: dict):
    """Insert a single job into BigQuery."""
    errors = client.insert_rows_json(TABLE, [job])
    if errors:
        raise Exception(f"BigQuery insert error: {errors}")
    print(f"\nInserted successfully!")
    print(f"Job ID: {job['job_id']}")
    print(f"Title:  {job['title']}")
    return job["job_id"]


if __name__ == "__main__":
    print("=== ReachOut AI — Job Description Ingester ===\n")

    choice = input("Do you have a URL? (y/n): ").strip().lower()

    if choice == "y":
        url = input("Paste the job URL: ").strip()
        job = parse_jd(url=url, source="seek")
    else:
        print("\nPaste the job description into 'job_temp.txt'")
        print("Save the file then press Enter here to continue...")
        input()

        with open("job_temp.txt", "r", encoding="utf-8") as f:
            raw_text = f.read().strip()

        if not raw_text:
            print("job_temp.txt is empty — please paste the job description and try again.")
            exit()

        job = parse_jd(raw_text=raw_text, source="manual")

    print("\nFill in a few details:")
    job["company"]    = input("Company name: ").strip()
    job["location"]   = input("Location (e.g. Sydney): ").strip()
    job["salary_raw"] = input("Salary (or press Enter to skip): ").strip()

    insert_job(job)

    # Clear the temp file after successful insert
    open("job_temp.txt", "w").close()

    print("\nCheck BigQuery — run this query:")
    print(f"SELECT * FROM `{os.getenv('GCP_PROJECT_ID')}.reachout.raw_jobs` ORDER BY ingested_at DESC LIMIT 5")