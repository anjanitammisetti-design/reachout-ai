# ReachOut AI 
### An AI-powered job search co-pilot for returning tech professionals

> Built on GCP · BigQuery · dbt · Airflow · Vertex AI · Gemini · Streamlit · Python

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square)](https://python.org)
[![GCP](https://img.shields.io/badge/GCP-BigQuery%20%7C%20Vertex%20AI-4285F4?style=flat-square)](https://cloud.google.com)
[![dbt](https://img.shields.io/badge/dbt-BigQuery-FF694B?style=flat-square)](https://getdbt.com)
[![Airflow](https://img.shields.io/badge/Airflow-2.x-017CEE?style=flat-square)](https://airflow.apache.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?style=flat-square)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

---

## Why I built this

I am a GCP Data Engineer with experience in BigQuery, Airflow, Python, and SQL.

In 2024 I relocated from India to Sydney, Australia and applied for Australian Permanent Residency. I also became a first-time mum. Between the visa process, settling into a new country, and parental leave — I had a two-year career gap.

When I received my PR and started job hunting, I did everything right:

- Tailored my resume to every job description
- Applied through LinkedIn and Seek consistently
- Optimised for ATS keywords
- Paid for LinkedIn Premium

And heard almost nothing back.

The more I looked into it, the more I realised the problem was not my skills. The problem was **the black hole that every job application disappears into after you click submit.**

LinkedIn and Seek are great at helping you find jobs. But once you apply, you are on your own — competing with hundreds of other candidates, with no tool to help you reach an actual human, explain your gap confidently, or track whether your outreach across email and LinkedIn is working.

So I built the tool I wished existed.

---

## What it does

ReachOut AI is a personal job search command centre that helps you break out of the application black hole through direct, personalised human outreach.

### ATS score engine
Paste any job description and your resume. Gemini analyses the match, gives you a percentage score, lists the exact missing keywords, and suggests specific edits to your resume for that role. Unlike LinkedIn's ATS badge, this works for jobs on **any** platform — Seek, company websites, JORA, anywhere.

### Personalised outreach message generator
Generates a tailored outreach message to a recruiter or hiring manager — not a template, a real message that references specific details from the job description. Works for both email and LinkedIn notes. A warm, direct message to the right person beats fifty cold applications every time.

### Career gap narrative generator
The feature no other tool has. You input your gap reason — relocation, parental leave, visa process, anything — and Gemini writes a confident, honest, forward-looking explanation tailored to the specific role you are applying for. No more apologetic one-liners. No more leaving it blank and hoping no one notices.

### Multi-channel outreach tracker
Tracks every conversation across email AND LinkedIn under one roof. LinkedIn only tracks InMails sent inside LinkedIn — the moment you move to email, that conversation disappears from LinkedIn's view entirely. ReachOut AI follows the thread wherever it goes, stores it in BigQuery, and shows you the full pipeline in one dashboard.

### Automated follow-up reminders
An Airflow DAG runs every morning, checks BigQuery for outreach with no reply after five days, and drafts a follow-up message using Gemini. You never lose track of a conversation again.

---

## Architecture

```
Job postings (Seek / LinkedIn / company sites)
        │
        ▼
  Python ingestion script
  (parse_jd.py)
        │
        ▼
  BigQuery — raw_jobs table
        │
        ▼
  dbt models
  (stg_jobs → jobs_enriched)
        │
        ├──────────────────────────────────┐
        ▼                                  ▼
  Vertex AI embeddings              Gemini 1.5 Flash
  (ATS scoring)                     (messages, narratives,
        │                            follow-ups)
        ▼                                  │
  BigQuery — ats_scores             BigQuery — outreach_log
                    │               gap_narratives
                    └───────┬───────┘
                            ▼
                    Streamlit dashboard
                    (full pipeline view)
                            │
                            ▼
                    Cloud Run (deployed)
                            │
                    Airflow DAG (daily follow-up check)
```

---

## Tech stack

| Component | Tool | Why |
|---|---|---|
| Cloud platform | GCP | Native to my existing skill set |
| Data warehouse | BigQuery | Core data engineering skill |
| Transformations | dbt | Modern DE standard, pairs perfectly with BigQuery |
| Orchestration | Apache Airflow | Production-grade scheduling |
| AI / LLM | Gemini 1.5 Flash via Vertex AI | On GCP, excellent for structured output |
| App UI | Streamlit | Fast to build, Python-native |
| Deployment | Cloud Run | GCP free tier, containerised |
| Language | Python 3.11 | Core skill |

---

## Features vs existing tools

| Feature | LinkedIn Premium | Seek | ReachOut AI |
|---|---|---|---|
| Cost | $40–$170/month | Free | Free + open source |
| Works outside their platform | ❌ | ❌ | ✅ Any job site |
| ATS score per role | ❌ | ❌ | ✅ |
| Career gap narrative | ❌ | ❌ | ✅ Built for returners |
| Personalised outreach drafting | Partial (InMail only) | ❌ | ✅ Email + LinkedIn |
| Cross-channel outreach tracking | ❌ | ❌ | ✅ |
| Automated follow-up reminders | ❌ | ❌ | ✅ Via Airflow |
| Direct recruiter outreach | 5 InMails/month | ❌ | ✅ Unlimited |

---

## Project structure

```
reachout-ai/
├── ingestion/
│   └── parse_jd.py          # Job description parser (URL or raw text)
├── dbt_reachout/
│   ├── models/
│   │   ├── staging/          # stg_jobs — clean and tag raw data
│   │   └── marts/            # jobs_enriched — analysis-ready
│   └── tests/                # dbt data quality tests
├── ai/
│   ├── ats_scorer.py         # ATS score engine (Gemini)
│   ├── message_generator.py  # Outreach message drafter (Gemini)
│   └── gap_narrator.py       # Career gap narrative generator (Gemini)
├── airflow/
│   └── dags/
│       └── followup_dag.py   # Daily follow-up reminder DAG
├── app/
│   └── streamlit_app.py      # Dashboard UI
├── deploy/
│   └── Dockerfile            # Cloud Run deployment
├── run_once/
│   └── create_tables.py      # BigQuery table setup
├── .env.example              # Environment variable template
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.11+
- A GCP account (free tier is sufficient)
- Git

### 1 — Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/reachout-ai.git
cd reachout-ai
```

### 2 — Create a virtual environment

```bash
# Mac / Linux
python -m venv venv
source venv/bin/activate

# Windows PowerShell
python -m venv venv
venv\Scripts\Activate.ps1
```

### 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### 4 — Set up your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in your real values:

```
GCP_PROJECT_ID=your-actual-project-id
GCP_REGION=australia-southeast1
BQ_DATASET=reachout
GOOGLE_APPLICATION_CREDENTIALS=./credentials/service_account.json
```

### 5 — Set up GCP

1. Create a GCP project
2. Enable BigQuery API and Vertex AI API
3. Create a service account with BigQuery Admin and Vertex AI User roles
4. Download the JSON key to `credentials/service_account.json`

### 6 — Create BigQuery tables

```bash
python run_once/create_tables.py
```

### 7 — Update your profile

Open `ai/message_generator.py` and update `MY_PROFILE` with your real background.
Open `ai/gap_narrator.py` and update `MY_GAP` with your real gap details.

### 8 — Run the app

```bash
streamlit run app/streamlit_app.py
```

Open `http://localhost:8501` in your browser.

---

## Usage — quick start

**Step 1 — Add a job:**
```bash
python ingestion/parse_jd.py
# Paste a URL or job description text when prompted
```

**Step 2 — Score your resume:**
```bash
python ai/ats_scorer.py
# Enter the job ID, get your ATS score and missing keywords
```

**Step 3 — Generate outreach:**
```bash
python ai/message_generator.py
# Enter job ID, contact name, channel — get a personalised message
```

**Step 4 — Generate gap narrative:**
```bash
python ai/gap_narrator.py
# Enter job ID, get a tailored gap explanation for that role
```

**Step 5 — View your pipeline:**
```bash
streamlit run app/streamlit_app.py
# See all roles, scores, outreach status, and follow-up flags in one view
```

---

## Live demo

🔗 [Live app on Cloud Run](YOUR_CLOUD_RUN_URL)

*(Screenshot or demo GIF here)*

---

## Roadmap

- [ ] Gmail API integration for automatic reply detection
- [ ] Chrome extension to parse JDs directly from Seek and LinkedIn
- [ ] Resume version manager — track which resume version was sent to which role
- [ ] Interview prep generator — Gemini generates likely questions based on the JD
- [ ] Analytics dashboard — which outreach channels get the best reply rates

---

## The honest disclaimer

This tool does not scrape LinkedIn or any other platform. Job descriptions are entered manually or via URL. The warm outreach features work with contacts you already know or find through normal channels. Everything is stored locally in your own GCP project — your job search data never leaves your account.

---

## About the author

I am a GCP Data Engineer based in Sydney, Australia. I built ReachOut AI because I lived the problem it solves — two years out of the workforce, back in the market, and frustrated by the silence that follows every job application.

This project taught me dbt, Vertex AI, Gemini, and Streamlit on top of my existing BigQuery, Airflow, and Python background. It is the most personally meaningful thing I have ever built.

If you are a returning tech professional facing the same wall — this tool is for you.

---

## Contributing

Pull requests are welcome. If you have faced the job search black hole yourself and have ideas for features, open an issue and let us talk about it.

---

## License

MIT — free to use, modify, and share.

---

*Built with GCP · BigQuery · dbt · Airflow · Vertex AI · Gemini · Streamlit · Python*

*Sydney, Australia · 2025*
