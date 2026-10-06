-- staging.batch_flat: one row per material + batch + inspection lot (04-data-contracts section 3).
-- Released lots (an accept usage decision) get no need-by: the demand is no longer theirs.
CREATE OR REPLACE TABLE batch_flat AS
SELECT concat_key(l.material_no, l.batch_no, l.inspection_lot_no) AS row_key,
       l.material_no, l.material_desc, l.material_class, l.molecule_type,
       l.supplier_id, l.supplier_name, l.supplier_batch, l.batch_no, l.batch_status_code,
       l.inspection_lot_no, l.lot_type, l.lot_start_date,
       l.storage_location, l.location_type, l.received_location_type, l.stock_category,
       l.gr_date, l.transfer_to_site_date,
       l.inbound_check_status, l.inbound_check_completed_date,
       s.sample_id, s.sample_collected_date,
       COALESCE(s.offsite_test, FALSE) AS offsite_test,
       s.external_lab, s.sample_shipped_date,
       COALESCE(s.lims_status, 'none') AS lims_status,
       s.lims_approved_date, s.lims_approved_at,
       l.ud_code, l.ud_date, l.erp_results_recorded_at,
       CASE WHEN l.ud_code IN {{ accept_codes | sql }} THEN NULL ELSE n.campaign END AS campaign,
       CASE WHEN l.ud_code IN {{ accept_codes | sql }} THEN NULL ELSE n.system_need_by_date END AS system_need_by_date,
       COALESCE(d.open_deviation_count, 0) AS open_deviation_count,
       COALESCE(d.closed_deviation_count, 0) AS closed_deviation_count,
       l.next_inspection_date,
       r.need_by_at_release,
       l.expedite_requested_on,
       l.expedite_due_date
FROM t_lot l
LEFT JOIN t_lims s ON s.inspection_lot_no = l.inspection_lot_no
LEFT JOIN t_deviation d ON d.material_no = l.material_no AND d.batch_no = l.batch_no
LEFT JOIN t_need n ON n.matnr = l.material_no
LEFT JOIN t_need_release r ON r.inspection_lot_no = l.inspection_lot_no;
