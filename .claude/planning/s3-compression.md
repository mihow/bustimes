# S3 Data Compression, JSON Fix & Consolidation

GitHub issue: https://github.com/mihow/bustimes/issues/3

## Problem

The S3 bucket has ~4.84M uncompressed files totaling 909 GB (~$21/month). Two issues:

1. **No compression** — gzip yields ~88% reduction (tested: 287 KB → 33 KB per file)
2. **Invalid JSON pre-2021-11-10** — Python 2 repr format (`u'key'`, `None`, `True`) instead of valid JSON

## Format cutoff (verified)
- Last malformed: `raw/bustimes__2021-11-10__07-15-05.json`
- First valid JSON: `raw/bustimes__2021-11-10__07-16-05.json`
- Matches Lambda's last deployment: 2021-11-10T07:15:58Z

## Target

Weekly gzipped JSONL files:
```
v2/2020-W25.jsonl.gz   (~250 MB)
```
Each line = one vehicle position record with `snapshot_time` added.
4.8M files → ~480 files. 909 GB → ~100 GB. Saves ~$19/month.

---

## Steps

### 1. Build `scripts/convert_bustimes.py`

Conversion script that:
- Lists source objects by ISO week
- Downloads with thread pool (16 workers, pattern from `download_json_from_s3.py`)
- Parses each file (literal_eval pre-cutoff, json.loads post-cutoff)
- Adds `snapshot_time` to each record (from filename)
- Writes combined gzipped JSONL per week
- Supports `--weeks`, `--all`, `--dry-run`, `--validate`, `--workers`, resume

### 2. Test locally on stratified sample

```
--weeks 2017-W03,2018-W25,2019-W50,2020-W25,2021-W45,2022-W25,2023-W25,2024-W25,2025-W25
```

### 3. Full batch on EC2 spot instance (same region as bucket)

Run in tmux, resumes on interruption. ~$5 total cost.

### 4. Lambda update (separate)

New Python 3.12 Lambda writing gzipped JSONL. Existing Lambda stays for web app.

### 5. Athena + cleanup (separate)

Create Athena table, validate queries, delete originals.

---

## Assumptions to verify

### Before writing the script

- [ ] **Root-level files scope**: There are ~182 `bustimes__*.json` files at the bucket root (not in `raw/`). These are from Dec 2016. Need to confirm they are the same format as early `raw/` files (Python repr). *Should be included in conversion.*

- [ ] **All pre-cutoff files are Python repr**: Assumed all files before 2021-11-10T07:16Z are Python repr. The stratified sample test (step 2) will verify this across years. *If some files are already valid JSON, `ast.literal_eval` would still work on them, but it's slower.*

- [ ] **JSON fields are consistent across years**: The TriMet API response schema may have changed over 9 years (fields added/removed/renamed). The conversion script preserves whatever fields exist per record, but Athena table schema needs to be a superset. *Verify during sample test by comparing field sets across years.*

### During sample test

- [ ] **Compression ratio holds**: Tested on two files (88% reduction). Monthly/weekly aggregated compression may be slightly different due to repeated field names across records in the same file. *Measure actual ratio during sample run.*

- [ ] **No encoding issues**: Python repr files might have unusual unicode handling with `ast.literal_eval`. *Watch for UnicodeDecodeError or ValueError during sample run.*

- [ ] **File naming is consistent**: Assumed all files follow `bustimes__YYYY-MM-DD__HH-MM-SS.json` pattern. *Verify no edge cases (missing files, duplicate timestamps, unexpected prefixes).*

- [ ] **Record counts are stable**: ~800-1000 vehicles per snapshot (based on recent data). Older data may have fewer. *Not a problem, just note it.*

### Before full batch

- [ ] **Spot instance IAM access**: Need IAM role or instance profile with S3 read/write. Current setup uses SSO profiles which won't work on EC2 — need to create an IAM role or use access keys. *Decide: IAM instance profile (cleaner) vs temporary credentials.*

- [ ] **s5cmd viability**: May be faster than boto3 for bulk downloads. *Test during sample run — if downloads are the bottleneck, s5cmd could cut total time significantly.*

- [ ] **Disk space on spot instance**: A week of data is ~2 GB uncompressed. Processing one week at a time in memory (streaming gzip) avoids disk constraints. *But if using s5cmd bulk download, need temp disk space. t3.medium has 20 GB EBS by default — may need more or use instance store.*

### Before cleanup

- [ ] **No other consumers of `raw/` prefix**: Confirm nothing else reads from `raw/` (no other Lambda, no Athena table, no external integration). *The web app's `save_to_s3()` also writes to `raw/` — the new Lambda should write to `v2/` instead.*

- [ ] **Data integrity**: Spot-check random weeks by comparing record counts: `(files in raw/) × (avg records per file)` should match `(lines in v2/ JSONL)`. *Build this check into the --validate flag.*

## Existing code to reuse

| File | What | Notes |
|---|---|---|
| `fix_malformed_json.py` | `ast.literal_eval` parsing | Proven approach, used in production |
| `download_json_from_s3.py` | Thread pool + S3 pattern | 16 workers, `bucket.objects.filter(Prefix=...)` |
| `bustimes/bustimes.py:23-31` | `get_bus_data()` | Shows TriMet API URL and response parsing |
| `bustimes/bustimes.py:85-107` | `save_to_s3()` | Current S3 write format |
| `combine_json.py` | JSON merge pattern | Simple but shows the combine concept |
