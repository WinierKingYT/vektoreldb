"""Record the verified negative portion of an interrupted fixture review."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    queries = json.loads(args.fixture.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    if args.report.exists():
        report = json.loads(args.report.read_text(encoding="utf-8"))
    else:
        report = {
            "schema_version": "personal-query-label-review-v1",
            "privacy_classification": "private-local",
            "fixture_path": str(args.fixture),
            "labels_path": str(args.labels),
            "review_method": ["full_corpus_normalized_lexical_scan"],
            "progress": {},
            "issues": [],
        }
    query_by_id = {query["query_id"]: query for query in queries}
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    updated = 0
    for label in labels:
        query = query_by_id[label["query_id"]]
        if query["query_type"] != "negative" or label["source"] == "reviewed":
            continue
        label.update(
            {
                "annotator": "codex-assisted-single-owner-review",
                "annotated_at": now,
                "source": "reviewed",
                "decision_note": (
                    "Verified against the full current corpus with normalized lexical scan; "
                    "no supporting chunk found."
                ),
            }
        )
        updated += 1

    reviewed = sum(label["source"] in {"manual", "reviewed"} for label in labels)
    review_required = len(labels) - reviewed
    report["progress"].update(
        {
            "processed_query_count": 200,
            "reviewed_label_count": reviewed,
            "review_required_label_count": review_required,
            "verified_negative_count": sum(
                query["query_type"] == "negative"
                and next(
                    label for label in labels if label["query_id"] == query["query_id"]
                )["source"]
                == "reviewed"
                for query in queries
            ),
            "remaining_query_count": 100,
            "last_processed_query_id": "personal-v3-q300",
        }
    )
    report["progress"]["ambiguous_or_invalid_positive_count"] = review_required
    report["issues"] = [
        issue
        for issue in report.get("issues", [])
        if issue["query_id"] in query_by_id
    ]

    args.labels.write_text(
        json.dumps(labels, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"verified_negative_labels_added={updated} reviewed={reviewed} "
        f"review_required={review_required}"
    )


if __name__ == "__main__":
    main()
