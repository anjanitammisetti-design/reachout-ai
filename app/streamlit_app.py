# app/streamlit_app.py

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

import streamlit as st
import pandas as pd
from google.cloud import bigquery
from dotenv import load_dotenv

# ── Setup ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

if not os.getenv("GCP_PROJECT_ID"):
    os.environ["GCP_PROJECT_ID"] = "reachout-ai-496806"
    os.environ["GCP_REGION"]     = "us-central1"
    os.environ["BQ_DATASET"]     = "reachout"

PROJECT = os.getenv("GCP_PROJECT_ID")
DATASET = os.getenv("BQ_DATASET")
REGION  = os.getenv("GCP_REGION")

st.set_page_config(
    page_title="ReachOut AI",
    page_icon="💼",
    layout="wide"
)

# ── Session state ─────────────────────────────────────────
if "resume_text" not in st.session_state:
    st.session_state.resume_text     = None
if "resume_filename" not in st.session_state:
    st.session_state.resume_filename = None

# ── Resume helper ─────────────────────────────────────────
def read_resume(uploaded_file) -> str:
    """Read resume from txt or docx upload."""
    if uploaded_file.name.endswith(".docx"):
        import docx
        doc = docx.Document(uploaded_file)
        return "\n".join([
            para.text for para in doc.paragraphs
            if para.text.strip()
        ])
    else:
        content = uploaded_file.read()
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return content.decode("windows-1252")

# ── BigQuery client ───────────────────────────────────────
@st.cache_resource
def get_bq_client():
    return bigquery.Client(project=PROJECT)

client = get_bq_client()

# ── Data loaders ──────────────────────────────────────────
@st.cache_data(ttl=30)
def load_pipeline():
    query = f"""
        SELECT
            j.job_id,
            j.title,
            j.company,
            j.location,
            j.url,
            j.ingested_at,
            COALESCE(a.match_score, 0)    AS ats_score,
            a.missing_keywords,
            a.suggestions,
            o.outreach_id,
            o.contact_name,
            o.channel,
            o.sent_at,
            o.replied,
            o.follow_up_due,
            CASE
                WHEN o.replied = TRUE        THEN 'Replied'
                WHEN o.follow_up_due = TRUE  THEN 'Follow-up due'
                WHEN o.sent_at IS NOT NULL   THEN 'Outreach sent'
                ELSE 'Not contacted'
            END AS status
        FROM `{PROJECT}.{DATASET}.raw_jobs` j
        LEFT JOIN (
            SELECT * FROM `{PROJECT}.{DATASET}.ats_scores`
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY job_id ORDER BY scored_at DESC
            ) = 1
        ) a USING (job_id)
        LEFT JOIN (
            SELECT * FROM `{PROJECT}.{DATASET}.outreach_log`
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY job_id ORDER BY sent_at DESC
            ) = 1
        ) o USING (job_id)
        ORDER BY j.ingested_at DESC
    """
    return client.query(query).to_dataframe()


@st.cache_data(ttl=30)
def load_stats():
    query = f"""
        SELECT
            (SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.raw_jobs`) AS total_jobs,
            (SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.outreach_log`) AS total_outreach,
            (SELECT COUNTIF(replied=TRUE) FROM `{PROJECT}.{DATASET}.outreach_log`) AS total_replied,
            (SELECT COUNTIF(follow_up_due=TRUE AND replied=FALSE) FROM `{PROJECT}.{DATASET}.outreach_log`) AS follow_ups_due,
            (SELECT ROUND(AVG(match_score),1) FROM `{PROJECT}.{DATASET}.ats_scores`) AS avg_ats_score
    """
    rows = list(client.query(query).result())
    return dict(rows[0]) if rows else {}


# ── Sidebar ───────────────────────────────────────────────
st.sidebar.title("ReachOut AI")
st.sidebar.caption("Your AI job search co-pilot")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Pipeline", "Add Job", "Score Resume",
     "Tailor Resume", "Find Email",
     "Generate Message", "Interview Prep"]
)

st.sidebar.divider()
st.sidebar.markdown("**My Resume**")
sidebar_resume = st.sidebar.file_uploader(
    "Upload once, use everywhere",
    type=["txt", "docx"],
    key="sidebar_resume"
)
if sidebar_resume:
    st.session_state.resume_text     = read_resume(sidebar_resume)
    st.session_state.resume_filename = sidebar_resume.name
    st.sidebar.success(f"✅ {sidebar_resume.name}")

