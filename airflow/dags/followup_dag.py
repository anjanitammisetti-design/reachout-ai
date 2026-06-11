import os
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

PROJECT = os.getenv("GCP_PROJECT_ID", "reachout-ai-496806")
DATASET = os.getenv("BQ_DATASET", "reachout")
REGION  = os.getenv("GCP_REGION", "us-central1")


# ── DAG 1 tasks — follow-up reminders ────────────────────

def flag_stale_outreach():
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    query  = f"""
        UPDATE `{PROJECT}.{DATASET}.outreach_log`
        SET follow_up_due = TRUE
        WHERE replied = FALSE
          AND follow_up_due = FALSE
          AND TIMESTAMP_DIFF(
              CURRENT_TIMESTAMP(), sent_at, DAY
          ) >= 5
    """
    client.query(query).result()
    print("Stale outreach flagged successfully.")


def draft_follow_ups():
    import vertexai
    from vertexai.generative_models import GenerativeModel
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)
    query  = f"""
        SELECT
            o.outreach_id,
            o.contact_name,
            o.channel,
            o.message_text,
            o.sent_at,
            j.title,
            j.company,
            TIMESTAMP_DIFF(
                CURRENT_TIMESTAMP(), o.sent_at, DAY
            ) AS days_waiting
        FROM `{PROJECT}.{DATASET}.outreach_log` o
        JOIN `{PROJECT}.{DATASET}.raw_jobs` j
          USING (job_id)
        WHERE o.follow_up_due = TRUE
          AND o.replied = FALSE
        ORDER BY o.sent_at ASC
    """
    rows = list(client.query(query).result())

    if not rows:
        print("No follow-ups needed today.")
        return

    vertexai.init(project=PROJECT, location=REGION)
    model = GenerativeModel("gemini-2.5-flash")

    print(f"\n{'='*50}")
    print(f"FOLLOW-UPS DUE — {len(rows)} contact(s)")
    print(f"{'='*50}")

    for row in rows:
        print(f"\n📧 {row['company']} — {row['title']}")
        print(f"   Contact: {row['contact_name']} via {row['channel']}")
        print(f"   Waiting: {row['days_waiting']} days")

        prompt = f"""
Write a very short, friendly follow-up message.
The original message was sent {row['days_waiting']} days ago
to {row['contact_name']} about a {row['title']} role at {row['company']}.

Original message:
{row['message_text'][:500]}

Rules:
- Maximum 3 sentences
- Friendly, not pushy
- Reference the original message briefly
- End with a simple question
- Sound human, not robotic
"""
        response = model.generate_content(prompt)
        print(f"\n   Suggested follow-up:")
        print(f"   {response.text.strip()}")
        print()


# ── DAG 2 tasks — weekly report ───────────────────────────

def generate_weekly_report():
    from google.cloud import bigquery

    client = bigquery.Client(project=PROJECT)

    jobs_query = f"""
        SELECT COUNT(*) AS count
        FROM `{PROJECT}.{DATASET}.raw_jobs`
        WHERE ingested_at >= TIMESTAMP_SUB(
            CURRENT_TIMESTAMP(), INTERVAL 7 DAY
        )
    """

    outreach_query = f"""
        SELECT
            COUNT(*)                                    AS total_sent,
            COUNTIF(replied = TRUE)                     AS total_replied,
            COUNTIF(follow_up_due = TRUE
                AND replied = FALSE)                    AS follow_ups_due,
            COUNTIF(channel = 'email')                  AS emails_sent,
            COUNTIF(channel = 'linkedin')               AS linkedin_sent
        FROM `{PROJECT}.{DATASET}.outreach_log`
        WHERE sent_at >= TIMESTAMP_SUB(
            CURRENT_TIMESTAMP(), INTERVAL 7 DAY
        )
    """

    ats_query = f"""
        SELECT
            ROUND(AVG(match_score), 1) AS avg_score,
            MAX(match_score)           AS best_score,
            COUNT(*)                   AS roles_scored
        FROM `{PROJECT}.{DATASET}.ats_scores`
        WHERE scored_at >= TIMESTAMP_SUB(
            CURRENT_TIMESTAMP(), INTERVAL 7 DAY
        )
    """

    jobs_result     = list(client.query(jobs_query).result())[0]
    outreach_result = list(client.query(outreach_query).result())[0]
    ats_result      = list(client.query(ats_query).result())[0]

    total_sent    = outreach_result["total_sent"] or 0
    total_replied = outreach_result["total_replied"] or 0
    reply_rate    = round((total_replied / total_sent * 100), 1) if total_sent > 0 else 0

    print(f"\n{'='*50}")
    print(f"WEEKLY JOB SEARCH REPORT")
    print(f"{datetime.now().strftime('%A %d %B %Y')}")
    print(f"{'='*50}")

    print(f"\n📋 THIS WEEK'S ACTIVITY")
    print(f"   Jobs added:        {jobs_result['count']}")
    print(f"   Roles scored:      {ats_result['roles_scored']}")
    print(f"   Avg ATS score:     {ats_result['avg_score']}%")
    print(f"   Best ATS score:    {ats_result['best_score']}%")

    print(f"\n📧 OUTREACH SUMMARY")
    print(f"   Emails sent:       {outreach_result['emails_sent']}")
    print(f"   LinkedIn sent:     {outreach_result['linkedin_sent']}")
    print(f"   Total outreach:    {total_sent}")
    print(f"   Replies received:  {total_replied}")
    print(f"   Reply rate:        {reply_rate}%")
    print(f"   Follow-ups due:    {outreach_result['follow_ups_due']}")

    print(f"\n💡 RECOMMENDATIONS FOR NEXT WEEK")
    if total_sent == 0:
        print("   → Send at least 5 outreach messages this week")
    elif reply_rate < 10:
        print("   → Reply rate is low — try personalising messages more")
    elif reply_rate >= 20:
        print("   → Great reply rate! Keep up the outreach momentum")

    if outreach_result["follow_ups_due"] > 0:
        print(f"   → {outreach_result['follow_ups_due']} follow-up(s) overdue — send them today")

    if ats_result["avg_score"] and float(ats_result["avg_score"]) < 70:
        print("   → Average ATS score is below 70% — focus on higher match roles")

    print(f"\n{'='*50}\n")


# ── DAG 1 — Follow-up reminders ───────────────────────────

default_args = {
    "owner":       "reachout",
    "retries":     1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="reachout_followup_reminder",
    default_args=default_args,
    description="Daily check for outreach needing follow-up",
    schedule_interval="0 8 * * *",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["reachout", "followup"],
) as dag1:

    flag_task = PythonOperator(
        task_id="flag_stale_outreach",
        python_callable=flag_stale_outreach,
    )

    draft_task = PythonOperator(
        task_id="draft_follow_up_messages",
        python_callable=draft_follow_ups,
    )

    flag_task >> draft_task


# ── DAG 2 — Weekly report ─────────────────────────────────

with DAG(
    dag_id="reachout_weekly_report",
    default_args=default_args,
    description="Weekly job search summary every Sunday",
    schedule_interval="0 9 * * 0",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["reachout", "report"],
) as dag2:

    report_task = PythonOperator(
        task_id="generate_weekly_report",
        python_callable=generate_weekly_report,
    )
