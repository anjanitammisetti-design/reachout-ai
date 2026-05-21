# ai/ats_scorer.py

import os
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from google.cloud import bigquery
import vertexai
from vertexai.generative_models import GenerativeModel
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

if not os.getenv("GCP_PROJECT_ID"):
    os.environ["GCP_PROJECT_ID"] = "reachout-ai-496806"
    os.environ["GCP_REGION"]     = "us-central1"
    os.environ["BQ_DATASET"]     = "reachout"

PROJECT = os.getenv("GCP_PROJECT_ID")
REGION  = os.getenv("GCP_REGION")
DATASET = os.getenv("BQ_DATASET")
TABLE   = f"{PROJECT}.{DATASET}.ats_scores"

vertexai.init(project=PROJECT, location=REGION)
bq_client = bigquery.Client(project=PROJECT)


def load_resume(path: str = "my_resume.txt") -> str:
    """Load resume text from file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def fetch_jd(job_id: str) -> dict:
    """Fetch job description from BigQuery."""
    query = f"""
        SELECT title, company, description_raw
        FROM `{PROJECT}.{DATASET}.raw_jobs`
        WHERE job_id = '{job_id}'
        LIMIT 1
    """
    rows = list(bq_client.query(query).result())
    if not rows:
        raise Exception(f"Job ID not found: {job_id}")
    return dict(rows[0])


def score_resume(jd_text: str, resume_text: str) -> dict:
    """
    Send resume + JD to Gemini and get back a structured ATS score.
    """
    model = GenerativeModel("gemini-2.5-flash")

    prompt = f"""
You are an expert ATS (Applicant Tracking System) and recruitment specialist.

Analyse the match between this resume and job description.

RESUME:
{resume_text}

JOB DESCRIPTION:
{jd_text}

Return ONLY a valid JSON object with this exact structure.
No markdown, no explanation, just the JSON:
{{
  "match_score": <integer 0-100>,
  "matched_keywords": ["keyword1", "keyword2"],
  "missing_keywords": ["keyword1", "keyword2"],
  "suggestions": [
    "Specific actionable suggestion 1",
    "Specific actionable suggestion 2",
    "Specific actionable suggestion 3"
  ],
  "summary": "One sentence summary of the match"
}}
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip markdown code fences if Gemini adds them
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())


def save_score(job_id: str, result: dict) -> str:
    """Save ATS score result to BigQuery."""
    row = {
        "score_id":        str(uuid.uuid4()),
        "job_id":          job_id,
        "resume_version":  "v1",
        "match_score":     float(result["match_score"]),
        "missing_keywords": json.dumps(result["missing_keywords"]),
        "suggestions":     json.dumps(result["suggestions"]),
        "scored_at":       datetime.now(timezone.utc).isoformat(),
    }
    errors = bq_client.insert_rows_json(TABLE, [row])
    if errors:
        raise Exception(f"BigQuery error: {errors}")
    return row["score_id"]


def print_results(job: dict, result: dict):
    """Print results in a readable format."""
    print("\n" + "="*60)
    print(f"Role:    {job['title']} at {job['company']}")
    print("="*60)
    print(f"\nMatch score:   {result['match_score']}%")
    print(f"Summary:       {result['summary']}")
    print(f"\nMatched keywords:")
    for kw in result["matched_keywords"]:
        print(f"  ✓ {kw}")
    print(f"\nMissing keywords:")
    for kw in result["missing_keywords"]:
        print(f"  ✗ {kw}")
    print(f"\nSuggestions to improve your resume:")
    for i, s in enumerate(result["suggestions"], 1):
        print(f"  {i}. {s}")
    print("="*60)


if __name__ == "__main__":
    print("=== ReachOut AI — ATS Score Engine ===\n")

    # List available jobs
    query = f"""
        SELECT job_id, title, company
        FROM `{PROJECT}.{DATASET}.raw_jobs`
        ORDER BY ingested_at DESC
        LIMIT 10
    """
    rows = list(bq_client.query(query).result())

    print("Your recent jobs:\n")
    for i, row in enumerate(rows, 1):
        print(f"  {i}. {row['company']} — {row['title']}")

    print()
    choice = input("Enter the number of the job to score (e.g. 1): ").strip()
    selected = rows[int(choice) - 1]
    job_id = selected["job_id"]

    print(f"\nScoring: {selected['company']} — {selected['title']}")

    job    = fetch_jd(job_id)
    resume = load_resume()
    result = score_resume(job["description_raw"], resume)

    print_results(job, result)

    save_it = input("\nSave this score to BigQuery? (y/n): ").strip().lower()
    if save_it == "y":
        score_id = save_score(job_id, result)
        print(f"Saved. Score ID: {score_id}")