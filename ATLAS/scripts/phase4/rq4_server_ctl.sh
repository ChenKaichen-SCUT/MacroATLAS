#!/usr/bin/env bash
set -euo pipefail

rq4_atlas=/srv/macroatlas/rq4-code/ATLAS
rq4_python=/srv/macroatlas/venv/bin/python
rq4_campaign=/srv/macroatlas/experiments/rq4-scale-once
rq4_java_home=/srv/macroatlas/jdks/jdk8u462-b08
rq4_unit=macroatlas-rq4
export JAVA_HOME="$rq4_java_home"
export PATH="$rq4_java_home/bin:$PATH"

case "${1:-status}" in
  run)
    if [[ -f "$rq4_campaign/state.json" ]] &&
       "$rq4_python" -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["status"]!="COMPLETE")' "$rq4_campaign/state.json"; then
      echo 'RQ4 is already complete; no solver job will be started.'
      exit 0
    fi
    systemctl start "$rq4_unit"
    echo 'Started RQ4. Use: macroatlas-rq4 status | watch | tail | summary'
    ;;
  service-run)
    "$rq4_python" "$rq4_atlas/scripts/phase4/campaign.py" run "$rq4_campaign"
    "$rq4_python" "$rq4_atlas/scripts/phase4/rq4.py" report --campaign "$rq4_campaign"
    ;;
  status)
    "$rq4_python" "$rq4_atlas/scripts/phase4/rq4.py" status --campaign "$rq4_campaign"
    ;;
  watch)
    exec watch -n 5 macroatlas-rq4 status
    ;;
  tail)
    exec tail -n 30 -F "$rq4_campaign/logs/controller.log" "$rq4_campaign"/logs/e8-synthetic-w*.log
    ;;
  summary)
    "$rq4_python" "$rq4_atlas/scripts/phase4/rq4.py" status --campaign "$rq4_campaign"
    if [[ -f "$rq4_campaign/rq4_summary.json" ]]; then
      "$rq4_python" -m json.tool "$rq4_campaign/rq4_summary.json"
    else
      echo 'Paper tables are written automatically after all 60 attempts are complete.'
    fi
    ;;
  finalize)
    "$rq4_python" "$rq4_atlas/scripts/phase4/rq4.py" report --campaign "$rq4_campaign"
    ;;
  *)
    echo 'Usage: macroatlas-rq4 {run|status|watch|tail|summary|finalize}' >&2
    exit 2
    ;;
esac
