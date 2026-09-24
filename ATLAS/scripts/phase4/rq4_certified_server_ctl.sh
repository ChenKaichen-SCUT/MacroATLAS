#!/usr/bin/env bash
set -euo pipefail

atlas=/srv/macroatlas/rq4-certified-code/ATLAS
python=/srv/macroatlas/venv/bin/python
ab=/srv/macroatlas/experiments/rq4-certified-ab-once
profile=/srv/macroatlas/experiments/rq4-certified-profile-once
paper=/srv/macroatlas/experiments/rq4-certified-paper
unit=macroatlas-rq4-certified-sequence
ab_unit=macroatlas-rq4c-ab
profile_unit=macroatlas-rq4c-profile

complete() {
  [[ -f "$1/state.json" ]] && "$python" -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["status"]!="COMPLETE")' "$1/state.json"
}

finish_tables() {
  "$python" "$atlas/scripts/phase4/rq4.py" report --campaign "$ab"
  "$python" "$atlas/scripts/phase4/rq4_certified.py" audit-ab --campaign "$ab"
  "$python" "$atlas/scripts/phase4/rq4_certified.py" report-profile --campaign "$profile"
  "$python" "$atlas/scripts/phase4/rq4_certified.py" summarize \
    --ab-campaign "$ab" --profile-campaign "$profile" --output "$paper"
}

run_one() {
  local campaign=$1
  local controller=$2
  if complete "$campaign"; then return; fi
  systemctl start "$controller"
  while systemctl is-active --quiet "$controller"; do sleep 5; done
  if ! complete "$campaign"; then
    echo "$controller stopped without COMPLETE; inspect $campaign/logs/controller.log" >&2
    exit 1
  fi
}

case "${1:-status}" in
  run)
    if complete "$ab" && complete "$profile"; then
      echo 'Both RQ4 certified campaigns already complete; no solver will restart.'
      exit 0
    fi
    systemctl start --no-block "$unit"
    echo 'Started the A+B then C sequence. Use: macroatlas-rq4-certified status | watch | tail | summary'
    ;;
  service-run)
    run_one "$ab" "$ab_unit"
    "$python" "$atlas/scripts/phase4/rq4.py" report --campaign "$ab"
    "$python" "$atlas/scripts/phase4/rq4_certified.py" audit-ab --campaign "$ab"
    run_one "$profile" "$profile_unit"
    finish_tables
    ;;
  status)
    "$python" "$atlas/scripts/phase4/rq4_certified.py" status \
      --ab-campaign "$ab" --profile-campaign "$profile"
    ;;
  watch)
    exec watch -n 5 macroatlas-rq4-certified status
    ;;
  tail)
    exec tail -n 25 -F /srv/macroatlas/experiments/rq4-certified-sequence.log \
      "$ab/logs/controller.log" "$profile/logs/controller.log" \
      "$ab"/logs/e8-synthetic-w*.log "$profile"/logs/e8-synthetic-w*.log
    ;;
  summary)
    "$python" "$atlas/scripts/phase4/rq4_certified.py" status \
      --ab-campaign "$ab" --profile-campaign "$profile"
    if [[ -f "$paper/rq4c_summary.json" ]]; then
      "$python" -m json.tool "$paper/rq4c_summary.json"
    else
      echo 'Final paper table is written automatically after both campaigns complete.'
    fi
    ;;
  finalize)
    if ! complete "$ab" || ! complete "$profile"; then
      echo 'Both campaigns must complete before finalization.' >&2
      exit 1
    fi
    finish_tables
    ;;
  *)
    echo 'Usage: macroatlas-rq4-certified {run|status|watch|tail|summary|finalize}' >&2
    exit 2
    ;;
esac
