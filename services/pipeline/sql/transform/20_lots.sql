-- One row per inspection lot (types 01 and 09, cancelled usage decisions excluded) with its ERP facts.
CREATE OR REPLACE TABLE t_lot AS
SELECT q.matnr AS material_no,
       m.maktx AS material_desc,
       m.zclass AS material_class,
       m.zmolty AS molecule_type,
       b.lifnr AS supplier_id,
       s.name1 AS supplier_name,
       b.licha AS supplier_batch,
       q.charg AS batch_no,
       b.zstat AS batch_status_code,
       q.prueflos AS inspection_lot_no,
       q.art AS lot_type,
       q.pastrterm AS lot_start_date,
       bs.storage_location,
       loc.zloctype AS location_type,
       CASE WHEN q.art = '09' THEN 'onsite' ELSE r.received_location_type END AS received_location_type,
       bs.stock_category,
       r.gr_date,
       t.transfer_to_site_date,
       COALESCE(z.status, 'none') AS inbound_check_status,
       CASE WHEN z.status = 'passed' THEN z.completed_on END AS inbound_check_completed_date,
       q.vcode AS ud_code,
       q.vdatum AS ud_date,
       q.zresrec AS erp_results_recorded_at
FROM stg_qals q
JOIN stg_mcha b ON b.matnr = q.matnr AND b.charg = q.charg
JOIN stg_mara m ON m.matnr = q.matnr
LEFT JOIN stg_lfa1 s ON s.lifnr = b.lifnr
LEFT JOIN t_batch_receipt r ON r.matnr = q.matnr AND r.charg = q.charg
LEFT JOIN t_batch_transfer t ON t.matnr = q.matnr AND t.charg = q.charg
LEFT JOIN t_batch_stock bs ON bs.matnr = q.matnr AND bs.charg = q.charg
LEFT JOIN stg_t001l loc ON loc.lgort = bs.storage_location
LEFT JOIN stg_zinbchk z ON z.prueflos = q.prueflos
WHERE q.art IN ('01', '09')
  AND (q.vcode IS NULL OR q.vcode NOT IN {{ cancel_codes | sql }});
