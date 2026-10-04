-- System need-by per material: the earliest open demand line on or after the snapshot date (ties: lowest id).
CREATE OR REPLACE TABLE t_need AS
SELECT matnr, campaign, bdter AS system_need_by_date
FROM (
  SELECT matnr, campaign, bdter,
         ROW_NUMBER() OVER (PARTITION BY matnr ORDER BY bdter, id) AS rk
  FROM stg_mdez
  WHERE is_open AND bdter >= {{ snapshot_date | sql }}
) ranked
WHERE rk = 1;
