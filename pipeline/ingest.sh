#!/bin/bash
# Ingestion: copies the daily export files from ./data into the RAW zone of the data lake.
# Files are NOT changed in any way (FR1, FR2). Each file goes into a folder for its date:
#   ./data/pms/pms_reservations_20261001.csv  ->  /datalake/raw/pms/2026-10-01/pms_reservations_20261001.csv
#
# The source files must be in the ./data folder next to docker-compose.yml, which the
# namenode container sees as /data. The script itself can be run from any folder:
#   bash ingest.sh            ingest every file in ./data (first load)
#   bash ingest.sh 20261015   ingest only one day's files (what the nightly run does)
#
# Safe to re-run: a file that is already in HDFS is overwritten with the same file.

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

DAY="${1:-all}"
if [ "$DAY" != "all" ] && ! [[ "$DAY" =~ ^[0-9]{8}$ ]]; then
  echo "Usage: bash ingest.sh [YYYYMMDD]"
  exit 1
fi

START=$(date +%s)

# The ./data folder is mounted at /data inside the namenode container (see docker-compose.yml).
# All the work runs inside the container in one go, because starting the hdfs command
# once per file would be very slow.
docker exec -i namenode bash -s "$DAY" <<'INNER'
DAY="$1"
STAGE=/tmp/raw_stage
rm -rf "$STAGE"
mkdir -p "$STAGE"

count=0
for srcdir in /data/*/; do
  src=$(basename "$srcdir")
  for f in "$srcdir"*.csv "$srcdir"*.json; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    d=$(echo "$name" | grep -oE '[0-9]{8}' | head -1)      # date from the file name
    [ -n "$d" ] || { echo "  skipped (no date in name): $name"; continue; }
    [ "$DAY" = "all" ] || [ "$DAY" = "$d" ] || continue
    folder="$STAGE/$src/${d:0:4}-${d:4:2}-${d:6:2}"
    mkdir -p "$folder"
    cp "$f" "$folder/"
    count=$((count + 1))
  done
done

if [ "$count" -eq 0 ]; then
  echo "No files found for: $DAY  (is the data folder next to docker-compose.yml?)"
  rm -rf "$STAGE"
  exit 1
fi

# One upload per source: puts every date folder for that source into the raw zone
for srcdir in "$STAGE"/*/; do
  src=$(basename "$srcdir")
  hdfs dfs -mkdir -p "/datalake/raw/$src"
  hdfs dfs -put -f "$srcdir"* "/datalake/raw/$src/"
  echo "  $src: $(ls "$srcdir" | wc -l) day folder(s) uploaded"
done

rm -rf "$STAGE"
echo "Ingested $count file(s) into /datalake/raw"
INNER
STATUS=$?

echo "Ingestion took $(( $(date +%s) - START )) seconds"
exit $STATUS
