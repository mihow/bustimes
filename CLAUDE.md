# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**bustimes** is a data collection and analysis project for Portland TriMet bus arrival time prediction. A Flask app on AWS Lambda fetches bus positions from the TriMet API every minute and saves raw JSON to S3. Separate Python scripts analyze the collected data (trip durations, delay patterns) using pandas.

## Architecture

### Data Pipeline

1. **Collection**: Lambda runs `save_bus_data()` every 1 minute via CloudWatch Events
2. **Storage**: Raw JSON saved to S3 bucket `bustimes-data` at `raw/bustimes__YYYY-MM-DD__HH-MM-SS.json`
3. **Analysis**: Offline scripts load JSON into pandas DataFrames, track bus state transitions (approaching/leaving stops), compute trip durations
4. **Visualization**: Dash app (`bustimes_dash.py`) for interactive maps and charts; matplotlib/seaborn for static boxplots

### Key Data Format Issue

Files before `2021-11-10T07:16Z` contain Python repr format (`u'key'`, `None`, `True`) instead of valid JSON. `fix_malformed_json.py` uses `ast.literal_eval()` to convert. The cutoff files are documented in `bustimes/README.md`.

### Main Components

| File | Purpose |
|---|---|
| `bustimes/bustimes.py` | Flask app + Lambda function (Python 2.7). Fetches TriMet API, saves to S3 |
| `find_completed_routes.py` | Core analysis: tracks bus state transitions to compute trip durations |
| `download_json_from_s3.py` | Threaded S3 download with Python repr → JSON conversion |
| `fix_malformed_json.py` | Standalone converter for malformed pre-2021 files |
| `make_trip_times_chart.py` | Generates boxplot charts of trip duration by hour |
| `bustimes_dash.py` | Plotly Dash interactive dashboard (requires `MAPBOX_ACCESS_TOKEN` env var) |
| `bustimes/zappa_settings.json` | Lambda deployment config |

### S3 Data

- Bucket: `bustimes-data` — 4.84M objects, 909 GB
- Active migration plan in `PLAN.md`: compress into weekly JSONL.gz files under `v2/`

## Commands

```bash
# Lambda app (Python 2.7 virtualenv required)
cd bustimes && source env/bin/activate
pip install -r requirements.txt
./runserver.sh                    # Flask dev server at localhost:5000

# Deploy
zappa deploy dev                  # Initial deploy
zappa update dev                  # Update existing
zappa schedule dev                # Enable 1-minute schedule

# Analysis scripts (Python 3)
python find_completed_routes.py path/to/data.json
python make_trip_times_chart.py completed_bus_routes-bus19.pickle bus19-sample.png
python bustimes_dash.py           # Dash app at localhost:8050
```

There is no test suite.

## Environment Variables

- `MAPBOX_ACCESS_TOKEN` — Dash dashboard map tiles
- `db4iot_credentials.py` — API_KEY/SECRET_KEY for DB4IoT (see `.py.example`)
- TriMet App ID is hardcoded in `bustimes/bustimes.py:14`

## AWS Resources

- S3 `bustimes-data` — data storage
- S3 `hackoregon-bustimes` — Zappa deployment artifacts
- DynamoDB `bustimes` — exists but `save_to_db()` is commented out
- Lambda 128 MB, Python 2.7
