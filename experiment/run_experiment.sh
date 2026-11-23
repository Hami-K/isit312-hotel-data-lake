#!/usr/bin/env bash
# ISIT312 #6 - Is MapReduce fast enough for real-time? Timing experiment.
# Run from Git Bash in this folder while the Hadoop Docker cluster is up:
#     bash run_experiment.sh
# Optional overrides:  NN=namenode NM=nodemanager REPS=3 INTERVAL=10 BATCHES=6 bash run_experiment.sh
set -euo pipefail

# Stop Git Bash turning /datalake/... into C:/... (same fix as section 5.1.6)
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL="*"

NN=${NN:-namenode}            # container we submit jobs from
NM=${NM:-nodemanager}         # container that runs the map/reduce tasks
REPS=${REPS:-3}               # repeats per input size (median is reported)
SIZES=${SIZES:-"10 1500 45000 547500"}   # 10 min, 1 day, 30 days, 1 year of POS checks
INTERVAL=${INTERVAL:-10}      # Experiment B: seconds between arriving mini-batches
BATCHES=${BATCHES:-6}         # Experiment B: number of mini-batches
BATCH_ROWS=${BATCH_ROWS:-50}
EXP=/datalake/experiments/realtime
TMP=/tmp/rtexp

now_ms() { date +%s%3N; }
log() { echo "[$(date +%H:%M:%S)] $*"; }

# ---- 0. Pick a Python on the host ----------------------------------------
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c "import sys; sys.exit(0)" >/dev/null 2>&1; then PY=$c; break; fi
done
[ -n "$PY" ] || { echo "No working Python found on this machine (tried python3, python, py)."; exit 1; }
log "Host Python: $PY"

# ---- 1. Check the cluster -------------------------------------------------
for c in "$NN" "$NM"; do
  docker ps --format '{{.Names}}' | tr -d '\r' | grep -qx "$c" || {
    echo "Container '$c' is not running. Start the cluster, or set NN=/NM= to your container names:"
    docker ps --format '  {{.Names}}'; exit 1; }
done
JAR=$(docker exec "$NN" bash -c 'ls $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-*.jar' | head -1 | tr -d '\r')
[ -n "$JAR" ] || { echo "Could not find the Hadoop Streaming jar in $NN"; exit 1; }
log "Streaming jar: $JAR"

if docker exec "$NM" sh -c 'command -v python3' >/dev/null 2>&1; then
  MODE=python; MAP="python3 mapper.py"; RED="python3 reducer.py"; FILES="file://$TMP/mapper.py,file://$TMP/reducer.py"
else
  MODE=awk; MAP="sh mapper.sh"; RED="sh reducer.sh"; FILES="file://$TMP/mapper.sh,file://$TMP/reducer.sh"
  log "python3 not found on $NM - using the awk version of the same job (same logic, see mapper.sh)"
fi
log "Job mode: $MODE"

# ---- 2. Generate data -----------------------------------------------------
mkdir -p data results logs
for n in $SIZES; do
  [ -f "data/pos_$n.csv" ] || $PY gen_pos.py --rows "$n" --out "data/pos_$n.csv"
done
for i in $(seq 1 "$BATCHES"); do
  $PY gen_pos.py --rows "$BATCH_ROWS" --seed $((100 + i)) --out "data/batch_$i.csv"
done
log "Data generated in ./data"

# ---- 3. Copy scripts + data into the cluster ------------------------------
docker exec "$NN" mkdir -p "$TMP"
for f in mapper.py reducer.py mapper.sh reducer.sh; do docker cp "$f" "$NN:$TMP/$f" >/dev/null; done
docker exec "$NN" hdfs dfs -mkdir -p "$EXP/input" "$EXP/stream"
for n in $SIZES; do
  docker cp "data/pos_$n.csv" "$NN:$TMP/pos_$n.csv" >/dev/null
  docker exec "$NN" hdfs dfs -mkdir -p "$EXP/input/$n"
  docker exec "$NN" hdfs dfs -put -f "$TMP/pos_$n.csv" "$EXP/input/$n/"
done
log "Inputs loaded to HDFS under $EXP/input"

run_job() {   # $1 = HDFS input, $2 = HDFS output, $3 = log file
  docker exec "$NN" hdfs dfs -rm -r -f -skipTrash "$2" >/dev/null 2>&1 || true
  docker exec "$NN" hadoop jar "$JAR" \
      -D mapreduce.job.name="rt-experiment" -D mapreduce.job.reduces=1 \
      -files "$FILES" -mapper "$MAP" -reducer "$RED" \
      -input "$1" -output "$2" >"$3" 2>&1
}

