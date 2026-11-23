#!/bin/bash
# Creates the data lake zones in HDFS: raw, cleaned, curated
# Run from the folder with docker-compose.yaml, after the cluster is up:
#   bash create_zones.sh
# Safe to run more than once (mkdir -p does not touch folders that already exist).

# Stop Git Bash / MSYS2 on Windows from turning /datalake into C:/...
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SOURCES="pms pos procurement erp wifi reviews hr"

DIRS=""
for src in $SOURCES; do
  DIRS="$DIRS /datalake/raw/$src"               # files exactly as received (date subfolders added by ingestion)
  DIRS="$DIRS /datalake/cleaned/$src"           # rows after the quality fixes in Section 2.3
  DIRS="$DIRS /datalake/cleaned/_rejected/$src" # rows that could not be fixed, kept for checking
done
DIRS="$DIRS /datalake/cleaned/_logs"            # rows read / written / rejected per cleaning run (NFR6)

# Curated holds report-ready joined datasets, one per join key (Section 6.2)
DIRS="$DIRS /datalake/curated/guest_stay_summary"   # PMS + POS + Wi-Fi on room_number + date
DIRS="$DIRS /datalake/curated/review_stay_link"     # PMS + Reviews on reservation_id
DIRS="$DIRS /datalake/curated/department_daily"     # Procurement + ERP + HR on department + date

# One call creates every folder (faster than one docker exec per folder)
docker exec namenode hdfs dfs -mkdir -p $DIRS

echo "Zones created:"
docker exec namenode hdfs dfs -ls -R /datalake