if st.session_state.resume_filename:
    st.sidebar.caption(f"Loaded: {st.session_state.resume_filename}")

st.sidebar.divider()
st.sidebar.caption(f"Project: `{PROJECT}`")
st.sidebar.caption(f"Dataset: `{DATASET}`")


# ══════════════════════════════════════════════════════════
# PAGE 1 — Pipeline
# ══════════════════════════════════════════════════════════
if page == "Pipeline":
    st.title("ReachOut AI — Job Pipeline")

    stats = load_stats()
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Roles tracked",  int(stats.get("total_jobs", 0)))
    col2.metric("Outreach sent",  int(stats.get("total_outreach", 0)))
    col3.metric("Replies",        int(stats.get("total_replied", 0)))
    col4.metric("Follow-ups due", int(stats.get("follow_ups_due", 0)))
    col5.metric("Avg ATS score",  f"{stats.get('avg_ats_score') or 0}%")

    st.divider()

    df = load_pipeline()
    if df.empty:
        st.info("No jobs yet — go to Add Job to get started!")
    else:
        st.subheader(f"Your pipeline — {len(df)} roles")
        for _, row in df.iterrows():
            ats    = int(row["ats_score"]) if row["ats_score"] else 0
            status = row["status"]
            if status == "Replied":
                icon = "🟢"
            elif status == "Follow-up due":
                icon = "🔴"
            elif status == "Outreach sent":
                icon = "🔵"
            else:
                icon = "⚪"

            with st.expander(
                f"{icon}  **{row['company']}** — {row['title']}  "
                f"|  ATS: {ats}%  |  {status}"
            ):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.markdown("**Role details**")
                    st.write(f"📍 {row['location']}")
                    st.write(f"📅 Added: {str(row['ingested_at'])[:10]}")
                    if row["url"]:
                        st.markdown(f"[View job posting ↗]({row['url']})")
                with col_b:
                    st.markdown("**ATS score**")
                    st.progress(ats / 100)
                    st.caption(f"{ats}% match")
                    if row["missing_keywords"]:
                        try:
                            missing = json.loads(row["missing_keywords"])
                            st.caption(f"Missing: {', '.join(missing[:5])}")
                        except:
                            st.caption(f"Missing: {row['missing_keywords']}")
                with col_c:
                    st.markdown("**Outreach**")
                    if pd.notna(row.get("sent_at")):
                        st.write(f"📧 {row['channel']} → {row['contact_name']}")
                        if row["replied"]:
                            st.success("They replied!")
                        elif row["follow_up_due"]:
                            st.warning("Follow-up overdue")
                        else:
                            st.info("Waiting for reply")
                    else:
                        st.write("Not contacted yet")


# ══════════════════════════════════════════════════════════
# PAGE 2 — Add Job
# ══════════════════════════════════════════════════════════
elif page == "Add Job":
    st.title("➕ Add Job")
    st.caption("Paste a Seek or LinkedIn job URL to add it to your pipeline")

    url      = st.text_input("Job URL")
    company  = st.text_input("Company name")
    location = st.text_input("Location (e.g. Sydney, NSW)")
    salary   = st.text_input("Salary (optional)")

    if st.button("Add Job to Pipeline", type="primary"):
        if not url or not company:
            st.error("Please enter a URL and company name")
        else:
            with st.spinner("Fetching job description..."):
                try:
                    from ingestion.parse_jd import parse_jd, insert_job
                    job               = parse_jd(url=url, source="seek")
                    job["company"]    = company
                    job["location"]   = location
                    job["salary_raw"] = salary
                    job_id            = insert_job(job)
                    st.success(f"Job added! ID: `{job_id[:8]}...`")
                    st.balloons()
                    load_pipeline.clear()
                    load_stats.clear()
                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════
