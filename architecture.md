# Architecture

The data lake runs on a Hadoop 3.2.1 cluster in Docker on one host machine. Data moves through five layers: source systems, ingestion, storage zones, processing and reporting. Each night, `pipeline/run_pipeline.sh` loads, cleans and joins the data, then `mapreduce/run_jobs.sh` runs the four MapReduce analysis jobs.

```mermaid
flowchart TB
    SRC["1. Source systems: 7 hotel systems, daily exports<br/>PMS, POS, procurement, ERP, HR as CSV<br/>Wi-Fi and reviews as JSON<br/>synthetic data"]
    RT["Real-time path<br/>future extension, not built"]
    ING["2. Ingestion: ingest.sh<br/>copies each day's files into HDFS unchanged"]

    subgraph CLUSTER["Hadoop 3.2.1 cluster in Docker on one host machine"]
        subgraph HDFS["3. Storage: HDFS, NameNode + 3 DataNodes, replication factor 3"]
            RAW["Raw zone<br/>files as received"]
            CLEAN["Cleaned zone<br/>fixed data, plus _rejected and _logs"]
            CUR["Curated zone<br/>guest_stay_summary, review_stay_link,<br/>department_daily"]
        end
        subgraph YARN["4. Processing: MapReduce on YARN, ResourceManager + NodeManager with Python 3.5"]
            J1["Job 1<br/>guest spend per stay,<br/>then per room type"]
            J2["Job 2<br/>purchasing cost<br/>vs revenue"]
            J3["Job 3<br/>Wi-Fi usage<br/>vs occupancy"]
            J4["Job 4<br/>reviews<br/>vs operations"]
        end
        RES["Job results stored in HDFS<br/>/datalake/curated/reports"]
    end

    REP["5. Reporting<br/>results saved as CSV files and turned into charts"]

    SRC --> ING --> RAW
    SRC -.-> RT
    RAW -- "clean.py" --> CLEAN
    CLEAN -- "curate.py" --> CUR
    CUR --> J1 & J2 & J3 & J4
    J1 & J2 & J3 & J4 --> RES
    RES --> REP
```

| Layer | What happens | Folder in this repo |
| --- | --- | --- |
| 1. Source systems | Seven hotel systems export daily CSV and JSON files (synthetic data) | `data_generator/` |
| 2. Ingestion | The daily files are copied into the Raw zone unchanged | `pipeline/` |
| 3. Storage | HDFS holds the Raw, Cleaned and Curated zones, with three copies of each block | `cluster/` |
| 4. Processing | Python programs clean and join the data between zones; four MapReduce jobs (Hadoop Streaming) analyse the Curated zone and write their results to `/datalake/curated/reports` | `pipeline/`, `mapreduce/` |
| 5. Reporting | The job results are saved as CSV files and turned into charts | `charts/` |
