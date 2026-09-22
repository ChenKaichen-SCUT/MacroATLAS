#!/usr/bin/env bash
set -euo pipefail

# Installed as /usr/local/bin/macroatlas on the dedicated experiment server.
macroatlas_python=/srv/macroatlas/venv/bin/python
macroatlas_script=/srv/macroatlas/repo/ATLAS/scripts/phase4/campaign.py
macroatlas_campaign=/srv/macroatlas/experiments/phase4
macroatlas_unit=macroatlas-phase4

case "${1:-status}" in
  run|start|resume)
    systemctl start "$macroatlas_unit"
    printf 'Started/resumed. Progress: macroatlas status; logs: macroatlas tail\n'
    ;;
  stop)
    systemctl stop "$macroatlas_unit"
    "$macroatlas_python" "$macroatlas_script" status "$macroatlas_campaign"
    ;;
  status)
    "$macroatlas_python" "$macroatlas_script" status "$macroatlas_campaign"
    df -h "$macroatlas_campaign"
    ;;
  tail)
    exec tail -n 30 -F "$macroatlas_campaign/logs/controller.log" "$macroatlas_campaign"/logs/*-w*.log
    ;;
  summary)
    exec "$macroatlas_python" "$macroatlas_script" summarize "$macroatlas_campaign"
    ;;
  backup)
    macroatlas_archive="/srv/macroatlas/archives/phase4-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
    exec "$macroatlas_python" "$macroatlas_script" archive "$macroatlas_campaign" --output "$macroatlas_archive"
    ;;
  *)
    printf 'Usage: macroatlas {run|status|tail|summary|stop|backup}\n' >&2
    exit 2
    ;;
esac
