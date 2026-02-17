# Plan: Compress, Fix JSON, and Combine S3 Data

## Context

The Lambda writes TriMet bus positions every minute to S3. The bucket has 4.84M objects totaling 909 GB, costing ~$21/month in storage. Files are uncompressed, and those created before 2021-11-10T07:16Z contain Python repr format (not valid JSON — `u'key'`, `None`, `True` instead of `"key"`, `null`, `true`). Gzip yields ~88% size reduction.

- **Last malformed file:** `raw/bustimes__2021-11-10__07-15-05.json`
- **First valid JSON file:** `raw/bustimes__2021-11-10__07-16-05.json`
- Existing `fix_malformed_json.py` has the `ast.literal_eval()` approach to reuse

## AWS Details (validated 2026-02-16)

| Item | Value |
|------|-------|
| Bucket | `bustimes-data` |
| Region | **us-east-1** (LocationConstraint: null) |
| Account | `144370233886` |
| IAM user | `michael` |
| CLI command | `aws2` (not `aws`) |
| CLI profile | `--profile michael` for bucket operations |
| Storage class | STANDARD (no lifecycle rules) |
| Versioning | Disabled |
| Access | Public READ via ACL (AllUsers READ grant) |

### Bucket contents

| Prefix | Count | Notes |
|--------|-------|-------|
| `raw/` | ~4.84M files | Main data, `.json` uncompressed |
| Root-level `bustimes__*` | 181 files | Dec 2016, before `raw/` prefix was added |
| `every_minute/` | 2 files | Dec 2016 test, negligible |
| `data_test/` | 4,971 files | `.json.gz` from May 2018 (previous compression experiment, all dated Aug 2018). Not handled by script (different extension). Can be deleted in cleanup. |
| `v2/` | Does not exist yet | Our target output prefix |

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

## Step 3: Full batch on EC2 in us-east-1

### Pre-flight checklist

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Bucket region confirmed | DONE | us-east-1 (LocationConstraint: null) |
| 2 | Write access profile confirmed | DONE | `--profile michael` (account `144370233886`). `mixedneeds` (`655926922222`) is read-only. |
| 3 | Root-level files handled | DONE | Script scans both `raw/` and `bustimes__` prefixes (line 150). 181 root files from Dec 2016. |
| 4 | Python repr parsing verified | DONE | 0 errors across 90,740 files spanning 2017-2025. |
| 5 | Compression ratio confirmed | DONE | Avg 180 MB/week compressed. ~91% reduction. |
| 6 | `is_malformed()` for root keys | DONE | Root keys `bustimes__*` < `raw/bustimes__*` alphabetically, so they get `ast.literal_eval()`. Correct. |
| 7 | Create IAM instance role | TODO | In account `144370233886`. Needs S3 access to `bustimes-data` + `AmazonSSMManagedInstanceCore` for remote commands. |
| 8 | Launch EC2 spot instance | TODO | Must be in us-east-1. |
| 9 | Smoke test on instance | TODO | Install deps, run 1 week, verify output, test s5cmd sync. See testing stages below. |
| 10 | No other consumers of `raw/` | DEFERRED | Only matters for Step 5 (delete originals). Lambda writes to `raw/` — new Lambda (Step 4) writes to `v2/`. |

### Instance setup

