#!/usr/bin/env python3
"""
Convert raw bustimes S3 objects into weekly gzipped JSONL files.

Usage:
    # Local test
    python scripts/convert_bustimes.py --local-dir data/test_local --output-dir data/test_output

    # Specific weeks from S3 (public bucket, no credentials needed)
    python scripts/convert_bustimes.py --weeks 2018-W31,2021-W45 --output-dir data/output

    # All weeks from S3
    python scripts/convert_bustimes.py --all --output-dir data/output

    # Dry run (list files, don't convert)
    python scripts/convert_bustimes.py --all --dry-run --local-dir data/test_local
"""

import argparse
import ast
import datetime
import gzip
import json
import os
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Files at or before this key use Python repr format, not JSON
LAST_MALFORMED_KEY = "raw/bustimes__2021-11-10__07-15-05.json"

FILENAME_RE = re.compile(
    r"bustimes__(\d{4})-(\d{2})-(\d{2})__(\d{2})-(\d{2})-(\d{2})\.json$"
)

S3_BUCKET = "bustimes-data"
S3_PREFIX = "raw/"


def parse_filename_dt(key: str) -> datetime.datetime | None:
    """Extract UTC datetime from a bustimes S3 key or local filename."""
    m = FILENAME_RE.search(key)
    if not m:
        return None
    return datetime.datetime(
        *map(int, m.groups()), tzinfo=datetime.timezone.utc
    )


