-- Linked deviations per batch.
CREATE OR REPLACE TABLE t_deviation AS
SELECT l.material_no, l.batch_no,
       SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) AS open_deviation_count,
       SUM(CASE WHEN d.status = 'closed' THEN 1 ELSE 0 END) AS closed_deviation_count
FROM stg_deviation_link l
JOIN stg_deviation d ON d.deviation_no = l.deviation_no
GROUP BY l.material_no, l.batch_no;
