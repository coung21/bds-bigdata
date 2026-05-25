# BDS Big Data Pipeline

A simple pipeline to crawl listings, stream raw data to Kafka, process with Spark, and persist to Postgres. Includes a Streamlit dashboard to explore recent rows and basic charts.

## Requirements

- Docker + Docker Compose
- Conda environment: `bds`
- Python deps in `requirements.txt`

## Setup

```bash
conda activate bds
pip install -r requirements.txt
```

## Start the pipeline

```bash
make up
make create-topic

# In separate terminals:
make run-spark
make run-producer
```

## Dashboard

```bash
conda activate bds
streamlit run dashboard/streamlit_app.py --server.address 0.0.0.0 --server.port 8501
```

Open: http://localhost:8501

## Stop everything

```bash
make down
```

## Environment variables

You can override DB connection values for the dashboard:

- `DB_HOST` (default: `localhost`)
- `DB_PORT` (default: `5432`)
- `DB_NAME` (default: `bds`)
- `DB_USER` (default: `user`)
- `DB_PASSWORD` (default: `password`)
