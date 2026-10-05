-- Open purchase-order lines (F17-FR-03): a pre-batch grain, one row per open line.
-- The campaign is the one of the material's earliest open demand, as for the batch rows.
CREATE OR REPLACE TABLE expected_deliveries_sql AS
SELECT e.ebeln,
       e.ebelp,
       e.matnr AS material_no,
       m.maktx AS material_desc,
       m.zmolty AS molecule_type,
       m.zclass AS material_class,
       e.lifnr AS supplier_id,
       s.name1 AS supplier_name,
       n.campaign AS campaign,
       e.eindt AS scheduled_date,
       e.menge AS quantity,
       e.lgort AS planned_location,
       l.zloctype AS planned_location_type,
       CASE WHEN e.eindt < {{ snapshot_date | sql }} THEN TRUE ELSE FALSE END AS overdue
FROM stg_ekpo e
JOIN stg_mara m ON m.matnr = e.matnr
JOIN stg_lfa1 s ON s.lifnr = e.lifnr
JOIN stg_t001l l ON l.lgort = e.lgort
LEFT JOIN t_need n ON n.matnr = e.matnr
WHERE e.is_open;
