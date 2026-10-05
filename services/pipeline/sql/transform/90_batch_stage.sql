-- Stage engine output joined with the flags: staging.batch_stage before the Python-built JSON columns.
CREATE OR REPLACE TABLE batch_stage_sql AS
SELECT s.row_key, s.stage_key, s.stage_rule_id, s.cycle_start_date, s.ud_effective, s.stage_sort, s.current_stage_entry_date, fl.lims_rejected,
{% for stage in dated_stages %}
       s.{{ stage.key }}_entry, s.{{ stage.key }}_exit,
{% endfor %}
       fl.on_hold, fl.erp_blocked, fl.re_eval, fl.offsite, fl.full_spec, fl.ud_rejected,
       fl.deviation_light, fl.inbound_light
FROM t_stage s
JOIN t_flags fl ON fl.row_key = s.row_key;
