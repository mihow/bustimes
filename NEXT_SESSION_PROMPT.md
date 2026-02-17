# Next Session: Bustimes S3 Batch Conversion (Step 3)

## What's done

- `scripts/convert_bustimes.py` — conversion script, tested on 9 stratified sample weeks (90K files, 25M records, 0 errors)
- `PLAN.md` — full migration plan with step 2 results
- `CLAUDE.md` — project context for AI agents

## Next: Run full batch on EC2 spot (Step 3)

The conversion script needs to process all ~4.8M files from `s3://bustimes-data/raw/` into weekly JSONL.gz files under `s3://bustimes-data/v2/`. Running from an EC2 spot instance in us-east-1 avoids data transfer costs and gives fast S3 access.

### Tasks

1. **Launch spot instance**: `t3.medium` in us-east-1, attach IAM role with `s3:GetObject`, `s3:PutObject`, `s3:ListBucket` on `bustimes-data`. Use Amazon Linux 2023 AMI.

2. **Add S3 output support to script**: Currently writes to local disk. Add `--s3-output s3://bustimes-data/v2/` flag to upload each completed `.jsonl.gz` directly to S3 (avoids filling instance disk). Use `s3_client.upload_file()` after writing to a temp file.

3. **Run the conversion**:
   ```bash
   # On the EC2 instance
   pip3 install boto3
   tmux new -s convert
   python3 convert_bustimes.py --all --workers 32 --s3-output s3://bustimes-data/v2/
   ```
   - Expected: ~480 weeks, 4-6 hours, ~$0.05 compute + ~$4 S3 API
   - Script resumes automatically (skips weeks with existing output in v2/)
   - If spot reclaimed, just re-run — it picks up where it left off

4. **Verify**: After completion, spot-check a few weeks:
   ```bash
   aws s3 ls s3://bustimes-data/v2/ | wc -l     # should be ~480
   aws s3 cp s3://bustimes-data/v2/2020-W01.jsonl.gz - | zcat | head -1 | python3 -m json.tool
   ```

### Key files

| File | Purpose |
|---|---|
| `scripts/convert_bustimes.py` | Conversion script (all logic here) |
| `PLAN.md` | Full plan with step 2 validation results |
| `CLAUDE.md` | Project context |

### Later steps (not this session)

- **Step 4**: New Lambda writing gzipped JSONL to v2/ (replace current Lambda)
- **Step 5**: Athena table over v2/, validate queries, delete raw/ originals
