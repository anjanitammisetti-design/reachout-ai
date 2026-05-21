SELECT
    job_id,
    title,
    company,
    location_clean                  AS location,
    salary_min,
    is_senior,
    mentions_gcp,
    mentions_airflow,
    mentions_dbt,
    mentions_python,
    mentions_ai,
    url,
    source,
    ingested_at,

    -- Quick skill match score based on YOUR skills
    (
        CAST(mentions_gcp     AS INT64) +
        CAST(mentions_airflow AS INT64) +
        CAST(mentions_dbt     AS INT64) +
        CAST(mentions_python  AS INT64) +
        CAST(mentions_ai      AS INT64)
    )                               AS skill_match_count,

    -- Days since job was added
    DATE_DIFF(
        CURRENT_DATE(),
        DATE(ingested_at),
        DAY
    )                               AS days_since_added,

    -- Freshness tag
    CASE
        WHEN DATE_DIFF(CURRENT_DATE(), DATE(ingested_at), DAY) <= 3
            THEN 'Fresh'
        WHEN DATE_DIFF(CURRENT_DATE(), DATE(ingested_at), DAY) <= 7
            THEN 'Recent'
        ELSE 'Older'
    END                             AS freshness

FROM {{ ref('stg_jobs') }}