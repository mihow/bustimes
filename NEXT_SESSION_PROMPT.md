# Next Session: Bustimes S3 Full Batch Conversion (Step 3)

## Context

TriMet bus position data in `s3://bustimes-data` (us-east-1, account `144370233886`): 4.84M files, 909 GB, ~$21/month storage. Compressing + fixing format + combining into weekly JSONL.gz files under `v2/`.

## What's done (steps 1-2)

`scripts/convert_bustimes.py` is complete and validated. It:
- Lists S3 objects by week (parallel per-date listing, 16 threads)
- Downloads with thread pool (`--workers N`, default 16)
- Parses Python repr (pre-2021-11-10) via `ast.literal_eval()` or JSON (post-2021-11-10) via `json.loads()`
- Adds `snapshot_time` ISO 8601 field from filename timestamp
- Writes one `{YYYY}-W{WW}.jsonl.gz` per ISO week (atomic: writes to `.tmp`, renames on completion)
- Gzip level 6 (fast, nearly same compression as level 9)
- Resumes by skipping weeks with existing output files
- `--max-errors N` (default 100) aborts if too many errors
- Per-week timing and running ETA printed during conversion
- Has `--dry-run`, `--validate`, `--profile`, `--local-dir`

Tested on 9 stratified sample weeks (2017-2025 plus format transition week): **90,740 files, 25M records, 0 errors.** Avg 180 MB compressed per week. Full run: ~481 weeks, ~85 GB total (91% reduction).

## AWS details

| Item | Value |
|------|-------|
| Bucket | `bustimes-data` |
| Region | **us-east-1** |
| Account | `144370233886` |
| CLI | `aws2 --profile michael` |
| Bucket access | Public READ ACL. `michael` profile has write. `mixedneeds` profile is read-only. |
| Storage | STANDARD, no versioning, no lifecycle |

## What needs doing (step 3)

### 1. Create IAM instance role

In account `144370233886`:
- Role name: e.g. `bustimes-conversion`
- Trust: EC2 service
- Policies:
  - `AmazonSSMManagedInstanceCore` (for remote command execution)
  - Custom inline policy for S3:
    ```json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Action": ["s3:GetObject", "s3:ListBucket"],
          "Resource": ["arn:aws:s3:::bustimes-data", "arn:aws:s3:::bustimes-data/*"]
        },
        {
          "Effect": "Allow",
          "Action": "s3:PutObject",
          "Resource": "arn:aws:s3:::bustimes-data/v2/*"
        }
      ]
    }
    ```
- Create instance profile, attach role

### 2. Launch EC2 spot instance

- **Region**: us-east-1 (same as bucket, zero data transfer cost)
- **AMI**: Amazon Linux 2023
- **Instance type**: Start with t3.medium (~$0.01/hr spot). Bump to c5.xlarge/2xlarge after smoke test if CPU-bound.
- **EBS**: 20 GB gp3 (sync + cleanup keeps disk usage low)
- **IAM instance profile**: `bustimes-conversion`
- **No SSH needed** — use SSM for remote commands

### 3. Set up instance (via SSM send-command)

```bash
# Send commands from local machine:
aws2 --profile michael ssm send-command \
  --instance-ids $INSTANCE_ID --document-name "AWS-RunShellScript" \
  --parameters 'commands=["..."]' --region us-east-1

# Get output:
aws2 --profile michael ssm get-command-invocation \
  --command-id $CMD_ID --instance-id $INSTANCE_ID --region us-east-1
```

Setup commands to send:
```bash
sudo dnf install -y python3-pip tmux
pip3 install --user boto3

# Install s5cmd
curl -sL https://github.com/peak/s5cmd/releases/latest/download/s5cmd_2.2.2_Linux-64bit.tar.gz | sudo tar xz -C /usr/local/bin

# Verify
python3 -c "import boto3; print('boto3 OK')"
s5cmd ls s3://bustimes-data/raw/bustimes__2025-02-10* | head -3
```

### 4. Smoke test (one week)