# PAGE 3 — Score Resume
# ══════════════════════════════════════════════════════════
elif page == "Score Resume":
    st.title("📊 Score Resume")
    st.caption("Compare your resume against a job description")

    if not st.session_state.resume_text:
        st.warning("Please upload your resume in the sidebar first")
    else:
        st.success(f"Resume loaded: {st.session_state.resume_filename}")
        df = load_pipeline()
        if df.empty:
            st.info("Add jobs first from the Add Job page")
        else:
            options  = {
                f"{row['company']} — {row['title']}": row["job_id"]
                for _, row in df.iterrows()
            }
            selected = st.selectbox("Select a job to score against", list(options.keys()))

            if st.button("Score My Resume", type="primary"):
                job_id = options[selected]
                with st.spinner("Analysing with Gemini... (10-15 seconds)"):
                    try:
                        from ai.ats_scorer import fetch_jd, score_resume, save_score
                        job    = fetch_jd(job_id)
                        result = score_resume(
                            job["description_raw"],
                            st.session_state.resume_text
                        )

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Match Score", f"{result['match_score']}%")
                            st.progress(result["match_score"] / 100)
                        with col2:
                            st.write(result["summary"])

                        col3, col4 = st.columns(2)
                        with col3:
                            st.markdown("**✅ Matched keywords**")
                            for kw in result.get("matched_keywords", []):
                                st.write(f"- {kw}")
                        with col4:
                            st.markdown("**❌ Missing keywords**")
                            for kw in result.get("missing_keywords", []):
                                st.write(f"- {kw}")

                        st.markdown("**💡 Suggestions**")
                        for s in result.get("suggestions", []):
                            st.write(f"- {s}")

                        save_score(job_id, result)
                        st.success("Score saved to BigQuery!")
                        load_pipeline.clear()
                        load_stats.clear()

                    except Exception as e:
                        st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════
# PAGE 4 — Tailor Resume
# ══════════════════════════════════════════════════════════
elif page == "Tailor Resume":
    st.title("📝 Tailor Resume")
    st.caption("Gemini rewrites your resume for the specific role")

    if not st.session_state.resume_text:
        st.warning("Please upload your resume in the sidebar first")
    else:
        st.success(f"Resume loaded: {st.session_state.resume_filename}")
        df = load_pipeline()
        if df.empty:
            st.info("Add jobs first from the Add Job page")
        else:
            options  = {
                f"{row['company']} — {row['title']}": row["job_id"]
                for _, row in df.iterrows()
            }
            selected = st.selectbox("Select a job", list(options.keys()))

            if st.button("Tailor My Resume", type="primary"):
                job_id = options[selected]
                with st.spinner("Tailoring with Gemini... (15-20 seconds)"):
                    try:
                        from ai.resume_tailor import (
                            fetch_jd, get_tailored_content,
                            build_docx, save_to_bigquery
                        )
                        job      = fetch_jd(job_id)
                        tailored = get_tailored_content(
                            st.session_state.resume_text,
                            job["description_raw"],
                            job["title"],
                            job["company"]
                        )
                        filename = build_docx(
                            tailored, job["title"], job["company"]
                        )
                        save_to_bigquery(
                            job_id,
                            st.session_state.resume_text,
                            tailored,
                            filename
                        )

                        st.success("Resume tailored successfully!")
                        st.write(f"Keywords added: {', '.join(tailored.get('keywords_added', []))}")

                        with open(filename, "rb") as f:
                            st.download_button(
                                label="📥 Download Tailored Resume",
                                data=f,
                                file_name=filename.split("/")[-1],
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                            )
                    except Exception as e:
                        st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════
# PAGE 5 — Find Email
# ══════════════════════════════════════════════════════════
elif page == "Find Email":
    st.title("🔍 Find Recruiter Email")
    st.caption("Find a recruiter's direct email using Hunter.io")

    company    = st.text_input("Company name (e.g. Atlassian)")
    first_name = st.text_input("Recruiter first name")
    last_name  = st.text_input("Recruiter last name")

    if st.button("Find Email", type="primary"):
        if not company or not first_name or not last_name:
            st.error("Please fill in all fields")
        else:
            with st.spinner("Searching Hunter.io..."):
                try:
                    from ai.email_finder import (
                        find_domain, find_email, guess_email_patterns
                    )
                    domain = find_domain(company)
                    st.write(f"Domain found: `{domain}`")
                    result = find_email(first_name, last_name, domain)

                    if result["email"]:
                        st.success(f"Email found: **{result['email']}**")
                        st.write(f"Confidence: {result['score']}/100")
                        st.write(f"Status: {result['status']}")
                        st.code(result["email"])
                    else:
                        st.warning("No verified email found. Here are likely patterns:")
                        patterns = guess_email_patterns(
                            first_name, last_name, domain
                        )
                        for p in patterns:
                            st.code(p)

                except Exception as e:
                    st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════
