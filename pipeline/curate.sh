#!/bin/bash
# Curation step: CLEANED zone -> CURATED zone (three joined, report-ready datasets).
# Copies curate.py into the nodemanager container (which has Python 3 and the Hadoop client)
# and runs it there. Works from any folder, as long as the cluster is running.
#
#   bash curate.sh

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

cd "$(dirname "$0")" || exit 1     # the folder this script is in, where curate.py also is

if [ ! -f curate.py ]; then
  echo "curate.py not found. Keep it in the same folder as curate.sh."
  exit 1
fi

# Copy the latest version of the program into the container every time
docker exec nodemanager mkdir -p /pipeline
docker cp curate.py nodemanager:/pipeline/curate.py > /dev/null || exit 1

docker exec nodemanager python3 /pipeline/curate.py
