#!/bin/bash
# Nightly pipeline: runs every step in order, with no manual work (FR7), and times each step (NFR2).
#   1. ingest.sh   source files  -> RAW zone       (one day)
#   2. clean.sh    RAW zone      -> CLEANED zone   (one day)
#   3. curate.sh   CLEANED zone  -> CURATED zone   (rebuilds the three joined datasets)
#
# Can be run from any folder, as long as the cluster is running:
#   bash run_pipeline.sh 20261031     process one day, as the nightly run would
#   bash run_pipeline.sh all          process every day in ./data (first full load)
#
# Each run adds a line to pipeline_timings.csv in this folder (timing evidence for the report).

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

cd "$(dirname "$0")" || exit 1     # the folder this script is in, next to the other steps

DAY="$1"
if [ -z "$DAY" ] || { [ "$DAY" != "all" ] && ! [[ "$DAY" =~ ^[0-9]{8}$ ]]; }; then
  echo "Usage: bash run_pipeline.sh YYYYMMDD   or   bash run_pipeline.sh all"
  exit 1
fi

step() {
  local name="$1"; shift
  echo ""
  echo "===== $name ====="
  local t0=$(date +%s)
  "$@" || { echo ""; echo "PIPELINE STOPPED: $name failed"; exit 1; }
  local secs=$(( $(date +%s) - t0 ))
  echo "----- $name took ${secs}s"
  TIMES="$TIMES,$secs"
}

START=$(date +%s)
STARTED_AT=$(date "+%Y-%m-%d %H:%M:%S")
TIMES=""
echo "Nightly pipeline started $STARTED_AT for: $DAY"

if [ "$DAY" = "all" ]; then
  step "1. Ingest (raw)"      bash ingest.sh
  step "2. Clean (cleaned)"   bash clean.sh
else
  step "1. Ingest (raw)"      bash ingest.sh "$DAY"
  step "2. Clean (cleaned)"   bash clean.sh "$DAY"
fi
step "3. Curate (curated)"    bash curate.sh

TOTAL=$(( $(date +%s) - START ))
[ -f pipeline_timings.csv ] || echo "started_at,day,ingest_s,clean_s,curate_s,total_s" > pipeline_timings.csv
echo "$STARTED_AT,$DAY$TIMES,$TOTAL" >> pipeline_timings.csv

echo ""
echo "===== Pipeline finished in ${TOTAL}s (limit: 7200s = 2 hours) ====="
echo "Timing saved to pipeline_timings.csv"
