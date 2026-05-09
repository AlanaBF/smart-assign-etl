# Smart Assign - ETL Pipeline

Extracts CV/skills data from Flowcase (formerly CV Partner), transforms it, and loads it into PostgreSQL. Runs as a Docker container inside the Azure VNet with access to the private database endpoint.

## Tech Stack

- **Language:** Python 3.11
- **Data Processing:** pandas
- **Database:** SQLAlchemy + psycopg2 (PostgreSQL)
- **API Client:** requests (Flowcase REST API)
- **Testing:** pytest (with coverage, mocking)
- **Containerisation:** Docker (Azure Container Instance)

## Project Structure

```
smart-assign-etl/
├── Dockerfile                    # Container image definition
├── .dockerignore                 # Excludes secrets and dev files
├── .env.example                  # Environment variable template
├── pyproject.toml                # Package definition and CLI entry point
├── azure-pipelines.yml           # CI/CD pipeline (test + build image)
└── flowcase_etl/
    ├── requirements.txt          # Python dependencies
    ├── make_fake_flowcase_reports.py  # Generates synthetic test data
    ├── cv_reports/               # Generated CSV data (quarterly snapshots)
    └── src/
        ├── flowcase_etl_pipeline/
        │   ├── cli.py            # CLI entry point (run_etl)
        │   ├── config.py         # Settings and DB config from environment
        │   ├── db.py             # Database connection and schema application
        │   ├── extract.py        # Reads CSV reports into DataFrames
        │   ├── transform.py      # Data cleaning, parsing, normalisation
        │   ├── load.py           # Upserts into PostgreSQL tables
        │   ├── flowcase_client.py # Flowcase API client (real data mode)
        │   ├── fake_data.py      # Wrapper for fake data generation
        │   └── constants.py      # CSV column name mappings
        ├── sql/
        │   ├── 01_schema.sql     # Database schema (tables, indices)
        │   └── 02_cv_search_profile_mv.sql  # Materialized view for search
        └── tests/
            ├── test_extract.py
            ├── test_transform.py
            ├── test_load.py
            └── test_integration_etl.py
```

## How It Works

1. **Extract** — Reads CSV reports from the latest quarterly folder (or downloads from Flowcase API in real mode)
2. **Transform** — Parses multilingual fields, maps SFIA/CPD levels, normalises dates, validates data
3. **Load** — Upserts into ~20 PostgreSQL tables using `INSERT ... ON CONFLICT ... DO UPDATE` (idempotent, safe to re-run)
4. **Refresh** — Refreshes the `cv_search_profile_mv` materialized view used by the backend API

## Prerequisites

- Python 3.11+
- Access to a PostgreSQL database

## Local Development Setup

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install the package and dependencies:**
   ```bash
   pip install -e .
   pip install -r flowcase_etl/requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

4. **Run the pipeline (generates fake data and loads it):**
   ```bash
   python -m flowcase_etl_pipeline.cli --generate-fake
   ```

## CLI Options

| Flag | Description |
|------|-------------|
| `--generate-fake` | Generate new synthetic CSV reports before running |
| `--data-folder PATH` | Override the cv_reports directory |
| `--sql-folder PATH` | Override the SQL schema directory |
| `--skip-refresh` | Skip refreshing the materialized view after load |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PGHOST` | Yes | — | PostgreSQL host |
| `PGPORT` | Yes | — | PostgreSQL port |
| `PGDATABASE` | Yes | — | Database name |
| `PGUSER` | Yes | — | Database user |
| `PGPASSWORD` | Yes | — | Database password |
| `PGSSLMODE` | No | `require` | SSL mode (use `require` for Azure, `prefer` for local) |
| `FLOWCASE_DATA_SOURCE` | No | `fake` | Data source: `fake` (synthetic) or `real` (Flowcase API) |
| `FLOWCASE_SUBDOMAIN` | Only if real | — | Flowcase instance subdomain |
| `FLOWCASE_API_TOKEN` | Only if real | — | Flowcase API bearer token |
| `FLOWCASE_OFFICE_IDS` | No | — | Comma-separated office IDs to filter |
| `FLOWCASE_LANG_PARAMS` | No | — | Comma-separated language codes |

## Data Modes

| Mode | What Happens |
|------|-------------|
| `fake` | Generates 500 synthetic users with realistic CVs, skills, clearances, and availability |
| `real` | Calls Flowcase API to download 14 report types as CSVs, then processes them |

## Deployment

The ETL runs as an **Azure Container Instance** inside the VNet. It is not always running — it starts on demand and stops when complete.

**Pipeline trigger:** Push to `main` branch

**Pipeline stages:**
1. Test (pytest with coverage)
2. Security audit (pip-audit + bandit)
3. SonarCloud analysis
4. Build Docker image and push to ACR

**To trigger a data load:**
```bash
az container start --name smart-assign-etl --resource-group <YOUR_RESOURCE_GROUP>
```

Or click "Start" on the Container Instance in the Azure portal.

## Database Schema

The pipeline creates and maintains:
- **Core tables:** `users`, `cvs`
- **Dimension tables:** `dim_technology`, `dim_language`, `dim_industry`, `dim_project_type`, `dim_clearance`
- **Detail tables:** `cv_technology`, `cv_language`, `project_experience`, `work_experience`, `certification`, `course`, `education`, `position`, `blog_publication`, `cv_role`, `key_qualification`
- **Operational tables:** `user_clearance`, `user_availability`
- **Materialized view:** `cv_search_profile_mv` (denormalised search profile used by the backend API)

## Important Notes

- The production PostgreSQL database is only accessible via private endpoint. The Container Instance runs inside the VNet to reach it.
- All upserts are idempotent — running the pipeline multiple times does not create duplicates.
- The pipeline creates the database schema on every run (tables are created if not existing, data is upserted).
- Fake data mode generates 500 users. Real mode pulls whatever is in Flowcase.
