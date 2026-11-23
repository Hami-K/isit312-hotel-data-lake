## Test A: time to get a result by data size (median of 3 runs)

| Input (POS checks) | MapReduce (s) | Plain Python (s) | MapReduce / Python |
|---|---|---|---|
| 10 | 19.3 | 0.0002 | 96,450x |
| 1,500 | 20.7 | 0.0022 | 9,395x |
| 45,000 | 20.3 | 0.0442 | 460x |
| 547,500 | 22.3 | 0.5606 | 40x |

## Test B: a new batch every 10 seconds

| Batch | Arrived (s) | Waited in queue (s) | Upload + job (s) | Result ready after arrival (s) |
|---|---|---|---|---|
| 1 | 10 | 0.2 | 24.6 | 24.8 |
| 2 | 20 | 14.9 | 25.4 | 40.3 |
| 3 | 30 | 30.5 | 30.0 | 60.5 |
| 4 | 40 | 50.8 | 26.6 | 77.3 |
| 5 | 50 | 67.5 | 26.4 | 93.9 |
| 6 | 60 | 84.1 | 28.4 | 112.5 |
