#!/usr/bin/env bash
set -euo pipefail

followup_atlas=/srv/macroatlas/rq4-followup-code/ATLAS
followup_python=/srv/macroatlas/venv/bin/python
followup_campaign=/srv/macroatlas/experiments/rq4-followup-once
followup_java_home=/srv/macroatlas/jdks/jdk8u462-b08
followup_unit=macroatlas-rq4-followup
export JAVA_HOME="$followup_java_home"
export PATH="$followup_java_home/bin:$PATH"

case "${1:-status}" in
  run)
    if [[ -f "$followup_campaign/state.json" ]] &&
       "$followup_python" -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["status"]!="COMPLETE")' "$followup_campaign/state.json"; then
      echo 'RQ4 follow-up is already complete; no solver job will be started.'
      exit 0
    fi
    systemctl start "$followup_unit"
    echo 'Started RQ4 follow-up. Use: macroatlas-rq4-followup status | watch | tail | summary'
    ;;
  service-run)
    "$followup_python" "$followup_atlas/scripts/phase4/campaign.py" run "$followup_campaign"
    "$followup_python" "$followup_atlas/scripts/phase4/rq4.py" report --campaign "$followup_campaign"
    "$followup_python" "$followup_atlas/scripts/phase4/rq4_followup.py" audit --campaign "$followup_campaign"
    ;;
  status)
    "$followup_python" "$followup_atlas/scripts/phase4/rq4.py" status --campaign "$followup_campaign"
    ;;
  watch)
    exec watch -n 5 macroatlas-rq4-followup status
    ;;
  tail)
    exec tail -n 30 -F "$followup_campaign/logs/controller.log" "$followup_campaign"/logs/e8-synthetic-w*.log
    ;;
  summary)
    "$followup_python" "$followup_atlas/scripts/phase4/rq4.py" status --campaign "$followup_campaign"
    if [[ -f "$followup_campaign/rq4_summary.json" ]]; then
      "$followup_python" -m json.tool "$followup_campaign/rq4_summary.json"
      "$followup_python" -m json.tool "$followup_campaign/rq4f_design_audit.json"
    else
      echo 'Paper tables and design audit are written automatically after all planned attempts complete.'
    fi
    ;;
  finalize)
    "$followup_python" "$followup_atlas/scripts/phase4/rq4.py" report --campaign "$followup_campaign"
    "$followup_python" "$followup_atlas/scripts/phase4/rq4_followup.py" audit --campaign "$followup_campaign"
    ;;
  *)
    echo 'Usage: macroatlas-rq4-followup {run|status|watch|tail|summary|finalize}' >&2
    exit 2
    ;;
esac
