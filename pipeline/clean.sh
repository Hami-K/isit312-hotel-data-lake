#!/bin/bash
# Cleaning step: RAW zone -> CLEANED zone.
# Copies clean.py into the nodemanager container (which has Python 3 and the Hadoop client)
# and runs it there. Works from any folder, as long as the cluster is running.
#
#   bash clean.sh                     clean every date in the raw zone
#   bash clean.sh 20261015            clean one day (what the nightly run does)
#   bash clean.sh 20261015 pos        clean one day of one source

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

cd "$(dirname "$0")" || exit 1     # the folder this script is in, where clean.py also is

DAY="${1:-all}"
SOURCE="${2:-all}"

if [ ! -f clean.py ]; then
  echo "clean.py not found. Keep it in the same folder as clean.sh."
  exit 1
fi

# Copy the latest version of the program into the container every time
docker exec nodemanager mkdir -p /pipeline
docker cp clean.py nodemanager:/pipeline/clean.py > /dev/null || exit 1

docker exec nodemanager python3 /pipeline/clean.py --date "$DAY" --source "$SOURCE"
