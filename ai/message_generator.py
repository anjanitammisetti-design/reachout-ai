MY_PROFILE = """
Name: Anjani Tammisetti
Current location: Sydney, Australia
Background: Data Engineer with experience in GCP, BigQuery, Airflow, Python, SQL
Previous companies: Tata Consultancy Services(TCS), Cognizant
Career gap: Relocated from India to Sydney for Australian PR (Applied: Feb 2024, received Apr 2025), parental leave 2025-2026
Now: Actively returning to data engineering, upskilling in Vertex AI, dbt, and AI pipelines
Key strengths: GCP-native pipelines, BigQuery at scale, Airflow orchestration
"""
# ai/message_generator.py

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

PROJECT  = os.getenv("GCP_PROJECT_ID")
REGION   = os.getenv("GCP_REGION")
DATASET  = os.getenv("BQ_DATASET")
TABLE    = f"{PROJECT}.{DATASET}.outreach_log"

vertexai.init(project=PROJECT, location=REGION)
model     = GenerativeModel("gemini-2.5-flash")
bq_client = bigquery.Client(project=PROJECT)

# ── Your profile ──────────────────────────────────────────
MY_PROFILE = """
Name: Anjani Tammisetti
Location: Sydney, NSW, Australia
Visa: Australian Permanent Resident (SC 309)
Experience: Senior Data Engineer with 5.5+ years

KEY ACHIEVEMENT TO ALWAYS MENTION:
At TCS, led migration of 200+ Teradata stored procedures and legacy
transformations into BigQuery — delivered 95%+ improvement in query
execution time. This is my strongest and most relevant achievement.

Core skills: GCP, BigQuery, Airflow, Python, SQL, dbt
Previous roles:
  - Senior Data Engineer at TCS (client: Bed Bath & Beyond) Mar 2022 – Jan 2024
    → Teradata to BigQuery migration, pipeline development, Airflow orchestration
  - PL/SQL Developer at Cognizant (client: Total Gas & Power) Aug 2018 – Mar 2022
    → Enterprise PL/SQL, batch processing, production support

Career gap: Took a planned break — relocated from India to Sydney,
            obtained Australian PR, welcomed first child.
            Now actively returning to data engineering.

Currently building: ReachOut AI — an end-to-end AI-powered job search
                    tool using GCP, BigQuery, Airflow, dbt, and Gemini

Certification: Google Associate Cloud Engineer (ACE)
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


def generate_message(jd_text: str, job_title: str, company: str,
                      contact_name: str, contact_role: str,
                      channel: str) -> str:
    """Generate personalised outreach message using Gemini."""

    if channel == "email":
        format_instruction = """
Write a professional email of 150-200 words.
Start with: Subject: [write a specific subject line]
Then a blank line.
Then the email body.
End with:
Best regards,
Anjani Tammisetti
+61 422 480 664
anjani.tammisetti@gmail.com
LinkedIn: https://www.linkedin.com/in/anjani-tammisetti-8ab793114/
"""
    else:
        format_instruction = """
Write a concise LinkedIn connection note of maximum 300 characters.
No subject line. No signature. Just a warm, specific, human message.
"""

    prompt = f"""
You are helping a Senior Data Engineer write a short, human, direct
outreach message. It should sound like a real person wrote it —
not a cover letter, not a template.

MY PROFILE:
{MY_PROFILE}

JOB TITLE: {job_title}
COMPANY: {company}
CONTACT NAME: {contact_name}
CONTACT ROLE: {contact_role}
CHANNEL: {channel}

JOB DESCRIPTION (excerpt):
{jd_text[:2000]}

{format_instruction}

RULES — follow these strictly:
- NEVER start with "I'm writing to express my interest"
- NEVER start with "I hope this finds you well"
- NEVER use: resonate, leverage, synergy, passionate, eager, dynamic
- NEVER say "having recently returned to the workforce" — too apologetic
- DO open with something specific about the role or a real observation
  e.g. "The migration work you described at {company} is exactly the
  kind of problem I have spent 5 years solving"
- ONE sentence about your experience — specific, not generic
- Gap explanation — one casual confident sentence, NOT apologetic
  e.g. "I took a planned break to relocate to Sydney and for parental
  leave — now back and actively looking"
- ONE concrete proof you are current — mention ReachOut AI briefly
- End with ONE simple question — not "I would welcome the opportunity"
  e.g. "Would a quick call this week work for you?"
- Email: maximum 150 words — short emails get read
- LinkedIn: maximum 300 characters — punchy and direct
- Read it back — if it sounds like a robot wrote it, rewrite it
- ALWAYS mention the TCS Teradata to BigQuery migration — it is the
  most relevant and impressive achievement for data engineering roles
- Lead with the achievement that is most relevant to THIS specific JD
"""

    response = model.generate_content(prompt)
    return response.text.strip()


def save_outreach(job_id: str, contact_name: str, contact_role: str,
                   channel: str, message_text: str) -> str:
    """Save outreach record to BigQuery."""
    row = {
        "outreach_id":   str(uuid.uuid4()),
        "job_id":        job_id,
        "contact_name":  contact_name,
        "contact_role":  contact_role,
        "channel":       channel,
        "sent_at":       datetime.now(timezone.utc).isoformat(),
        "message_text":  message_text,
        "replied":       False,
        "replied_at":    None,
        "follow_up_due": False,
        "notes":         "",
    }
    errors = bq_client.insert_rows_json(TABLE, [row])
    if errors:
        raise Exception(f"BigQuery error: {errors}")
    return row["outreach_id"]


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== ReachOut AI — Outreach Message Generator ===\n")

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
    choice   = input("Enter the number of the job: ").strip()
    selected = rows[int(choice) - 1]
    job_id   = selected["job_id"]

    print(f"\nSelected: {selected['company']} — {selected['title']}")

    # Contact details
    print()
    contact_name = input("Contact name (e.g. Sarah Chen): ").strip()
    contact_role = input("Contact role (e.g. Recruiter / Hiring Manager): ").strip()

    print()
    print("Channel:")
    print("  1. Email")
    print("  2. LinkedIn note")
    channel_choice = input("Enter 1 or 2: ").strip()
    channel = "email" if channel_choice == "1" else "linkedin"

    # Generate message
    print(f"\nGenerating {channel} message... (5-10 seconds)\n")
    job     = fetch_jd(job_id)
    message = generate_message(
        job["description_raw"],
        job["title"],
        job["company"],
        contact_name,
        contact_role,
        channel
    )

    print("=" * 60)
    print(message)
    print("=" * 60)

    # Save option
    print()
    save_it = input("Save this to BigQuery as sent? (y/n): ").strip().lower()
    if save_it == "y":
        oid = save_outreach(job_id, contact_name, contact_role,
                             channel, message)
        print(f"Saved. Outreach ID: {oid}")

    print("\nCopy the message above and send it!")