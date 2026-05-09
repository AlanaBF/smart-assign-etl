-- sql/03_cv_search_profile_qtest_mv.sql

-- Materialized view for QTEST dataset only. The fake QTEST reports use
-- small numeric `CV Partner User ID` values (e.g. "1"). The main
-- `cv_search_profile_mv` covers the production-like dataset; this view
-- filters to rows that look like the QTEST loader output using a simple
-- regular expression on `cv_partner_user_id`.

CREATE MATERIALIZED VIEW IF NOT EXISTS cv_search_profile_qtest_mv AS
WITH latest_availability AS (
    SELECT user_id, date, percent_available
    FROM (
        SELECT
            ua.*,
            ROW_NUMBER() OVER (
                PARTITION BY ua.user_id
                ORDER BY ua.date DESC
            ) AS rn
        FROM user_availability ua
    ) t
    WHERE rn = 1
)
SELECT
    u.user_id,
    u.cv_partner_user_id,
    (u.name_multilang->>'int')       AS user_name,
    c.cv_id,
    (c.title_multilang->>'int')      AS cv_title,
    c.sfia_level,
    c.cpd_label,
    u.country                AS country,
    STRING_AGG(DISTINCT dt.name, ', ' ORDER BY dt.name) AS technologies,
    MAX(ct.years_experience) AS max_years_experience,
    MAX(dc.name)             AS clearance,

    la.date               AS latest_availability_date,
    la.percent_available  AS latest_percent_available

FROM users u
JOIN cvs c
    ON c.user_id = u.user_id

LEFT JOIN cv_technology ct
    ON ct.cv_id = c.cv_id
LEFT JOIN dim_technology dt
    ON dt.technology_id = ct.technology_id

LEFT JOIN user_clearance uc
    ON uc.user_id = u.user_id
LEFT JOIN dim_clearance dc
    ON dc.clearance_id = uc.clearance_id

LEFT JOIN latest_availability la
    ON la.user_id = u.user_id

GROUP BY
    u.user_id,
    u.cv_partner_user_id,
    user_name,
    c.cv_id,
    cv_title,
    c.sfia_level,
    c.cpd_label,
    u.country,
    la.date,
    la.percent_available
