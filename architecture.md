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

    classDef source fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef ingest fill:#ccfbf1,stroke:#0d9488,stroke-width:2px,color:#134e4a
    classDef raw fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef cleaned fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#78350f
    classDef curated fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef job fill:#ffedd5,stroke:#ea580c,stroke-width:2px,color:#7c2d12
    classDef result fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#312e81
    classDef report fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#581c87
    classDef future fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,stroke-dasharray:5 5,color:#374151

    class SRC source
    class ING ingest
    class RAW raw
    class CLEAN cleaned
    class CUR curated
    class J1,J2,J3,J4 job
    class RES result
    class REP report
    class RT future

    linkStyle default stroke:#64748b,stroke-width:2px

    style CLUSTER fill:#f8fafc,stroke:#334155,stroke-width:2px,color:#0f172a
    style HDFS fill:#f0fdf4,stroke:#16a34a,stroke-width:1px,color:#14532d
    style YARN fill:#fff7ed,stroke:#ea580c,stroke-width:1px,color:#7c2d12
```

| Layer | What happens | Folder in this repo |
| --- | --- | --- |
| 1. Source systems | Seven hotel systems export daily CSV and JSON files (synthetic data) | `data_generator/` |
| 2. Ingestion | The daily files are copied into the Raw zone unchanged | `pipeline/` |
| 3. Storage | HDFS holds the Raw, Cleaned and Curated zones, with three copies of each block | `cluster/` |
| 4. Processing | Python programs clean and join the data between zones; four MapReduce jobs (Hadoop Streaming) analyse the Curated zone and write their results to `/datalake/curated/reports` | `pipeline/`, `mapreduce/` |
| 5. Reporting | The job results are saved as CSV files and turned into charts | `charts/` |