```bash
# Copy script to instance (via SSM heredoc or s5cmd from a temp location)

# Run one week
python3 convert_bustimes.py --weeks 2017-W01 --output-dir /home/ec2-user/v2/ --validate

# Check:
# - Timing (how many seconds?)
# - Output file size (~170 MB expected)
# - Valid gzip: zcat v2/2017-W01.jsonl.gz | head -1 | python3 -m json.tool
# - snapshot_time present
# - Test sync: s5cmd sync /home/ec2-user/v2/ s3://bustimes-data/v2/
# - Verify in S3: s5cmd ls s3://bustimes-data/v2/
# - Test resume: re-run, should print SKIP
# - Check memory: free -m
```

Use the per-week time to estimate full run. Decide whether to bump instance type.

### 5. Full conversion run

Generate all 481 week labels and run:
```bash
WEEKS=$(python3 -c "
import datetime
d, weeks = datetime.date(2016,12,5), set()
while d <= datetime.date.today():
    iso = d.isocalendar()
    weeks.add(f'{iso[0]}-W{iso[1]:02d}')
    d += datetime.timedelta(days=7)
print(','.join(sorted(weeks)))
")

# Run in tmux (or nohup with log file for SSM)
nohup python3 convert_bustimes.py --weeks $WEEKS --output-dir /home/ec2-user/v2/ \
  > /home/ec2-user/convert.log 2>&1 &
```

Sync + cleanup loop (separate background process):
```bash
nohup bash -c 'while true; do
  s5cmd sync /home/ec2-user/v2/ s3://bustimes-data/v2/
  find /home/ec2-user/v2/ -name "*.jsonl.gz" -mmin +10 -delete
  sleep 300
done' > /home/ec2-user/sync.log 2>&1 &
```

Monitor via SSM:
```bash
tail -20 /home/ec2-user/convert.log   # conversion progress + ETA
tail -5 /home/ec2-user/sync.log       # sync status
ls /home/ec2-user/v2/ | wc -l         # local files pending sync
s5cmd ls s3://bustimes-data/v2/ | wc -l  # files uploaded to S3
df -h                                  # disk usage
free -m                                # memory
```

### 6. Post-completion verification

```bash
# Count output files (expect ~481, some weeks may have no data)
s5cmd ls s3://bustimes-data/v2/ | wc -l

# Total size (expect ~85 GB)
s5cmd ls s3://bustimes-data/v2/ | awk '{sum+=$1} END {printf "%.1f GB\n", sum/1024/1024/1024}'

# Spot-check random weeks
s5cmd cat s3://bustimes-data/v2/2018-W01.jsonl.gz | zcat | head -1 | python3 -m json.tool
s5cmd cat s3://bustimes-data/v2/2023-W01.jsonl.gz | zcat | wc -l

# Verify first and last weeks match expected range
s5cmd ls s3://bustimes-data/v2/ | head -1   # expect 2016-W49
s5cmd ls s3://bustimes-data/v2/ | tail -1   # expect current week
```

### 7. Clean up

- Terminate the spot instance
- Delete the IAM role/instance profile
- **Do NOT delete raw/ yet** — that's step 5 (after Athena validation)

## Pitfalls

- **Do NOT run from local machine** — downloading ~900 GB over internet costs ~$80 in data transfer
- **Do NOT use `--profile` on EC2** — instance role provides credentials automatically
- **Do NOT use `--all`** — slow full-bucket listing. Use `--weeks` with all labels
- **SSM output truncation** — SSM caps output at 24K chars. Use `nohup` + log files, read via `tail`
- **Memory** — each week loads ~10K files (~2 GB) into memory. t3.medium (4 GB) is tight. If OOM, use t3.large (8 GB, ~$0.02/hr spot)
- **`is_malformed()` for root keys** — root keys `bustimes__*` < `raw/bustimes__*` alphabetically, so they correctly get `ast.literal_eval()`. Verified in sample test.

## Key files

| File | Purpose |
|---|---|
| `scripts/convert_bustimes.py` | Conversion script |
| `PLAN.md` | Full plan with validation results and cost estimates |
| `CLAUDE.md` | Project overview + AWS details |
