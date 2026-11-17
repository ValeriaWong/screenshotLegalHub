"""Export legacy screenshot cases without mutating source data or databases.

Example:
  python product_v1/tools/export_legacy_repository_cases.py --repo-root . --output reports/legacy-corpora.json
  Add --check-only to validate and print the prospective digest without writing.

Model transcripts/events retain their provenance and are not certified gold.
Quiz answers here are source task targets; private data/user_*.jsonl is never read.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.dont_write_bytecode = True
DB_REL = "blocks/retriever/artifacts/index.sqlite3"
ANNOTATION_REL = "projects/ScreenshotLegalBench_v2/process_local_evaluator/screenshot_legal_annotations (1).json"
GROUP_REL = "projects/quiz-collector/group_source.json"
MULTI_REL = "projects/quiz-collector/multi_choice_source.json"
CASE_NAME = re.compile(r"([0-9a-f]{24})_(?:image_\d+|cover)\.(?:jpg|png|jpeg)$", re.I)
IMAGE_NAME = re.compile(r"([0-9a-f]{24}_(?:image_\d+|cover)\.(?:jpg|png|jpeg))$", re.I)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(root: Path, relative: str):
    return json.loads(inside(root, relative).read_text(encoding="utf-8-sig"))


def inside(root: Path, relative: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Source path leaves repository: " + relative)
    return resolved


def basename(value: str) -> str:
    return str(value).replace(chr(92), "/").rsplit("/", 1)[-1]


def canonical_image(value: str) -> str:
    name = basename(value)
    match = IMAGE_NAME.search(name)
    return match.group(1) if match else name


def source_case_id(value: str) -> str | None:
    match = CASE_NAME.search(basename(value))
    return match.group(1) if match else None


def export(root: Path) -> dict:
    sys.path.insert(0, str(root))
    from legalhub.retrieval import validate_corpus

    connection = sqlite3.connect(inside(root, DB_REL).as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        images = [json.loads(row[0]) for row in connection.execute("SELECT body FROM images")]
        records = [json.loads(row[0]) for row in connection.execute(
            "SELECT body FROM records WHERE kind IN ('message','event')")]
    finally:
        connection.close()

    cases = {}
    for image in images:
        cases.setdefault(image["case_id"], {"images": [], "records": [], "metadata": {}})["images"].append(image)
    for record in records:
        if record["case_id"] not in cases:
            raise ValueError("Evidence record has no image case")
        cases[record["case_id"]]["records"].append(record)
    db_cases = len(cases)
    for case_id, corpus in cases.items():
        historical = bool(re.fullmatch(r"[0-9a-f]{24}", case_id))
        corpus["metadata"] = {
            "case_id": case_id, "source_db": DB_REL,
            "source_schema": "legacy images+records v1",
            "case_kind": "legacy_screenshot_case" if historical else "software_acceptance_test_upload",
            "professional_gold": False,
            "origin_counts": dict(Counter(row.get("origin_type", "unknown") for row in corpus["records"])),
        }

    # CaseRegistry's active vision pointer identifies one case, not one case per run.
    extra_cases = 0
    home = root / "blocks/evidence/artifacts/cases"
    if home.exists():
        for folder in sorted(home.iterdir()):
            if not (folder / "case.json").is_file():
                continue
            pointer = folder / "vision-active.json"
            if pointer.is_file():
                corpus_rel = json.loads(pointer.read_text(encoding="utf-8"))["corpus"]
            elif (folder / "vision/corpus.json").is_file():
                corpus_rel = (folder / "vision/corpus.json").relative_to(root).as_posix()
            else:
                continue
            corpus = read_json(root, corpus_rel)
            case_ids = {image["case_id"] for image in corpus["images"]}
            if len(case_ids) != 1:
                raise ValueError("Uploaded corpus contains multiple case IDs")
            case_id = next(iter(case_ids))
            if case_id in cases:
                if {image["sha256"] for image in corpus["images"]} != {image["sha256"] for image in cases[case_id]["images"]}:
                    raise ValueError("Uploaded case originals conflict with indexed case: " + case_id)
                continue
            corpus.setdefault("metadata", {}).update({
                "case_id": case_id, "source_corpus": corpus_rel,
                "case_kind": "legacy_uploaded_case", "professional_gold": False,
                "not_in_old_retriever": True,
            })
            cases[case_id] = corpus
            extra_cases += 1

    verified = 0
    for corpus in cases.values():
        validate_corpus(corpus)
        for image in corpus["images"]:
            actual = digest(inside(root, image["file"]).read_bytes())
            if actual != image["sha256"]:
                raise ValueError("Image SHA256 mismatch: " + image["file"])
            verified += 1

    annotations = read_json(root, ANNOTATION_REL)
    groups = read_json(root, GROUP_REL)
    multi = read_json(root, MULTI_REL)
    if [row["id"] for row in groups] != [row["id"] for row in multi]:
        raise ValueError("Group and multiple-choice IDs differ")
    source_hashes = {relative: digest(inside(root, relative).read_bytes())
                     for relative in (ANNOTATION_REL, GROUP_REL, MULTI_REL)}
    indexed = {}
    for image in images:
        indexed.setdefault(canonical_image(image["file"]), []).append(image)
    coverage = {
        "single_annotation_rows": len(annotations),
        "single_canonical_images": len({canonical_image(row["fileName"]) for row in annotations}),
        "single_case_groups": len({source_case_id(row["fileName"]) for row in annotations}),
        "grouped_tasks": len(groups),
        "grouped_canonical_images": len({canonical_image(name) for row in groups for name in row["image"]}),
        "missing_file_ids": [], "missing_case_ids": [], "sha_mismatches": [],
        "matched_sha_rows": 0,
    }
    for row in annotations:
        name = basename(row["fileName"])
        key = canonical_image(name)
        sha = digest(inside(root, "projects/quiz-collector/images/" + name).read_bytes())
        targets = indexed.get(key, [])
        if not targets:
            coverage["missing_file_ids"].append({"file_name": name, "canonical_file_id": key, "sha256": sha})
        elif not any(image["sha256"] == sha for image in targets):
            coverage["sha_mismatches"].append({"file_name": name, "canonical_file_id": key,
                "sha256": sha, "old_hashes": [image["sha256"] for image in targets]})
        else:
            coverage["matched_sha_rows"] += 1
        case_id = source_case_id(name)
        if case_id not in cases:
            coverage["missing_case_ids"].append(case_id)
    coverage["missing_case_ids"] = sorted(set(coverage["missing_case_ids"]))
    coverage["grouped_missing"] = []
    for group in groups:
        for name in group["image"]:
            if canonical_image(name) not in indexed or source_case_id(name) not in cases:
                coverage["grouped_missing"].append({"group_task_id": group["id"],
                    "file_name": basename(name), "case_id": source_case_id(name)})
    if any(coverage[key] for key in ("missing_file_ids", "missing_case_ids", "sha_mismatches", "grouped_missing")):
        raise ValueError("Quiz source coverage changed; inspect differences before importing: " +
                         json.dumps(coverage, ensure_ascii=True))

    for case_id, corpus in cases.items():
        if corpus["metadata"]["case_kind"] != "legacy_screenshot_case":
            continue
        indices = [i for i, row in enumerate(annotations) if source_case_id(row["fileName"]) == case_id]
        corpus["metadata"]["historical_annotation_sources"] = [{
            "path": ANNOTATION_REL, "sha256": source_hashes[ANNOTATION_REL],
            "row_indices": indices, "status": "historical_annotation_version_not_certified_here",
        }]
        group_indices = [i for i, row in enumerate(groups)
                         if any(source_case_id(name) == case_id for name in row["image"])]
        if group_indices:
            corpus["metadata"]["historical_quiz_tasks"] = {
                "group_source": {"path": GROUP_REL, "sha256": source_hashes[GROUP_REL],
                    "records": [{"source_index": i, **groups[i]} for i in group_indices]},
                "multi_choice_source": {"path": MULTI_REL, "sha256": source_hashes[MULTI_REL],
                    "records": [{"source_index": i, **multi[i]} for i in group_indices]},
                "status": "historical_task_targets_and_generated_distractors_not_new_cases_or_certified_gold",
            }

    return {
        "schema_version": "legacy-admin-case-corpora/1", "cases": cases, "validation_errors": [],
        "summary": {"cases": len(cases), "legacy_db_cases": db_cases, "extra_uploaded_cases": extra_cases,
            "images": sum(len(corpus["images"]) for corpus in cases.values()),
            "messages": sum(row["kind"] == "message" for corpus in cases.values() for row in corpus["records"]),
            "events": sum(row["kind"] == "event" for corpus in cases.values() for row in corpus["records"]),
            "image_hashes_verified": verified, "image_hash_mismatches": []},
        "quiz_coverage": coverage,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true", help="Validate and hash export without writing")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    corpus = export(root)
    payload = json.dumps(corpus, ensure_ascii=False, indent=2).encode("utf-8")
    if not args.check_only:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(payload)
    print(json.dumps({"output": str(args.output), "written": not args.check_only,
        "sha256": digest(payload), "bytes": len(payload), **corpus["summary"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
