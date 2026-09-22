#!/usr/bin/env bash
set -euo pipefail
export MACROATLAS_SCRIPT=/srv/macroatlas/repo-encoding-fix/ATLAS/scripts/phase4/campaign.py
export MACROATLAS_CAMPAIGN=/srv/macroatlas/experiments/phase4-quarter-once
export MACROATLAS_UNIT=macroatlas-phase4-quarter-once
export MACROATLAS_LABEL=macroatlas-quarter
exec bash /srv/macroatlas/repo-encoding-fix/ATLAS/scripts/phase4/server_ctl.sh "$@"
