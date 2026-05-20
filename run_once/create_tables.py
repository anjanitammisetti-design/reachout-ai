# run_once/create_tables.py

from google.cloud import bigquery
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))
dataset = os.getenv("BQ_DATASET")

schemas = {
    "raw_jobs": [
        bigquery.SchemaField("job_id", "STRING"),
        bigquery.SchemaField("title", "STRING"),
        bigquery.SchemaField("company", "STRING"),
        bigquery.SchemaField("location", "STRING"),
        bigquery.SchemaField("salary_raw", "STRING"),
        bigquery.SchemaField("description_raw", "STRING"),
        bigquery.SchemaField("url", "STRING"),
        bigquery.SchemaField("source", "STRING"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    ],
    "outreach_log": [
        bigquery.SchemaField("outreach_id", "STRING"),
        bigquery.SchemaField("job_id", "STRING"),
        bigquery.SchemaField("contact_name", "STRING"),
        bigquery.SchemaField("contact_role", "STRING"),
        bigquery.SchemaField("channel", "STRING"),
        bigquery.SchemaField("sent_at", "TIMESTAMP"),
        bigquery.SchemaField("message_text", "STRING"),
        bigquery.SchemaField("replied", "BOOLEAN"),
        bigquery.SchemaField("replied_at", "TIMESTAMP"),
        bigquery.SchemaField("follow_up_due", "BOOLEAN"),
        bigquery.SchemaField("notes", "STRING"),
    ],
    "ats_scores": [
        bigquery.SchemaField("score_id", "STRING"),
        bigquery.SchemaField("job_id", "STRING"),
        bigquery.SchemaField("resume_version", "STRING"),
        bigquery.SchemaField("match_score", "FLOAT"),
        bigquery.SchemaField("missing_keywords", "STRING"),
        bigquery.SchemaField("suggestions", "STRING"),
        bigquery.SchemaField("scored_at", "TIMESTAMP"),
    ],
    "gap_narratives": [
        bigquery.SchemaField("narrative_id", "STRING"),
        bigquery.SchemaField("job_id", "STRING"),
        bigquery.SchemaField("gap_reason", "STRING"),
        bigquery.SchemaField("narrative_text", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
    ],
}

for table_name, schema in schemas.items():
    table_ref = f"{os.getenv('GCP_PROJECT_ID')}.{dataset}.{table_name}"
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)
    print(f"Created: {table_name}")

print("\nAll tables created successfully!")