# ---- 4. Experiment A: latency vs input size -------------------------------
log "Warm-up job (not recorded)"
run_job "$EXP/input/10" "$EXP/out/warmup" logs/warmup.log || { echo "Warm-up job failed - see logs/warmup.log"; tail -20 logs/warmup.log; exit 1; }

echo "method,rows,bytes,rep,seconds" > results/timings.csv
for n in $SIZES; do
  bytes=$(wc -c < "data/pos_$n.csv" | tr -d ' ')
  for r in $(seq 1 "$REPS"); do
    t0=$(now_ms)
    run_job "$EXP/input/$n" "$EXP/out/size_$n" "logs/size_${n}_rep$r.log" || { echo "Job failed - see logs/size_${n}_rep$r.log"; exit 1; }
    t1=$(now_ms)
    secs=$(awk "BEGIN{printf \"%.2f\", ($t1-$t0)/1000}")
    echo "mapreduce,$n,$bytes,$r,$secs" >> results/timings.csv
    log "MapReduce  rows=$n rep=$r  ${secs}s"
    secs=$($PY baseline_local.py "data/pos_$n.csv" | tr -d '\r')
    echo "python,$n,$bytes,$r,$secs" >> results/timings.csv
    log "Python     rows=$n rep=$r  ${secs}s"
  done
done
docker exec "$NN" hdfs dfs -cat "$EXP/out/size_1500/part-00000" > results/sample_output.txt
log "Sample job output (1 day of checks):"; cat results/sample_output.txt

# ---- 5. Experiment B: mini-batches arriving every INTERVAL seconds --------
# Each batch is a few minutes of sales. A batch can only be processed once the
# previous job has finished, so if a job takes longer than INTERVAL a queue builds.
echo "batch,arrival_s,start_s,finish_s,queue_wait_s,job_s,data_age_s" > results/stream.csv
for i in $(seq 1 "$BATCHES"); do
  docker cp "data/batch_$i.csv" "$NN:$TMP/batch_$i.csv" >/dev/null
done
docker exec "$NN" hdfs dfs -rm -r -f -skipTrash "$EXP/stream" >/dev/null 2>&1 || true
docker exec "$NN" hdfs dfs -mkdir -p "$EXP/stream"
log "Experiment B: $BATCHES batches of $BATCH_ROWS rows, one every ${INTERVAL}s"
T0=$(now_ms)
for i in $(seq 1 "$BATCHES"); do
  arrival=$((T0 + i * INTERVAL * 1000))
  now=$(now_ms)
  if [ "$now" -lt "$arrival" ]; then sleep "$(awk "BEGIN{print ($arrival-$now)/1000}")"; fi
  start=$(now_ms)
  docker exec "$NN" hdfs dfs -mkdir -p "$EXP/stream/b$i"
  docker exec "$NN" hdfs dfs -put -f "$TMP/batch_$i.csv" "$EXP/stream/b$i/"
  run_job "$EXP/stream/b$i" "$EXP/out/stream_$i" "logs/stream_$i.log" || { echo "Job failed - see logs/stream_$i.log"; exit 1; }
  finish=$(now_ms)
  echo "$i,$(awk "BEGIN{printf \"%.2f,%.2f,%.2f,%.2f,%.2f,%.2f\", ($arrival-$T0)/1000, ($start-$T0)/1000, ($finish-$T0)/1000, ($start-$arrival)/1000, ($finish-$start)/1000, ($finish-$arrival)/1000}")" >> results/stream.csv
  log "Batch $i: arrived t=$(( (arrival-T0)/1000 ))s, result ready $(awk "BEGIN{printf \"%.1f\", ($finish-$arrival)/1000}")s after arrival"
done

# ---- 6. Summarise ---------------------------------------------------------
docker exec "$NN" bash -c 'hadoop version | head -1' > results/env.txt 2>/dev/null || true
echo "job_mode=$MODE reps=$REPS interval=$INTERVAL batch_rows=$BATCH_ROWS" >> results/env.txt
$PY analyse.py || log "Charts not drawn (pip install matplotlib, then: $PY analyse.py)"
log "Done. Results in ./results  - now take the screenshots listed in README.md"
