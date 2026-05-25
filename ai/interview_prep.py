# ai/interview_prep.py

import os
import uuid
import json
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
TABLE   = f"{PROJECT}.{DATASET}.interview_prep"

vertexai.init(project=PROJECT, location=REGION)
model     = GenerativeModel("gemini-2.5-flash")
bq_client = bigquery.Client(project=PROJECT)

# ── Your profile ──────────────────────────────────────────
MY_PROFILE = """
Name: Anjani Tammisetti
Role: Senior Data Engineer
Experience: 5.5+ years

KEY EXPERIENCE:
- At TCS: Led migration of 200+ Teradata stored procedures into
  BigQuery. Delivered 95%+ query performance improvement.
  Used Airflow for orchestration, GitHub for version control.
- At Cognizant: Enterprise PL/SQL development, batch processing,
  production support, SQL performance tuning.

Skills: GCP, BigQuery, Airflow, Python, SQL, PL/SQL, dbt
Certification: Google Associate Cloud Engineer (ACE)

Career gap: Planned break for relocation to Sydney and parental
            leave 2024-2026. Now actively returning.
Currently building: ReachOut AI — GCP, BigQuery, Airflow, dbt, Gemini
"""


# ── Helpers ───────────────────────────────────────────────

def fetch_jd(job_id: str) -> dict:
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


def generate_interview_prep(jd_text: str, job_title: str,
                             company: str) -> dict:
    """Ask Gemini to predict interview questions and draft answers."""

    prompt = f"""
You are an expert interview coach helping a Senior Data Engineer
prepare for a job interview.

MY PROFILE:
{MY_PROFILE}

JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION:
{jd_text[:3000]}

Generate interview preparation material for this specific role.

Return ONLY valid JSON — no markdown, no explanation:
{{
  "technical_questions": [
    {{
      "question": "Technical question based on the JD",
      "why_asked": "One sentence — why interviewers ask this",
      "suggested_answer": "Answer using MY real experience above — specific, not generic. Use the STAR method where relevant (Situation, Task, Action, Result)"
    }}
  ],
  "behavioural_questions": [
    {{
      "question": "Behavioural question e.g. Tell me about a time...",
      "why_asked": "One sentence — what they are testing",
      "suggested_answer": "Answer using MY real experience — specific story from TCS or Cognizant"
    }}
  ],
  "questions_to_ask_them": [
    "Smart question you should ask the interviewer 1",
    "Smart question you should ask the interviewer 2",
    "Smart question you should ask the interviewer 3"
  ],
  "key_talking_points": [
    "Most important thing to emphasise for THIS role",
    "Second most important point",
    "Third most important point"
  ],
  "gap_answer": "How to answer 'What have you been doing since January 2024?' — confident, honest, forward-looking"
}}

RULES:
- Generate exactly 5 technical questions and 5 behavioural questions
- Answers must reference MY specific experience — not generic advice
- Always mention the TCS Teradata to BigQuery migration where relevant
- The gap answer must sound confident and natural — not apologetic
- Questions to ask them should show strategic thinking about the role
"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())


def print_prep(prep: dict, job_title: str, company: str):
    """Print interview prep in a readable format."""

    print(f"\n{'='*60}")
    print(f"INTERVIEW PREP — {job_title} at {company}")
    print(f"{'='*60}")

    print(f"\n📌 KEY TALKING POINTS")
    print("-" * 40)
    for i, point in enumerate(prep.get("key_talking_points", []), 1):
        print(f"  {i}. {point}")

    print(f"\n💬 GAP ANSWER")
    print("-" * 40)
    print(f"  Q: What have you been doing since January 2024?")
    print(f"  A: {prep.get('gap_answer', '')}")

    print(f"\n🔧 TECHNICAL QUESTIONS")
    print("-" * 40)
    for i, q in enumerate(prep.get("technical_questions", []), 1):
        print(f"\n  Q{i}: {q['question']}")
        print(f"  Why asked: {q['why_asked']}")
        print(f"  Your answer: {q['suggested_answer']}")

    print(f"\n🤝 BEHAVIOURAL QUESTIONS")
    print("-" * 40)
    for i, q in enumerate(prep.get("behavioural_questions", []), 1):
        print(f"\n  Q{i}: {q['question']}")
        print(f"  Why asked: {q['why_asked']}")
        print(f"  Your answer: {q['suggested_answer']}")

    print(f"\n❓ QUESTIONS TO ASK THEM")
    print("-" * 40)
    for i, q in enumerate(prep.get("questions_to_ask_them", []), 1):
        print(f"  {i}. {q}")

    print(f"\n{'='*60}\n")


def save_to_bigquery(job_id: str, prep: dict) -> str:
    """Save interview prep to BigQuery."""
    row = {
        "prep_id":    str(uuid.uuid4()),
        "job_id":     job_id,
        "questions":  json.dumps(prep.get("technical_questions", []) +
                                  prep.get("behavioural_questions", [])),
        "answers":    json.dumps({
            "key_talking_points":  prep.get("key_talking_points", []),
            "gap_answer":          prep.get("gap_answer", ""),
            "questions_to_ask":    prep.get("questions_to_ask_them", []),
        }),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = bq_client.insert_rows_json(TABLE, [row])
    if errors:
        raise Exception(f"BigQuery error: {errors}")
    return row["prep_id"]


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ReachOut AI — Interview Question Predictor ===\n")

    # List recent jobs
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
    choice   = input("Enter the number of the job to prepare for: ").strip()
    selected = rows[int(choice) - 1]
    job_id   = selected["job_id"]

    print(f"\nPreparing for: {selected['company']} — {selected['title']}")
    print("Generating questions and answers... (15-20 seconds)\n")

    job  = fetch_jd(job_id)
    prep = generate_interview_prep(
        job["description_raw"],
        job["title"],
        job["company"]
    )

    print_prep(prep, job["title"], job["company"])

    save_it = input("Save this prep to BigQuery? (y/n): ").strip().lower()
    if save_it == "y":
        prep_id = save_to_bigquery(job_id, prep)
        print(f"Saved. Prep ID: {prep_id}")

    print("\nGood luck with your interview! 🎯")