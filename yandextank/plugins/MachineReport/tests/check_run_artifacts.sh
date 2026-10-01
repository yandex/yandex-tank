#!/bin/sh
# Checks downloaded files of one run in an Arcadia checkout:
#   test_run_artifacts.py - JSON schemas, the Python copy of report.Validate, sha256/bytes/lines of the hist file,
#                           window quantiles from the hist file and, with PHOUT, a replay of the run through the plugin;
#   load/projects/ai_analysis/report TestRunFiles - Go report.Validate on the same files.
# usage: check_run_artifacts.sh REPORT_JSON HIST_JSONL_GZ [PHOUT]
set -e
[ $# -ge 2 ] || { echo "usage: $0 REPORT_JSON HIST_JSONL_GZ [PHOUT]" >&2; exit 2; }
REPORT=$(readlink -f "$1")
HIST=$(readlink -f "$2")
PHOUT=${3:+$(readlink -f "$3")}
TESTS=$(dirname "$(readlink -f "$0")")
ARCADIA=$(cd "$TESTS/../../../../../../.." && pwd)
# a long run replays for minutes, longer than a SMALL test may take
set -- --retest --test-disable-timeout --test-env "MACHINE_REPORT=$REPORT" --test-env "MACHINE_REPORT_HIST=$HIST"
[ -z "$PHOUT" ] || set -- "$@" --test-env "MACHINE_REPORT_PHOUT=$PHOUT"
ya make -t "$@" -F 'test_run_artifacts.py::*' "$TESTS"
ya make -t "$@" -F '*TestRunFiles*' "$ARCADIA/load/projects/ai_analysis/report"
