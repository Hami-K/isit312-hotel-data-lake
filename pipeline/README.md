# Data pipeline (Raw → Cleaned → Curated)

These scripts move the hotel data through the three zones of the data lake in HDFS.
One command runs the whole nightly batch.

| File | What it does |
| --- | --- |
| `ingest.sh` | Copies the daily source files into the Raw zone, unchanged, one folder per day (`/datalake/raw/<source>/<date>/`) |
| `clean.sh` + `clean.py` | Raw → Cleaned: standardises dates, room numbers and department names, removes duplicates, moves rows that cannot be fixed to `_rejected`, writes a log to `_logs` |
| `curate.sh` + `curate.py` | Cleaned → Curated: joins the sources into three report-ready datasets and replaces reservation IDs with a hashed `stay_key` |
| `run_pipeline.sh` | Runs the three steps in order, stops if one fails, and records the time of each step in `pipeline_timings.csv` |
| `pipeline_timings.csv` | Timings from the test runs |

## Requirements

- The cluster from `cluster/` running (`docker compose up -d --build`), with the zone folders created (`bash create_zones.sh`).
- The NodeManager built from the custom image in `cluster/`, which adds Python 3.5. The Python programs run inside that container.
- The source files in a `data` folder next to `docker-compose.yaml` (one subfolder per source, as produced by the data generator).
- Git Bash on Windows, or any bash shell.

## How to run

```bash
bash pipeline/run_pipeline.sh all        # first load: every day in the data folder
bash pipeline/run_pipeline.sh 20261031   # nightly run: one day
```

Each step can also be run on its own, for example `bash pipeline/clean.sh 20261015 pos`.

## Results (31 days of synthetic data)

| Step | Result |
| --- | --- |
| Ingestion | 217 files, 37 MB loaded into Raw |
| Cleaning | 300,968 rows read: 296,895 kept, 2,052 rejected, 2,021 duplicates removed |
| Curation | `guest_stay_summary` 16,417 rows, `review_stay_link` 1,491 rows, `department_daily` 463 rows |
| Timing | 88 s for one night, 262 s for the full month (limit: 2 hours) |

The code is written for Python 3.5 (the version in the Hadoop container), so it uses no f-strings.
The hashing salt for `stay_key` can be set with the `STAY_KEY_SALT` environment variable.
