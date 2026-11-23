#!/bin/bash
# Creates the data lake zones in HDFS: raw, cleaned, curated
# Run from the folder with docker-compose.yml, after the cluster is up:
#   bash create_zones.sh

# Stop Git Bash / MSYS2 on Windows from turning /datalake into C:/...
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

SOURCES="pms pos procurement erp wifi reviews hr"

for zone in raw cleaned; do
  for src in $SOURCES; do
    docker exec namenode hdfs dfs -mkdir -p /datalake/$zone/$src
  done
done

# Curated holds report-ready tables, not one folder per source
docker exec namenode hdfs dfs -mkdir -p /datalake/curated/guest_spend
docker exec namenode hdfs dfs -mkdir -p /datalake/curated/cost_vs_revenue
docker exec namenode hdfs dfs -mkdir -p /datalake/curated/wifi_vs_occupancy
docker exec namenode hdfs dfs -mkdir -p /datalake/curated/reviews_vs_operations

echo "Zones created:"
docker exec namenode hdfs dfs -ls -R /datalake