# PAGE 6 — Generate Message
# ══════════════════════════════════════════════════════════
elif page == "Generate Message":
    st.title("✉️ Generate Outreach Message")
    st.caption("Personalised email or LinkedIn note drafted by Gemini")

    df = load_pipeline()
    if df.empty:
        st.info("Add jobs first from the Add Job page")
    else:
        options      = {
            f"{row['company']} — {row['title']}": row["job_id"]
            for _, row in df.iterrows()
        }
        selected     = st.selectbox("Select a job", list(options.keys()))
        contact_name = st.text_input("Contact name (e.g. Sarah Chen)")
        contact_role = st.text_input("Contact role (e.g. Recruiter)")
        channel      = st.radio("Channel", ["email", "linkedin"], horizontal=True)

        if st.button("Generate Message", type="primary"):
            if not contact_name or not contact_role:
                st.error("Please enter contact details")
            else:
                job_id = options[selected]
                with st.spinner("Drafting with Gemini... (5-10 seconds)"):
                    try:
                        from ai.message_generator import (
                            fetch_jd, generate_message, save_outreach
                        )
                        job     = fetch_jd(job_id)
                        message = generate_message(
                            job["description_raw"],
                            job["title"],
                            job["company"],
                            contact_name,
                            contact_role,
                            channel
                        )
                        st.markdown("**Generated message:**")
                        st.text_area("Copy this message", message, height=300)

                        if st.button("Save as Sent"):
                            save_outreach(
                                job_id, contact_name,
                                contact_role, channel, message
                            )
                            st.success("Saved to BigQuery!")
                            load_pipeline.clear()
                            load_stats.clear()

                    except Exception as e:
                        st.error(f"Error: {e}")


# ══════════════════════════════════════════════════════════
# PAGE 7 — Interview Prep
# ══════════════════════════════════════════════════════════
elif page == "Interview Prep":
    st.title("🎤 Interview Prep")
    st.caption("Gemini predicts interview questions and drafts answers from your experience")

    df = load_pipeline()
    if df.empty:
        st.info("Add jobs first from the Add Job page")
    else:
        options  = {
            f"{row['company']} — {row['title']}": row["job_id"]
            for _, row in df.iterrows()
        }
        selected = st.selectbox("Select a job to prepare for", list(options.keys()))

        if st.button("Generate Interview Prep", type="primary"):
            job_id = options[selected]
            with st.spinner("Generating questions... (15-20 seconds)"):
                try:
                    from ai.interview_prep import (
                        fetch_jd, generate_interview_prep,
                        save_to_bigquery
                    )
                    job  = fetch_jd(job_id)
                    prep = generate_interview_prep(
                        job["description_raw"],
                        job["title"],
                        job["company"]
                    )

                    st.markdown("### 💬 Gap answer")
                    st.info(prep.get("gap_answer", ""))

                    st.markdown("### 📌 Key talking points")
                    for point in prep.get("key_talking_points", []):
                        st.write(f"- {point}")

                    st.markdown("### 🔧 Technical questions")
                    for i, q in enumerate(
                        prep.get("technical_questions", []), 1
                    ):
                        with st.expander(f"Q{i}: {q['question']}"):
                            st.caption(f"Why asked: {q['why_asked']}")
                            st.write(q["suggested_answer"])

                    st.markdown("### 🤝 Behavioural questions")
                    for i, q in enumerate(
                        prep.get("behavioural_questions", []), 1
                    ):
                        with st.expander(f"Q{i}: {q['question']}"):
                            st.caption(f"Why asked: {q['why_asked']}")
                            st.write(q["suggested_answer"])

                    st.markdown("### ❓ Questions to ask them")
                    for q in prep.get("questions_to_ask_them", []):
                        st.write(f"- {q}")

                    save_to_bigquery(job_id, prep)
                    st.success("Saved to BigQuery!")

                except Exception as e:
                    st.error(f"Error: {e}")