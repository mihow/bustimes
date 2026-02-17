# Plan: Compress, Fix JSON, and Combine S3 Data

## Context

The Lambda writes TriMet bus positions every minute to S3. The bucket has 4.84M objects totaling 909 GB, costing ~$21/month in storage. Files are uncompressed, and those created before 2021-11-10T07:16Z contain Python repr format (not valid JSON — `u'key'`, `None`, `True` instead of `"key"`, `null`, `true`). Gzip yields ~88% size reduction.

- **Last malformed file:** `raw/bustimes__2021-11-10__07-15-05.json`
- **First valid JSON file:** `raw/bustimes__2021-11-10__07-16-05.json`
- Existing `fix_malformed_json.py` has the `ast.literal_eval()` approach to reuse

## Target format

One gzipped JSONL file per ISO week:
```
v2/2020-W25.jsonl.gz   (~250 MB)
```
Each line = one bus position record with `snapshot_time` (ISO 8601) added. ~10K source files per week → 1 output file. 4.8M files → ~480 files. 909 GB → ~100 GB.

---

## Step 1: Build conversion script

Create `scripts/convert_bustimes.py`:

- Takes `--weeks` (comma-separated) or `--all` flag
- For each ISO week: lists source objects, downloads with thread pool, parses (literal_eval or json.loads based on cutoff), writes combined gzipped JSONL
- Adds `snapshot_time` field to each record (from filename timestamp)
- `--dry-run`, `--validate`, `--workers N` (default 16)
- Resume support (skip weeks with existing output in v2/)

## Step 2: Test locally on stratified sample — DONE (2025-02-16)

One week from each year plus the transition week:
```
--weeks 2017-W03,2018-W25,2019-W50,2020-W25,2021-W45,2022-W25,2023-W25,2024-W25,2025-W25
```
2021-W45 = Nov 8-14, contains the format transition on Nov 10.

Results: **90,740 files → 25,361,072 records, 0 errors, 0 validation failures.**

| Week | Files | Records | Size | Format |
|------|-------|---------|------|--------|
| 2017-W03 | 10,085 | 2,676,153 | 164M | Python repr |
| 2018-W25 | 10,080 | 2,995,719 | 177M | Python repr |
| 2019-W50 | 10,081 | 3,156,175 | 194M | Python repr |
| 2020-W25 | 10,081 | 2,691,509 | 159M | Python repr |
| 2021-W45 | 10,093 | 2,870,380 | 173M | Mixed (transition) |
| 2022-W25 | 10,080 | 2,623,277 | 160M | Valid JSON |
| 2023-W25 | 10,080 | 2,715,906 | 171M | Valid JSON |
| 2024-W25 | 10,080 | 2,738,300 | 196M | Valid JSON |
| 2025-W25 | 10,080 | 2,893,653 | 195M | Valid JSON |

Avg ~180 MB/week compressed. Extrapolated: ~480 weeks × 180 MB ≈ 85 GB (vs 909 GB raw = 91% reduction).

## Step 3: Full batch on EC2 spot instance

- Launch spot instance in same region as bucket (~$0.01/hr)
- SCP script, run in tmux
- ~$4-5 total (compute + S3 API costs)
- Resumes from where it left off if interrupted

## Step 4: Lambda update (later)

New standalone Python 3.12 Lambda writing gzipped JSONL. Existing Lambda stays untouched (web app still live at API Gateway endpoint).

## Step 5: Athena + cleanup (later)

Create Athena table over `v2/`, validate queries, delete originals.

## Key references

| File | What to reuse |
|---|---|
| `fix_malformed_json.py` | `fix_json()` — `ast.literal_eval` for Python repr |
| `download_json_from_s3.py` | Thread pool + S3 download pattern |
| `bustimes/bustimes.py:85-107` | Current `save_to_s3()` format |
