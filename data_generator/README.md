# Synthetic data generator

`generate_data.ipynb` creates the synthetic data for the seven hotel systems (PMS, POS, procurement, ERP, HR, Wi-Fi and reviews), based on the data model in the report. It includes the quality problems the cleaning pipeline has to fix: mixed date formats, room numbers with and without a leading zero, different spellings of department names, duplicates and missing values.

## How to run

Open the notebook in Google Colab or Jupyter and run all cells. The first cell writes `generate_data.py`, and the third runs it:

```
python generate_data.py --start 2026-10-01 --days 31 --out data
```

This creates a `data` folder with one subfolder per source and one file per day (217 files, about 37 MB). Copy the `data` folder into `cluster/`, so the cluster sees it as `/data`.
