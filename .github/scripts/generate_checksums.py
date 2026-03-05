#!/usr/bin/env python3
"""Generate SHA-256 checksums for all dataset files."""

import hashlib
import json
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    repo_root = Path(__file__).resolve().parent.parent.parent
    dataset_files = sorted(repo_root.glob("cqr_*.json"))

    checksums = {}
    for f in dataset_files:
        sha = compute_sha256(f)
        size = f.stat().st_size
        checksums[f.name] = {"sha256": sha, "size_bytes": size}
        print(f"{sha}  {f.name}  ({size:,} bytes)")

    checksum_file = repo_root / "checksums.json"
    with open(checksum_file, "w") as out:
        json.dump(checksums, out, indent=2)
        out.write("\n")

    print(f"\nChecksums written to {checksum_file}")


if __name__ == "__main__":
    main()
