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

-- Need-by at release (F20-FR-02): for a lot with an accept usage decision, the earliest demand line of its
-- material on or after the lot's cycle start, closed lines included (demand closes when the lot is released).
-- The cycle start is the lot start of a re-evaluation (09) and the goods receipt date otherwise (03 section 4).
CREATE OR REPLACE TABLE t_need_release AS
SELECT l.inspection_lot_no, MIN(d.bdter) AS need_by_at_release
FROM t_lot l
JOIN stg_mdez d ON d.matnr = l.material_no
 AND d.bdter >= CASE WHEN l.lot_type = '09' THEN l.lot_start_date ELSE l.gr_date END
WHERE l.ud_code IN {{ accept_codes | sql }}
GROUP BY l.inspection_lot_no;
