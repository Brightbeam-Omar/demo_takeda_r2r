-- Overlay flags and quality lights (03-domain-model sections 6 and 8). expedite and air_gap are app-side.
CREATE OR REPLACE TABLE t_flags AS
SELECT row_key,
       COALESCE(batch_status_code = 'H', FALSE) AS on_hold,
       stock_category = 'BLOCKED' AS erp_blocked,
       lot_type = '09' AS re_eval,
       offsite_test AS offsite,
{% if full_spec_pairs %}
       ({% for material, supplier in full_spec_pairs %}(material_no = {{ material | sql }} AND supplier_id = {{ supplier | sql }}){% if not loop.last %} OR {% endif %}{% endfor %}) AS full_spec,
{% else %}
       FALSE AS full_spec,
{% endif %}
       COALESCE(ud_code IN {{ reject_codes | sql }}, FALSE) AS ud_rejected,
       lims_status = 'rejected' AS lims_rejected,
       CASE WHEN open_deviation_count > 0 THEN 'red' WHEN closed_deviation_count > 0 THEN 'amber' ELSE 'green' END AS deviation_light,
       CASE WHEN inbound_check_status IN ('open', 'failed') THEN 'red' WHEN inbound_check_status = 'resolved' THEN 'amber' WHEN inbound_check_status = 'passed' THEN 'green' ELSE 'grey' END AS inbound_light
FROM batch_flat;
