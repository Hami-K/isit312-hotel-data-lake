# MapReduce analysis jobs (#9, report section 5.3)

Four MapReduce jobs in Python (Hadoop Streaming) that run on the Curated zone and produce the four management reports.

| Job | Folder | Input (Curated zone) | Output |
|---|---|---|---|
| 1a + 1b. Guest spend per stay (two chained jobs) | `job1_guest_spend/` | guest_stay_summary | guest_spend_per_stay, guest_spend_by_room_type |
| 2. Purchasing cost vs revenue | `job2_cost_vs_revenue/` | department_daily | cost_vs_revenue |
| 3. Wi-Fi usage vs occupancy | `job3_wifi_vs_occupancy/` | guest_stay_summary | wifi_vs_occupancy |
| 4. Reviews vs operations | `job4_reviews_vs_operations/` | review_stay_link | reviews_vs_operations |

Each reducer also works as the combiner (`--combine` mode outputs partial sums instead of averages).

## How to run

The cluster must be running and the Curated zone filled (see `cluster/` and `pipeline/`). From the repo root, in Git Bash:

```
bash mapreduce/run_jobs.sh        # all jobs, about 2-3 minutes
bash mapreduce/run_jobs.sh 3      # one job only (1, 2, 3 or 4)
```

Results go to HDFS under `/datalake/curated/reports/<job>/`, and a CSV copy goes to `./mapreduce_output/`.

## Other files

- `output/` - the CSV results from our run (used for the charts)
- `mapreduce_timings.csv` - seconds per job on the cluster (all five jobs: 137 s)
- `screenshots/` - Figures 5.3.1 to 5.3.6 in the report
