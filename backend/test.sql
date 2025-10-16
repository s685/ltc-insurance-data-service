,retro_months as (
  select
    eh.rfb_id,
    case
      -- Case 1: Latest EOB (EOB_RANKER = 1) has both EB_START_DT and EB_END_DT as NULL
      when eh.eob_ranker = 1 and eh.eob_start_dt is null and eh.eob_end_dt is null then
        case
          -- Find prior EOB (EOB_RANKER = 2) and check FIRSTEBDECISIONDT in reporting period
          when prior_eob.firstebdecisiondt between '{{REPORT_START_DT}}' and '{{REPORT_END_DT}}' then
            least(3, datediff(month, prior_eob.eob_start_dt, '{{REPORT_START_DT}}'))
          else 0
        end
      -- Case 2: Latest EOB (EOB_RANKER = 1) has EB_START_DT NOT NULL
      when eh.eob_ranker = 1 and eh.eob_start_dt is not null then
        case
          when eh.firstebdecisiondt between '{{REPORT_START_DT}}' and '{{REPORT_END_DT}}' then
            least(3, datediff(month, eh.eob_start_dt, '{{REPORT_START_DT}}'))
          else 0
        end
      else 0
    end as retro_months
  from eob_history eh
  left join eob_history prior_eob
    on eh.rfb_id = prior_eob.rfb_id and prior_eob.eob_ranker = 2
  where eh
