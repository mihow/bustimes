# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**bustimes** is a data collection and analysis project for Portland TriMet bus arrival time prediction. A Flask app on AWS Lambda fetches bus positions from the TriMet API every minute and saves raw JSON to S3. Separate Python scripts analyze the collected data (trip durations, delay patterns) using pandas.

## Architecture

### Data Pipeline

1. **Collection**: Lambda runs `save_bus_data()` every 1 minute via CloudWatch Events
2. **Storage**: Raw JSON saved to S3 at `raw/bustimes__YYYY-MM-DD__HH-MM-SS.json`
3. **Analysis**: Offline scripts load JSON into pandas DataFrames, track bus state transitions (approaching/leaving stops), compute trip durations
4. **Visualization**: Dash app (`bustimes_dash.py`) for interactive maps and charts; matplotlib/seaborn for static boxplots

### Two Python Runtimes

- **Lambda app** (`bustimes/`): Python 2.7, Flask, Zappa. Do not modernize — it's a running production service.
- **Everything else**: Python 3.10+. Analysis scripts, conversion scripts, notebooks.

### Key Data Format Issue

Files before `2021-11-10T07:16Z` contain Python repr format (`u'key'`, `None`, `True`) instead of valid JSON. `fix_malformed_json.py` uses `ast.literal_eval()` to convert. The last malformed file is `raw/bustimes__2021-11-10__07-15-05.json`.

### Main Components

| File | Purpose |
|---|---|
| `bustimes/bustimes.py` | Flask app + Lambda function (Python 2.7). Fetches TriMet API, saves to S3 |
| `scripts/convert_bustimes.py` | S3 migration: converts raw JSON into weekly gzipped JSONL under `v2/` |
| `find_completed_routes.py` | Core analysis: tracks bus state transitions to compute trip durations |
| `make_trip_times_chart.py` | Generates boxplot charts of trip duration by hour |
| `bustimes_dash.py` | Plotly Dash interactive dashboard (requires `MAPBOX_ACCESS_TOKEN` env var) |
| `fix_malformed_json.py` | Standalone converter for malformed pre-2021 files |

## Commands

```bash
# Lambda app (Python 2.7 virtualenv required)
cd bustimes && source env/bin/activate
pip install -r requirements.txt
./runserver.sh                    # Flask dev server at localhost:5000

# Deploy Lambda
zappa deploy dev                  # Initial deploy
zappa update dev                  # Update existing
zappa schedule dev                # Enable 1-minute schedule

# S3 data conversion (Python 3, active development)
python scripts/convert_bustimes.py --weeks 2021-W45 --output-dir data/output --validate
python scripts/convert_bustimes.py --all --output-dir v2 --profile michael
python scripts/convert_bustimes.py --local-dir data/test_local --output-dir data/test_output  # local test
python scripts/convert_bustimes.py --all --dry-run  # list without converting

# Analysis scripts (Python 3)
python find_completed_routes.py path/to/data.json
python make_trip_times_chart.py completed_bus_routes-bus19.pickle bus19-sample.png
python bustimes_dash.py           # Dash app at localhost:8050
```

There is no test suite.

## Environment Variables

- `MAPBOX_ACCESS_TOKEN` -- Dash dashboard map tiles
- `db4iot_credentials.py` -- API_KEY/SECRET_KEY for DB4IoT (see `.py.example`)
- TriMet App ID is hardcoded in `bustimes/bustimes.py:14`

## AWS

| Resource | Details |
|----------|---------|
| S3 `bustimes-data` | Data storage. **Region: us-east-1.** Account `144370233886`. Public READ ACL. STANDARD storage, no versioning, no lifecycle rules. |
| S3 `hackoregon-bustimes` | Zappa deployment artifacts |
| DynamoDB `bustimes` | Exists but `save_to_db()` is commented out |
| Lambda | 128 MB, Python 2.7, 1-minute CloudWatch schedule |

### AWS CLI

Use `aws2` (not `aws`) with `--profile michael` for bucket operations:

```bash
aws2 --profile michael s3 ls s3://bustimes-data/raw/ | head -5
aws2 --profile michael s3 cp local.gz s3://bustimes-data/v2/2020-W25.jsonl.gz
```

### S3 Bucket Contents

| Prefix | Count | Notes |
|--------|-------|-------|
| `raw/` | ~4.84M files | Main data, uncompressed `.json` |
| Root-level `bustimes__*` | 181 files | Dec 2016, before `raw/` prefix was added |
| `data_test/` | 4,971 files | `.json.gz` from a 2018 compression experiment. Cleanup candidate. |
| `every_minute/` | 2 files | Dec 2016 test, negligible |
| `v2/` | TBD | Target output for migration |

### Data Migration

Active plan in `PLAN.md`. Script: `scripts/convert_bustimes.py`.
Step 2 (local validation) complete -- 90,740 files, 0 errors, ~91% size reduction.
Step 3 (EC2 batch in us-east-1) is next.
