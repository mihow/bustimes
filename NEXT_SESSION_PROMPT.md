# Next Session: Bustimes S3 Full Batch Conversion (Step 3)

## Context

TriMet bus position data in `s3://bustimes-data/raw/` (us-east-1): 4.84M files, 909 GB, ~$21/month storage. We're compressing + fixing format + combining into weekly JSONL.gz files under `v2/`.

## What's done (steps 1-2)

`scripts/convert_bustimes.py` is complete and validated. It:
- Lists S3 objects by week (parallel per-date listing)
- Downloads with thread pool (`--workers N`, default 16)
- Parses Python repr (pre-2021-11-10) via `ast.literal_eval()` or JSON (post-2021-11-10) via `json.loads()`
- Adds `snapshot_time` ISO 8601 field from filename timestamp
- Writes one `{YYYY}-W{WW}.jsonl.gz` per ISO week
- Resumes by skipping weeks with existing output files
- Has `--dry-run`, `--validate`, `--profile` (for SSO auth), `--local-dir` (for local testing)

Tested on stratified sample (one week from each year 2017-2025 plus the format transition week 2021-W45): **90,740 files, 25M records, 0 errors.** Avg 180 MB compressed per week. Extrapolated full run: ~480 weeks, ~85 GB total (91% reduction).

## What needs doing (step 3)

### 1. Add `--s3-output` to the script

The script currently writes `.jsonl.gz` to a local `--output-dir`. For the EC2 batch run, add a `--s3-output` flag that uploads each completed weekly file to S3 and deletes the local temp copy. This avoids filling the instance disk (a `t3.medium` only has 8 GB root volume).

Key changes to `scripts/convert_bustimes.py`:
- Add `--s3-output` arg (e.g. `s3://bustimes-data/v2/`)
- After `convert_week()` writes the local `.jsonl.gz`, upload it with `s3_client.upload_file()`
- Delete the local file after successful upload
- For resume: check if the S3 key already exists (HEAD object) before processing a week

**Important**: when `--s3-output` is used, the script needs an authenticated S3 client (not the anonymous one). On the EC2 instance the default boto3 session will use the instance IAM role automatically, so no `--profile` needed. But make sure the `make_s3_client()` path works without a profile AND without UNSIGNED config — just a plain `boto3.client("s3")`.

### 2. Launch EC2 spot instance

- **Instance type**: `t3.medium` (2 vCPU, 4 GB RAM) in **us-east-1** (same region as bucket — S3 transfer is free within region)
- **AMI**: Amazon Linux 2023 (has Python 3.9+ and pip pre-installed)
- **IAM role**: needs `s3:GetObject`, `s3:ListBucket` on `arn:aws:s3:::bustimes-data` and `arn:aws:s3:::bustimes-data/*`, plus `s3:PutObject` on `arn:aws:s3:::bustimes-data/v2/*`
- **Spot price**: ~$0.01/hr, set max at $0.02/hr
- **Security group**: SSH only (port 22 from your IP)
- **Key pair**: use existing or create new
- **User data** or manual setup after SSH:
  ```bash
  sudo yum install -y python3-pip tmux
  pip3 install --user boto3
  ```

### 3. Run the conversion

```bash
# SCP the script to the instance
scp -i key.pem scripts/convert_bustimes.py ec2-user@<ip>:~/

# SSH in, run in tmux
ssh -i key.pem ec2-user@<ip>
tmux new -s convert
python3 convert_bustimes.py --all --workers 32 --s3-output s3://bustimes-data/v2/
# Ctrl-B D to detach, reconnect with: tmux attach -t convert
```

- The `--all` flag first lists ALL 4.8M keys (slow, ~10-20 min for pagination), then processes week by week
- Expected: ~480 weeks, 4-6 hours total
- Cost: ~$0.05 compute + ~$4 S3 GET requests (~4.8M × $0.0004/1K) + $0 data transfer (same region)
- If spot is reclaimed, re-SSH and re-run — it resumes from the last incomplete week

### 4. Verify after completion

```bash
# Count output files (should be ~480)
aws s3 ls s3://bustimes-data/v2/ | wc -l

# Check total size
aws s3 ls s3://bustimes-data/v2/ --summarize --human-readable | tail -2

# Spot-check a few files
aws s3 cp s3://bustimes-data/v2/2018-W01.jsonl.gz - | zcat | head -1 | python3 -m json.tool
aws s3 cp s3://bustimes-data/v2/2023-W01.jsonl.gz - | zcat | wc -l  # should be ~250K-300K records
```

### 5. Clean up

- Terminate the spot instance
- Delete the IAM role/instance profile
- Delete the security group
- **Do NOT delete raw/ yet** — that's step 5 (after Athena validation)

## Pitfalls to avoid

- **Do NOT run `--all` from the local machine** — it downloads ~900 GB from S3 over the internet. That's ~$80 in data transfer and would take days. Must run from EC2 in us-east-1.
- **Do NOT use `--profile` on the EC2 instance** — it doesn't have SSO configured. The IAM instance role provides credentials automatically via the default boto3 credential chain.
- **The `--all` listing is slow** — listing 4.8M objects via `list_objects_v2` pagination takes 10-20 minutes. Don't think it's stuck. The script prints progress every 100K keys.
- **Memory**: each week downloads ~10K files into memory before writing. At ~200 KB per file, that's ~2 GB per week. A `t3.medium` with 4 GB RAM should handle this, but don't increase `--workers` above 32 or you may OOM.
- **Root-level files**: there may be `bustimes__*.json` files at the bucket root (no `raw/` prefix) from Dec 2016. The script already handles these — `list_s3_keys_all()` scans both `raw/` and `bustimes__` prefixes.
- **The `is_malformed()` check uses string comparison**: `key <= "raw/bustimes__2021-11-10__07-15-05.json"`. Root-level keys like `bustimes__2016-*` are always less than `raw/*` (since 'b' < 'r'), so they correctly get the `ast.literal_eval()` path.

## Key files

| File | What it does |
|---|---|
| `scripts/convert_bustimes.py` | All conversion logic — listing, downloading, parsing, writing, resume |
| `PLAN.md` | Full plan with step 2 validation results table |
| `CLAUDE.md` | Project overview for AI agents |

## Later steps (not this session)

- **Step 4**: New Lambda writing gzipped JSONL to `v2/` (existing Lambda stays untouched)
- **Step 5**: Create Athena table over `v2/`, validate queries match raw data, then delete `raw/` originals
