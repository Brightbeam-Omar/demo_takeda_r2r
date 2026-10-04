-- The latest LIMS sample of each lot: the one with the highest sample id (04-data-contracts section 1.2).
CREATE OR REPLACE TABLE t_lims AS
SELECT inspection_lot_no,
       sample_id,
       collected_date AS sample_collected_date,
       offsite_test,
       external_lab,
       shipped_date AS sample_shipped_date,
       CASE WHEN status IN ('registered', 'in_progress') THEN 'in_progress' ELSE status END AS lims_status,
       CASE WHEN status = 'approved' THEN site_date(approved_at) END AS lims_approved_date,
       CASE WHEN status = 'approved' THEN approved_at END AS lims_approved_at
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY inspection_lot_no ORDER BY sample_id DESC) AS rk
  FROM stg_sample
) ranked
WHERE rk = 1;
