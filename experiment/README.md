# Timing experiment (#6, report section 7.1)

A timing experiment that tests whether MapReduce could give management real-time results by simply running jobs more often. It shows that every MapReduce job has a fixed start-up delay of about 19 seconds, even for 10 rows. MapReduce therefore suits the nightly batch but not real-time processing.

The test job counts the number of sales and the total revenue per POS outlet, using synthetic POS data at about 1,500 sales a day.

| Test | What it does |
|---|---|
| Test A | Runs the job on 10 rows (about 10 minutes of sales), 1,500 rows (1 day), 45,000 rows (30 days) and 547,500 rows (1 year), 3 times each, and compares the median time with the same calculation in plain Python |
| Test B | Sends a batch of 50 new sales every 10 seconds and runs one job per batch, to measure how far behind the results fall |

## Results

| Input | MapReduce (median) | Plain Python (median) |
|---|---|---|
| 10 rows | 19.3 s | 0.0002 s |
| 1,500 rows | 20.7 s | 0.0022 s |
| 45,000 rows | 20.3 s | 0.044 s |
| 547,500 rows | 22.3 s | 0.56 s |

In Test B, the delay grew from 24.8 seconds for the first batch to 112.5 seconds for the sixth, because each job took longer than the 10-second gap between batches. Full tables are in `results/summary.md`.

## How to run

The cluster must be running (see `cluster/`). This experiment uses its own HDFS folder, `/datalake/experiments/realtime`, so it does not affect the data lake zones. From the repo root, in Git Bash:

```
cd experiment
bash run_experiment.sh       # about 10 minutes
```

The script generates the test data, loads it into HDFS, runs Test A and Test B, and then runs `analyse.py` to make the tables and the two charts (Figures 7.1 and 7.4 in the report). The charts need matplotlib (`pip install matplotlib`).

To remove the test data from HDFS afterwards:
```
MSYS_NO_PATHCONV=1 docker exec namenode hdfs dfs -rm -r -skipTrash /datalake/experiments
```

## Files

| File | What it does |
|---|---|
| `run_experiment.sh` | Runs the whole experiment and times each job |
| `gen_pos.py` | Generates synthetic POS sales (about 1,500 a day, generic outlet names) |
| `mapper.py`, `reducer.py` | The MapReduce job (Hadoop Streaming): sales and revenue per outlet |
| `mapper.sh`, `reducer.sh` | The same job as shell scripts, used automatically if python3 is not available on the NodeManager |
| `baseline_local.py` | The same calculation in plain Python, without Hadoop |
| `analyse.py` | Makes the result tables and the two charts from the CSV files |

## Other files

- `results/timings.csv` - every Test A run (method, rows, file size, run number, seconds)
- `results/stream.csv` - every Test B batch (arrival, queue wait, job time, delay)
- `results/summary.md` - the result tables used in the report
- `results/sample_output.txt` - the job's output for one day of sales

The generated data files are not included. `gen_pos.py` recreates exactly the same data, because it uses a fixed random seed.
