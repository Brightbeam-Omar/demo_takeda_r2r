-- Goods receipts, netting and stock per batch (04-data-contracts section 3). Inputs: stg_mseg, stg_mchb, stg_t001l.

-- A 102 cancels at most one 101 of the same batch, posting date and quantity: the n-th 102 cancels the n-th 101.
CREATE OR REPLACE TABLE t_gr AS
SELECT matnr, charg, mblnr, lgort, budat, menge,
       ROW_NUMBER() OVER (PARTITION BY matnr, charg, budat, menge ORDER BY mblnr) AS rn
FROM stg_mseg
WHERE bwart = '101';

CREATE OR REPLACE TABLE t_gr_reversal AS
SELECT matnr, charg, mblnr, budat, menge,
       ROW_NUMBER() OVER (PARTITION BY matnr, charg, budat, menge ORDER BY mblnr) AS rn
FROM stg_mseg
WHERE bwart = '102';

CREATE OR REPLACE TABLE t_gr_net AS
SELECT g.matnr, g.charg, g.mblnr, g.lgort, g.budat, g.menge
FROM t_gr g
LEFT JOIN t_gr_reversal r
  ON g.matnr = r.matnr AND g.charg = r.charg AND g.budat = r.budat AND g.menge = r.menge AND g.rn = r.rn
WHERE r.mblnr IS NULL;

-- First surviving receipt per batch: its date and the type of its storage location.
CREATE OR REPLACE TABLE t_batch_receipt AS
SELECT f.matnr, f.charg, f.budat AS gr_date, l.zloctype AS received_location_type
FROM (
  SELECT matnr, charg, lgort, budat,
         ROW_NUMBER() OVER (PARTITION BY matnr, charg ORDER BY budat, mblnr) AS rk
  FROM t_gr_net
) f
JOIN stg_t001l l ON l.lgort = f.lgort
WHERE f.rk = 1;

-- First transfer to an onsite location on or after the receipt.
CREATE OR REPLACE TABLE t_batch_transfer AS
SELECT m.matnr, m.charg, MIN(m.budat) AS transfer_to_site_date
FROM stg_mseg m
JOIN stg_t001l dest ON dest.lgort = m.umlgo
JOIN t_batch_receipt r ON r.matnr = m.matnr AND r.charg = m.charg
WHERE m.bwart = '311' AND dest.zloctype = 'onsite' AND m.budat >= r.gr_date
GROUP BY m.matnr, m.charg;

-- Where the stock is: the location with most quantity (ties: lowest number), else the last movement's destination.
CREATE OR REPLACE TABLE t_stock_ranked AS
SELECT matnr, charg, lgort,
       ROW_NUMBER() OVER (PARTITION BY matnr, charg ORDER BY insme + speme + clabs DESC, lgort) AS rk
FROM stg_mchb;

CREATE OR REPLACE TABLE t_stock_sum AS
SELECT matnr, charg, SUM(insme) AS insme, SUM(speme) AS speme, SUM(clabs) AS clabs
FROM stg_mchb
GROUP BY matnr, charg;

CREATE OR REPLACE TABLE t_last_move AS
SELECT matnr, charg, COALESCE(umlgo, lgort) AS lgort,
       ROW_NUMBER() OVER (PARTITION BY matnr, charg ORDER BY budat DESC, mblnr DESC) AS rk
FROM stg_mseg;

CREATE OR REPLACE TABLE t_batch_stock AS
SELECT b.matnr, b.charg,
       COALESCE(s.lgort, lm.lgort) AS storage_location,
       CASE WHEN ss.speme > 0 THEN 'BLOCKED' WHEN ss.insme > 0 THEN 'QI' ELSE 'UNRESTRICTED' END AS stock_category
FROM stg_mcha b
LEFT JOIN t_stock_ranked s ON s.matnr = b.matnr AND s.charg = b.charg AND s.rk = 1
LEFT JOIN t_last_move lm ON lm.matnr = b.matnr AND lm.charg = b.charg AND lm.rk = 1
LEFT JOIN t_stock_sum ss ON ss.matnr = b.matnr AND ss.charg = b.charg;
