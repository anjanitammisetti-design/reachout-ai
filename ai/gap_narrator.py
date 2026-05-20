"""
gap_narrator.py — Career Gap Narrative Generator
Part of ReachOut AI: AI-powered job search co-pilot for returning tech professionals

Uses Gemini via Vertex AI to generate a confident, honest, forward-looking
career gap explanation tailored to a specific job description.
"""

import os
import vertexai
from vertexai.generative_models import GenerativeModel
from google.cloud import bigquery
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "australia-southeast1")
BQ_DATASET = os.getenv("BQ_DATASET", "reachout")

# ─── Your gap details — update this with your real information ────────────────

MY_GAP = {
    "duration": "2 years (2024–2026)",
    "reasons": [
        "Relocated from India to Sydney, Australia",
        "Applied for and received Australian Permanent Residency",
        "Became a first-time mother and took parental leave",
        "Focused on family settlement during the transition period",
    ],
    "what_i_did_during_gap": [
        "Stayed current with GCP, BigQuery, dbt, and Airflow developments",
        "Built ReachOut AI — a full-stack AI job search tool using GCP, BigQuery, dbt, Airflow, Vertex AI, Gemini, and Streamlit",
        "Learned dbt, Vertex AI, Gemini, and Streamlit independently during the gap",
        "Self-taught Snowflake including architecture, virtual warehouses, and data sharing",
        "Continued personal projects and upskilling in cloud data engineering",
    ],
    "current_status": "Received Australian PR in 2025 and actively job searching",
    "core_skills": [
        "GCP Data Engineering",
        "BigQuery",
        "Apache Airflow",
        "Python",
        "SQL",
        "dbt",
        "Vertex AI",
        "Gemini API",
    ],
}

# ─── Prompt ───────────────────────────────────────────────────────────────────

GAP_NARRATOR_PROMPT = """
You are a career coach specialising in helping returning tech professionals re-enter the workforce.
Your tone is warm, confident, and direct — never apologetic or defensive.

A candidate is returning to work after a career gap. Here are the details of their gap:

Duration: {duration}

Reasons for the gap:
{reasons}

What they did during the gap:
{gap_activities}

Current status: {current_status}

Core technical skills: {skills}

They are applying for the following role:
---
Job Title: {job_title}
Job Description:
{job_description}
---

Write a confident, honest, forward-looking career gap explanation tailored specifically to this role.

Requirements:
- 3–4 sentences maximum — concise and natural, not a wall of text
- Open with the gap reason directly and matter-of-factly — no apology, no over-explanation
- Highlight what they built or learned during the gap that is directly relevant to this specific role
- Close with a forward-looking statement about being ready to contribute
- Tone should feel human, warm, and professional — not robotic or templated
- Do NOT use phrases like "I am proud to say", "I utilised my time", or "Despite the gap"
- Write in first person

Return ONLY the narrative text. No preamble, no labels, no formatting.
"""

# ─── BigQuery helpers ─────────────────────────────────────────────────────────

def fetch_job_from_bq(job_id: str) -> dict | None:
    """Fetch a job record from BigQuery by job_id."""
    client = bigquery.Client(project=GCP_PROJECT_ID)
    query = f"""
        SELECT job_id, job_title, job_description
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.raw_jobs`
        WHERE job_id = @job_id
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("job_id", "STRING", job_id)]
    )
    results = list(client.query(query, job_config=job_config).result())
    if not results:
        return None
    row = results[0]
    return {
        "job_id": row["job_id"],
        "job_title": row["job_title"],
        "job_description": row["job_description"],
    }


def save_narrative_to_bq(job_id: str, narrative: str) -> None:
    """Save the generated gap narrative back to BigQuery."""
    client = bigquery.Client(project=GCP_PROJECT_ID)
    table_id = f"{GCP_PROJECT_ID}.{BQ_DATASET}.gap_narratives"

    rows = [
        {
            "job_id": job_id,
            "narrative": narrative,
            "generated_at": bigquery.enums.SqlTypeNames.TIMESTAMP,
        }
    ]

    # Use INSERT via query to handle timestamp correctly
    query = f"""
        INSERT INTO `{table_id}` (job_id, narrative, generated_at)
        VALUES (@job_id, @narrative, CURRENT_TIMESTAMP())
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("job_id", "STRING", job_id),
            bigquery.ScalarQueryParameter("narrative", "STRING", narrative),
        ]
    )
    client.query(query, job_config=job_config).result()
    print(f"✅ Narrative saved to BigQuery for job_id: {job_id}")


# ─── Gemini narrative generator ───────────────────────────────────────────────

def generate_gap_narrative(job_title: str, job_description: str) -> str:
    """Generate a tailored career gap narrative using Gemini via Vertex AI."""
    vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
    model = GenerativeModel("gemini-1.5-flash")

    prompt = GAP_NARRATOR_PROMPT.format(
        duration=MY_GAP["duration"],
        reasons="\n".join(f"- {r}" for r in MY_GAP["reasons"]),
        gap_activities="\n".join(f"- {a}" for a in MY_GAP["what_i_did_during_gap"]),
        current_status=MY_GAP["current_status"],
        skills=", ".join(MY_GAP["core_skills"]),
        job_title=job_title,
        job_description=job_description,
    )

    response = model.generate_content(prompt)
    return response.text.strip()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n🎯 ReachOut AI — Career Gap Narrative Generator")
    print("─" * 50)

    mode = input("\nEnter job manually or load from BigQuery? (manual / bq): ").strip().lower()

    if mode == "bq":
        job_id = input("Enter job ID: ").strip()
        job = fetch_job_from_bq(job_id)
        if not job:
            print(f"❌ No job found with ID: {job_id}")
            return
        job_title = job["job_title"]
        job_description = job["job_description"]
        print(f"\n✅ Loaded: {job_title}")

    else:
        job_id = None
        job_title = input("\nJob title: ").strip()
        print("Paste the job description (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        job_description = "\n".join(lines)

    print("\n⏳ Generating your gap narrative with Gemini...")
    narrative = generate_gap_narrative(job_title, job_description)

    print("\n" + "─" * 50)
    print("📝 YOUR CAREER GAP NARRATIVE")
    print("─" * 50)
    print(f"\n{narrative}\n")
    print("─" * 50)

    if job_id:
        save = input("\nSave this narrative to BigQuery? (y/n): ").strip().lower()
        if save == "y":
            save_narrative_to_bq(job_id, narrative)

    copy = input("\nCopy to clipboard? (y/n): ").strip().lower()
    if copy == "y":
        try:
            import pyperclip
            pyperclip.copy(narrative)
            print("✅ Copied to clipboard!")
        except ImportError:
            print("⚠️  Install pyperclip to enable clipboard copy: pip install pyperclip")

    print("\n✨ Good luck with your application!\n")


if __name__ == "__main__":
    main()
