"""Promote a fully reviewed local fixture manifest to ready."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--embedding-manifest-id", required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    if not coverage.get("coverage_complete"):
        raise ValueError("fixture coverage is incomplete")
    if not labels or any(label["source"] not in {"manual", "reviewed"} for label in labels):
        raise ValueError("every label must be manual or reviewed")
    if coverage.get("review_required_label_count", 0) != 0:
        raise ValueError("coverage still reports review-required labels")
    manifest["status"] = "ready"
    manifest["embedding_manifest_id"] = args.embedding_manifest_id
    manifest["notes"] = (
        "Corpus-bound fixture with single-owner reviewed labels; private-local "
        "and ready for acceptance validation."
    )
    args.manifest.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"manifest_status={manifest['status']} label_count={len(labels)}")


if __name__ == "__main__":
    main()
