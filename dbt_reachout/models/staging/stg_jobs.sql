WITH raw AS (
    SELECT
        job_id,
        TRIM(title)                                     AS title,
        TRIM(company)                                   AS company,
        TRIM(location)                                  AS location,
        salary_raw,
        description_raw,
        url,
        source,
        ingested_at,

        -- Extract salary lower bound
        SAFE_CAST(
            REGEXP_EXTRACT(salary_raw, r'\$?([\d,]+)')
            AS INT64
        )                                               AS salary_min,

        -- Senior role tag
        CASE
            WHEN LOWER(title) LIKE '%senior%'
              OR LOWER(title) LIKE '%lead%'
              OR LOWER(title) LIKE '%principal%' THEN TRUE
            ELSE FALSE
        END                                             AS is_senior,

        -- GCP mentions
        CASE
            WHEN LOWER(description_raw) LIKE '%bigquery%'
              OR LOWER(description_raw) LIKE '%vertex ai%'
              OR LOWER(description_raw) LIKE '%gcp%'
              OR LOWER(description_raw) LIKE '%google cloud%' THEN TRUE
            ELSE FALSE
        END                                             AS mentions_gcp,

        -- Airflow mentions
        CASE
            WHEN LOWER(description_raw) LIKE '%airflow%'
              OR LOWER(description_raw) LIKE '%cloud composer%' THEN TRUE
            ELSE FALSE
        END                                             AS mentions_airflow,

        -- dbt mentions
        CASE
            WHEN LOWER(description_raw) LIKE '% dbt %'
              OR LOWER(description_raw) LIKE '%dbt core%' THEN TRUE
            ELSE FALSE
        END                                             AS mentions_dbt,

        -- Python mentions
        CASE
            WHEN LOWER(description_raw) LIKE '%python%' THEN TRUE
            ELSE FALSE
        END                                             AS mentions_python,

        -- AI/ML mentions
        CASE
            WHEN LOWER(description_raw) LIKE '%machine learning%'
              OR LOWER(description_raw) LIKE '%llm%'
              OR LOWER(description_raw) LIKE '%generative ai%'
              OR LOWER(description_raw) LIKE '%vertex ai%' THEN TRUE
            ELSE FALSE
        END                                             AS mentions_ai,

        -- Location normalisation
        CASE
            WHEN LOWER(location) LIKE '%sydney%' THEN 'Sydney'
            WHEN LOWER(location) LIKE '%melbourne%' THEN 'Melbourne'
            WHEN LOWER(location) LIKE '%brisbane%' THEN 'Brisbane'
            WHEN LOWER(location) LIKE '%remote%' THEN 'Remote'
            WHEN LOWER(location) LIKE '%hybrid%' THEN 'Hybrid'
            ELSE location
        END                                             AS location_clean

    FROM {{ source('reachout', 'raw_jobs') }}
    WHERE description_raw IS NOT NULL
      AND LENGTH(description_raw) > 100
)

SELECT * FROM raw