- **Region:** us-east-1 (same as bucket — zero data transfer cost)
- **Instance:** Start with t3.medium spot (~$0.01/hr), Amazon Linux 2023. Bump to c5.xlarge/2xlarge (~$0.03-0.07/hr spot) after smoke test if CPU-bound.
- **EBS:** 20 GB gp3 (process + upload incrementally, don't need full 85 GB)
- **Access:** SSM Session Manager (no SSH key needed) or SSH
- **Profile:** instance profile with S3 read/write to `bustimes-data`
- **CLI:** `aws2 --profile michael` locally; on EC2, use instance role

### Remote access

Commands sent via SSM from local machine (no SSH key needed):

```bash
aws2 --profile michael ssm send-command \
  --instance-ids $INSTANCE_ID --document-name "AWS-RunShellScript" \
  --parameters 'commands=["..."]' --region us-east-1

aws2 --profile michael ssm get-command-invocation \
  --command-id $CMD_ID --instance-id $INSTANCE_ID --region us-east-1
```

Instance IAM role needs `AmazonSSMManagedInstanceCore` + S3 access. Amazon Linux 2023 has SSM agent pre-installed.

For long-running commands: start with `nohup` or `tmux`, monitor via log files.

### Process

1. Launch spot instance with instance profile granting `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on `bustimes-data` + `AmazonSSMManagedInstanceCore`
2. Install Python 3, boto3, s5cmd
3. Copy `scripts/convert_bustimes.py` to instance (via `s5cmd` from a temp S3 location, or SSM `send-command` with inline script)
4. Smoke test (see testing stages below)
5. Start conversion in background — use `--weeks` with all 481 week labels (2016-W49 to 2026-W08) instead of `--all` to skip the slow full-bucket listing:
   ```bash
   python3 -c "
   import datetime
   d, weeks = datetime.date(2016,12,5), []
   while d <= datetime.date.today():
       iso = d.isocalendar()
       weeks.append(f'{iso[0]}-W{iso[1]:02d}')
       d += datetime.timedelta(days=7)
   print(','.join(sorted(set(weeks))))
   " | xargs -I{} python3 convert_bustimes.py --weeks {} --output-dir /home/ec2-user/v2/
   ```
6. Start sync + cleanup loop in background:
   ```bash
   while true; do
     s5cmd sync /home/ec2-user/v2/ s3://bustimes-data/v2/
     # Delete local files that have been synced (older than 10 min)
     find /home/ec2-user/v2/ -name '*.jsonl.gz' -mmin +10 -delete
     sleep 300
   done
   ```
   s5cmd sync is idempotent — if a sync takes longer than 300s, the next `sleep` just starts later. No overlap issues since the next invocation won't start until the previous one finishes. The `-mmin +10` cleanup ensures files are synced before deletion.
7. Resume-safe: script skips weeks with existing local output. If spot interrupted, re-launch, re-run — picks up where it left off.

### Testing stages

**Stage A: Instance health (immediately after launch)**
```
- Can SSM reach the instance?
- Python 3 + boto3 importable?
- s5cmd installed and can list bucket?
  s5cmd ls s3://bustimes-data/raw/bustimes__2025-02-10* | head -5
```

**Stage B: Single-week smoke test (before full run)**
```
- Run: convert_bustimes.py --weeks 2017-W01 --output-dir /home/ec2-user/v2/
- Verify output file exists and is reasonable size (~170 MB)
- Verify valid gzip: zcat 2017-W01.jsonl.gz | head -1 | python3 -m json.tool
- Verify snapshot_time present: zcat 2017-W01.jsonl.gz | head -1 | python3 -c "import sys,json; assert 'snapshot_time' in json.loads(sys.stdin.readline())"
- Test s5cmd sync: s5cmd sync /home/ec2-user/v2/ s3://bustimes-data/v2/
- Verify in S3: s5cmd ls s3://bustimes-data/v2/
- Test resume: re-run same --weeks, verify it prints SKIP
```

**Stage C: Monitor during full run (periodic checks)**
```
- Tail conversion log for errors
- Count local output files: ls v2/ | wc -l
- Check S3 sync progress: s5cmd ls s3://bustimes-data/v2/ | wc -l
- Check disk usage: df -h
- Check memory: free -m
```

**Stage D: Post-completion verification**
```
- Count v2/ files in S3 (expect ~480)
- Total size (expect ~85 GB)
- Spot-check 3 random weeks:
  - Download, decompress, verify JSON valid
  - Check record count is reasonable (~2.5M-3M per week)
  - Verify snapshot_time field present
- Compare first and last week dates to expected range (2016-W49 to current)
```

### Cost estimate

| Item | Estimate |
|------|----------|
| EC2 spot (t3.medium, ~24 hrs) | ~$0.25 |
| S3 GET requests (~4.84M) | ~$2.00 |
| S3 PUT requests (~480) | ~$0.01 |
| S3 LIST requests | ~$0.05 |
| EBS 20 GB gp3 (1 day) | ~$0.05 |
| Data transfer | $0 (same region) |
| **Total** | **~$2.30** |

### Risk mitigations

| Risk | Mitigation |
|------|-----------|
| Spot interruption | Resume support: skips weeks already uploaded to S3. At most loses 1 in-progress week (~10 min of work). |
| Large bill | No cross-region transfer. S3 API costs are fixed (~$2). EC2 spot caps at ~$0.04/hr. |
| Unusable data | Step 2 validated 0 errors across all format types. Script validates JSON on write. |
| Unfinished process | Incremental upload means partial runs still produce usable data. Re-run picks up where it left off. |
| Disk full | Upload + delete after each batch keeps disk under 5 GB. |
| Public access on v2/ | New objects inherit bucket ACL (public READ). Same as raw data — intentional. |

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
