#!/usr/bin/env python3
"""Validate CQR dataset JSON files for structural integrity and consistency."""

import json
import sys
import hashlib
from pathlib import Path


EXPECTED_FILES = {
    "cqr_kvret_train_public.json": {
        "min_records": 2000,
        "description": "Training split",
    },
    "cqr_kvret_dev_public.json": {
        "min_records": 200,
        "description": "Development/validation split",
    },
    "cqr_kvret_test_public.json": {
        "min_records": 200,
        "description": "Test split",
    },
}

REQUIRED_REFORMULATION_KEYS = {
    "base_utt_idx",
    "flag",
    "gold_slots",
    "reformulated_utt",
}


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_record(record: dict, idx: int, filename: str) -> list[str]:
    """Validate a single dialogue record."""
    errors = []

    if "reformulation" in record:
        reform = record["reformulation"]
        if isinstance(reform, dict):
            missing = REQUIRED_REFORMULATION_KEYS - set(reform.keys())
            if missing:
                errors.append(
                    f"{filename}: record {idx} reformulation missing keys: {missing}"
                )
        elif isinstance(reform, list):
            for j, r in enumerate(reform):
                if isinstance(r, dict):
                    missing = REQUIRED_REFORMULATION_KEYS - set(r.keys())
                    if missing:
                        errors.append(
                            f"{filename}: record {idx} reformulation[{j}] missing keys: {missing}"
                        )

    return errors


def validate_file(filepath: Path, spec: dict) -> tuple[bool, list[str], dict]:
    """Validate a single JSON dataset file."""
    errors = []
    stats = {"file": filepath.name, "sha256": compute_sha256(filepath)}

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"{filepath.name}: Invalid JSON - {e}")
        return False, errors, stats

    if isinstance(data, list):
        stats["record_count"] = len(data)
        if len(data) < spec["min_records"]:
            errors.append(
                f"{filepath.name}: Expected >= {spec['min_records']} records, got {len(data)}"
            )
        for idx, record in enumerate(data):
            errors.extend(validate_record(record, idx, filepath.name))
    elif isinstance(data, dict):
        stats["top_level_keys"] = list(data.keys())[:10]
        stats["record_count"] = len(data)
    else:
        errors.append(f"{filepath.name}: Unexpected top-level type: {type(data).__name__}")

    return len(errors) == 0, errors, stats


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    all_errors = []
    all_stats = []
    files_checked = 0

    print("=" * 60)
    print("CQR Dataset Validation Report")
    print("=" * 60)

    for filename, spec in EXPECTED_FILES.items():
        filepath = repo_root / filename
        if not filepath.exists():
            all_errors.append(f"MISSING: {filename} ({spec['description']})")
            continue

        files_checked += 1
        size_mb = filepath.stat().st_size / (1024 * 1024)
        print(f"\nValidating {filename} ({size_mb:.1f} MB) ...")

        ok, errors, stats = validate_file(filepath, spec)
        stats["size_mb"] = round(size_mb, 2)
        all_stats.append(stats)
        all_errors.extend(errors)

        status = "PASS" if ok else "FAIL"
        print(f"  Status: {status}")
        print(f"  Records: {stats.get('record_count', 'N/A')}")
        print(f"  SHA-256: {stats['sha256'][:16]}...")

    print("\n" + "=" * 60)
    print(f"Files checked: {files_checked}/{len(EXPECTED_FILES)}")

    if all_errors:
        print(f"\nERRORS ({len(all_errors)}):")
        for err in all_errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\nAll validations passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
