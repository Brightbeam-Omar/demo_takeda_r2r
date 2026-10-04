-- Linked deviations per batch.
CREATE OR REPLACE TABLE t_deviation AS
SELECT l.material_no, l.batch_no,
       CAST(SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) AS BIGINT) AS open_deviation_count,
       CAST(SUM(CASE WHEN d.status = 'closed' THEN 1 ELSE 0 END) AS BIGINT) AS closed_deviation_count
FROM stg_deviation_link l
JOIN stg_deviation d ON d.deviation_no = l.deviation_no
GROUP BY l.material_no, l.batch_no;
