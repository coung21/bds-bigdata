# BDS Big Data Pipeline

A simple pipeline to crawl listings, stream raw data to Kafka, process with Spark, and persist to Postgres. Includes a Streamlit dashboard for monitoring prices, areas, locations, and recent listings.

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
make run-dashboard
```

Open: http://localhost:8501

The dashboard includes:

- Filters for row count, area, total price, and district/area.
- KPI cards for listing count, average total price, average area, and average price per square meter.
- Charts for unit price trend, top listing areas, total price distribution, and area distribution.
- A recent listings table with direct links to source pages.

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
