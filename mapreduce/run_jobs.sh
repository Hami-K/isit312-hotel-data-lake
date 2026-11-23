#!/bin/bash
# MapReduce analysis jobs on the CURATED zone of the hotel data lake (Hadoop Streaming, Python).
#
#   Job 1  Guest spend per stay       guest_stay_summary -> 1a per stay -> 1b per room type (chained)
#   Job 2  Purchasing cost vs revenue department_daily   -> per department
#   Job 3  Wi-Fi usage vs occupancy   guest_stay_summary -> per day
#   Job 4  Reviews vs operations      review_stay_link   -> per room type and per theme in the text
#
# Run from the folder with docker-compose.yml, after run_pipeline.sh has filled the curated zone:
#   bash run_jobs.sh          run all four jobs
#   bash run_jobs.sh 3        run only job 3 (1, 2, 3 or 4)
#
# Results:  HDFS   /datalake/curated/reports/<job>/part-00000
#           laptop ./mapreduce_output/<job>.csv   (with a header row, for the charts)
#           laptop ./mapreduce_timings.csv        (seconds per job)

export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

ONLY="${1:-all}"
CURATED=/datalake/curated
REPORTS=/datalake/curated/reports
OUTDIR=mapreduce_output

if [ ! -d mapreduce ]; then
  echo "mapreduce folder not found. Put it next to docker-compose.yml."
  exit 1
fi

# The nodemanager container has Python 3 and the Hadoop client, so jobs are submitted from there
docker exec nodemanager mkdir -p /mapreduce
docker cp mapreduce/. nodemanager:/mapreduce/ > /dev/null || exit 1
docker exec nodemanager hdfs dfs -mkdir -p "$REPORTS"
mkdir -p "$OUTDIR"
[ -f mapreduce_timings.csv ] || echo "started_at,job,seconds,status" > mapreduce_timings.csv

# run_job <name> <job folder> <input> <mapper> <reducer> <combiner>
run_job() {
  local name="$1" dir="/mapreduce/$2" input="$3" mapper="$4" reducer="$5" combiner="$6"
  local output="$REPORTS/$name"
  echo ""
  echo "=================== $name"
  echo "input : $input"
  echo "output: $output"
  local started=$(date "+%Y-%m-%d %H:%M:%S")
  local t0=$(date +%s)

  # Hadoop will not overwrite an existing output folder, so remove the last run's result
  docker exec nodemanager hdfs dfs -rm -r -f -skipTrash "$output" > /dev/null

  docker exec nodemanager bash -c '
    JAR=$(ls ${HADOOP_HOME:-/opt/hadoop-3.2.1}/share/hadoop/tools/lib/hadoop-streaming-*.jar | head -1)
    hadoop jar "$JAR" \
      -D mapreduce.job.name="hotel-datalake '"$name"'" \
      -D mapreduce.job.reduces=1 \
      -files '"$dir/$mapper"','"$dir/$reducer"' \
      -input '"$input"' \
      -output '"$output"' \
      -mapper "python3 '"$mapper"'" \
      -combiner "python3 '"$combiner"'" \
      -reducer "python3 '"$reducer"'"
  '
  local rc=$?
  local secs=$(( $(date +%s) - t0 ))
  local status=$([ $rc -eq 0 ] && echo SUCCEEDED || echo FAILED)
  echo "$started,$name,$secs,$status" >> mapreduce_timings.csv
  echo "------------------- $name $status in ${secs}s"
  [ $rc -eq 0 ] || { echo "Job failed. See the YARN UI at http://localhost:8088 for the task logs."; exit 1; }
}

# save_output <name> <header>: copy the result to the laptop as CSV, and show it
save_output() {
  local name="$1" header="$2"
  { echo "$header"; docker exec nodemanager hdfs dfs -cat "$REPORTS/$name/part-*" | tr '\t' ','; } \
    > "$OUTDIR/$name.csv"
  echo ""
  echo "Result ($OUTDIR/$name.csv):"
  head -20 "$OUTDIR/$name.csv"
}

START=$(date +%s)

if [ "$ONLY" = "all" ] || [ "$ONLY" = "1" ]; then
  # 1a: add up every night of each stay. The stay reducer keeps the input layout, so it is also the combiner.
  run_job guest_spend_per_stay job1_guest_spend "$CURATED/guest_stay_summary" \
          mapper_stay.py reducer_stay.py reducer_stay.py
  # 1b: chained job - reads 1a's output and averages the stays per room type
  run_job guest_spend_by_room_type job1_guest_spend "$REPORTS/guest_spend_per_stay" \
          mapper_roomtype.py reducer_roomtype.py "reducer_roomtype.py --combine"
  save_output guest_spend_by_room_type \
    "room_type,stays,avg_nights,avg_room_revenue_per_stay,avg_fnb_spend_per_stay,avg_total_spend_per_stay,fnb_share_pct,pct_stays_with_fnb_spend"
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "2" ]; then
  run_job cost_vs_revenue job2_cost_vs_revenue "$CURATED/department_daily" \
          mapper.py reducer.py "reducer.py --combine"
  save_output cost_vs_revenue \
    "department,days,purchase_orders,purchase_cost,erp_revenue,purchase_pct_of_revenue,erp_cost,pos_revenue,avg_staff_on_shift"
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "3" ]; then
  run_job wifi_vs_occupancy job3_wifi_vs_occupancy "$CURATED/guest_stay_summary" \
          mapper.py reducer.py "reducer.py --combine"
  save_output wifi_vs_occupancy \
    "date,weekday,occupied_rooms,occupancy_pct,wifi_sessions,wifi_gb,mb_per_occupied_room,sessions_per_occupied_room,pct_rooms_using_wifi"
fi

if [ "$ONLY" = "all" ] || [ "$ONLY" = "4" ]; then
  run_job reviews_vs_operations job4_reviews_vs_operations "$CURATED/review_stay_link" \
          mapper.py reducer.py "reducer.py --combine"
  save_output reviews_vs_operations \
    "group,name,reviews,avg_score,pct_low_scores,avg_nights,negative_mentions,pct_negative"
fi

echo ""
echo "All jobs finished in $(( $(date +%s) - START ))s. Outputs in HDFS:"
docker exec nodemanager hdfs dfs -ls "$REPORTS"
echo "CSV copies for the charts are in ./$OUTDIR/ and job times in mapreduce_timings.csv"