def iso_week_label(dt: datetime.datetime) -> str:
    """Return ISO week string like '2021-W45'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_to_dates(week_str: str) -> list[datetime.date]:
    """Return all 7 dates (Mon-Sun) for an ISO week like '2021-W45'."""
    # Monday of the ISO week
    monday = datetime.date.fromisoformat(week_str + "-1")
    return [monday + datetime.timedelta(days=i) for i in range(7)]


def is_malformed(key: str) -> bool:
    """Return True if the file uses Python repr format (pre-cutoff)."""
    return key <= LAST_MALFORMED_KEY


def parse_records(raw: str, key: str) -> list[dict]:
    """Parse a raw file body into a list of dicts."""
    if is_malformed(key):
        return ast.literal_eval(raw)
    else:
        return json.loads(raw)


# --- S3 client --------------------------------------------------------------

def make_s3_client(profile: str | None = None):
    """Create an S3 client, optionally using a named profile for auth."""
    import boto3

    if profile:
        session = boto3.Session(profile_name=profile)
        return session.client("s3")
    else:
        from botocore import UNSIGNED
        from botocore.config import Config

        return boto3.client("s3", config=Config(signature_version=UNSIGNED))


# --- File listing -----------------------------------------------------------

def list_local_files(local_dir: str) -> list[str]:
    """List all bustimes JSON files under local_dir/raw/."""
    raw_dir = os.path.join(local_dir, "raw")
    files = []
    for name in sorted(os.listdir(raw_dir)):
        if FILENAME_RE.search(name):
            files.append(os.path.join("raw", name))
    return files


def list_s3_keys_for_date(s3_client, date: datetime.date) -> list[str]:
    """List all bustimes keys for a single date (both raw/ and root-level)."""
    keys = []
    # Check both raw/ prefix and root-level (pre-raw era, Dec 2016)
    for prefix in [f"raw/bustimes__{date:%Y-%m-%d}", f"bustimes__{date:%Y-%m-%d}"]:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if FILENAME_RE.search(obj["Key"]):
                    keys.append(obj["Key"])
    return keys


def list_s3_keys_for_weeks(s3_client, week_strs: list[str]) -> dict[str, list[str]]:
    """List S3 keys for specific weeks, grouped by week. Uses parallel listing."""
    weeks: dict[str, list[str]] = {}
    # Gather all (week, date) pairs
    tasks = []
    for week_str in week_strs:
        for date in week_to_dates(week_str):
            tasks.append((week_str, date))

    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {
            pool.submit(list_s3_keys_for_date, s3_client, date): (week_str, date)
            for week_str, date in tasks
        }
        for future in as_completed(futures):
            week_str, date = futures[future]
            try:
                keys = future.result()
                weeks.setdefault(week_str, []).extend(keys)
            except Exception as e:
                print(f"  ERROR listing {date}: {e}", file=sys.stderr)

    # Sort keys within each week
    for week_str in weeks:
        weeks[week_str].sort()
    return dict(sorted(weeks.items()))


def list_s3_keys_all(s3_client) -> list[str]:
    """List ALL bustimes keys in the bucket (slow — 4.8M objects)."""
    keys = []
    # Scan both raw/ prefix and root-level (pre-raw era, Dec 2016)
    for prefix in [S3_PREFIX, "bustimes__"]:
        paginator = s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                if FILENAME_RE.search(obj["Key"]):
                    keys.append(obj["Key"])
            if len(keys) % 100000 == 0 and keys:
                print(f"  ...listed {len(keys)} keys so far", flush=True)
    return keys


# --- File reading -----------------------------------------------------------

def read_local_file(local_dir: str, key: str) -> str:
    path = os.path.join(local_dir, key)
    with open(path, "r") as f:
        return f.read()


def read_s3_file(s3_client, key: str) -> str:
    resp = s3_client.get_object(Bucket=S3_BUCKET, Key=key)
    return resp["Body"].read().decode("utf-8")


# --- Grouping ---------------------------------------------------------------

def group_by_week(keys: list[str]) -> dict[str, list[str]]:
    """Group S3 keys by ISO week label."""
    groups: dict[str, list[str]] = defaultdict(list)
    for key in keys:
        dt = parse_filename_dt(key)
        if dt:
            groups[iso_week_label(dt)].append(key)
    # Sort keys within each week
    for week in groups:
        groups[week].sort()
    return dict(sorted(groups.items()))


# --- Conversion -------------------------------------------------------------

def convert_week(
    week: str,
    keys: list[str],
    read_fn,
    output_dir: str,
    workers: int,
    validate: bool,
) -> dict:
    """Convert all files for one ISO week into a gzipped JSONL file.

    Returns a stats dict with counts.
    """
    output_path = os.path.join(output_dir, f"{week}.jsonl.gz")

    stats = {
        "week": week,
        "files": len(keys),
        "records": 0,
        "errors": 0,
        "error_keys": [],
        "output": output_path,
    }

    # Collect (key, raw_body) in parallel
    file_data: list[tuple[str, str]] = []
    done_count = 0
    total = len(keys)

    def fetch(key):
        return key, read_fn(key)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, key): key for key in keys}
        for future in as_completed(futures):
            key = futures[future]
            try:
                file_data.append(future.result())
            except Exception as e:
                stats["errors"] += 1
                stats["error_keys"].append(key)
                print(f"  ERROR reading {key}: {e}", file=sys.stderr)
            done_count += 1
            if done_count % 500 == 0 or done_count == total:
                print(f"\r    downloaded {done_count}/{total}", end="", flush=True)
        if total >= 500:
            print()  # newline after progress

    # Sort by key to maintain chronological order
    file_data.sort(key=lambda x: x[0])

    # Parse and write JSONL
    with gzip.open(output_path, "wt", encoding="utf-8") as gz:
        for key, raw in file_data:
            dt = parse_filename_dt(key)
            assert dt is not None, f"could not parse datetime from {key}"
            snapshot_time = dt.isoformat()
            try:
                records = parse_records(raw, key)
            except Exception as e:
                stats["errors"] += 1
                stats["error_keys"].append(key)
                print(f"  ERROR parsing {key}: {e}", file=sys.stderr)
                continue

            for record in records:
                record["snapshot_time"] = snapshot_time
                gz.write(json.dumps(record, separators=(",", ":")) + "\n")
                stats["records"] += 1

    if validate:
        # Re-read and verify each line is valid JSON
        count = 0
        with gzip.open(output_path, "rt", encoding="utf-8") as gz:
            for line_no, line in enumerate(gz, 1):
                try:
                    obj = json.loads(line)
                    assert "snapshot_time" in obj, f"missing snapshot_time on line {line_no}"
                    count += 1
                except (json.JSONDecodeError, AssertionError) as e:
                    print(f"  VALIDATE ERROR {output_path}:{line_no}: {e}", file=sys.stderr)
                    stats["errors"] += 1
        if count != stats["records"]:
            print(
                f"  VALIDATE MISMATCH: wrote {stats['records']} but read back {count}",
                file=sys.stderr,
            )
            stats["errors"] += 1

    return stats


# --- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert raw bustimes JSON files into weekly gzipped JSONL."
    )
    parser.add_argument(
        "--weeks",
        help="Comma-separated ISO weeks to convert (e.g. 2018-W31,2021-W45)",
    )
    parser.add_argument(
        "--all", action="store_true", dest="all_weeks",
        help="Convert all available weeks",
    )
    parser.add_argument(
        "--local-dir",
        help="Read from local directory instead of S3 (for testing)",
    )
    parser.add_argument(
        "--output-dir", default="v2",
        help="Output directory for JSONL.gz files (default: v2)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List files and weeks without converting",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Re-read output files to verify integrity",
    )
    parser.add_argument(
        "--workers", type=int, default=16,
        help="Thread pool size for downloads (default: 16)",
    )
    parser.add_argument(
        "--profile",
        help="AWS profile name for SSO/IAM auth (default: anonymous access)",
    )
    args = parser.parse_args()

    if not args.weeks and not args.all_weeks:
        parser.error("Specify --weeks or --all")

    # List source files and build week groups
    if args.local_dir:
        all_keys = list_local_files(args.local_dir)
        read_fn = lambda key: read_local_file(args.local_dir, key)
        weeks = group_by_week(all_keys)
        if args.weeks:
            requested = set(args.weeks.split(","))
            weeks = {w: keys for w, keys in weeks.items() if w in requested}
    elif args.weeks:
        # Targeted listing: only list S3 keys for the requested weeks
        s3_client = make_s3_client(args.profile)
        requested = args.weeks.split(",")
        print(f"Listing S3 keys for {len(requested)} weeks...", flush=True)
        weeks = list_s3_keys_for_weeks(s3_client, requested)
        read_fn = lambda key: read_s3_file(s3_client, key)
    else:
        # --all: list everything (slow)
        s3_client = make_s3_client(args.profile)
        print("Listing ALL S3 keys (this may take a while)...", flush=True)
        all_keys = list_s3_keys_all(s3_client)
        read_fn = lambda key: read_s3_file(s3_client, key)
        weeks = group_by_week(all_keys)

    total_files = sum(len(k) for k in weeks.values())
    print(f"Found {total_files} files across {len(weeks)} weeks")

    # Warn about missing weeks
    if args.weeks:
        requested_set = set(args.weeks.split(","))
        missing = requested_set - set(weeks.keys())
        if missing:
            print(f"Warning: no files found for weeks: {', '.join(sorted(missing))}")

    if args.dry_run:
        for week, keys in weeks.items():
            malformed = sum(1 for k in keys if is_malformed(k))
            valid = len(keys) - malformed
            print(f"  {week}: {len(keys)} files ({malformed} malformed, {valid} valid JSON)")
        print(f"\nTotal: {total_files} files in {len(weeks)} weeks")
        return

    # Create output dir
    os.makedirs(args.output_dir, exist_ok=True)

    # Convert each week
    total_stats = {"files": 0, "records": 0, "errors": 0, "skipped": 0}
    for week, keys in weeks.items():
        output_path = os.path.join(args.output_dir, f"{week}.jsonl.gz")
        if os.path.exists(output_path):
            print(f"  {week}: SKIP (output already exists)")
            total_stats["skipped"] += 1
            continue

        print(f"  {week}: converting {len(keys)} files...", end=" ", flush=True)
        stats = convert_week(week, keys, read_fn, args.output_dir, args.workers, args.validate)
        print(f"{stats['records']} records, {stats['errors']} errors")

        total_stats["files"] += stats["files"]
        total_stats["records"] += stats["records"]
        total_stats["errors"] += stats["errors"]

    print(f"\nDone: {total_stats['files']} files → {total_stats['records']} records, "
          f"{total_stats['errors']} errors, {total_stats['skipped']} skipped")


if __name__ == "__main__":
    main()
