#!/usr/bin/env python3
"""Extract a sample of Stack Exchange questions and answers from the 7z dump.

The raw data source is:
    data_sources/stackexchange/stackexchange_dump.7z (~65 GB)

This archive contains XML dumps including Posts.xml, Users.xml, Comments.xml,
Tags.xml, and Votes.xml. Questions have PostTypeId=1, answers PostTypeId=2.

Usage:
    python3 scripts/extract_stackexchange_sample.py

Requirements:
    pip install py7zr

This script:
    1. Opens the 7z archive and stream-extracts Posts.xml
    2. Uses iterparse to read XML rows without loading the entire file
    3. Collects up to 500 questions (PostTypeId=1) and their answers (PostTypeId=2)
    4. Writes JSONL output files

Output files:
    data_sources/stackexchange/questions_sample.jsonl
    data_sources/stackexchange/answers_sample.jsonl
"""
import argparse
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

DATA_SOURCES = pathlib.Path("/scratch/general/vast/u1653932/data_sources")
ARCHIVE_PATH = DATA_SOURCES / "stackexchange" / "stackexchange_dump.7z"
OUTPUT_DIR = DATA_SOURCES / "stackexchange"

MAX_QUESTIONS = 500
MAX_ANSWERS = 2000


def parse_tags(tags_str):
    """Parse '<python><asyncio><flask>' into ['python', 'asyncio', 'flask']."""
    if not tags_str:
        return []
    return re.findall(r'<([^>]+)>', tags_str)


def extract_from_7z():
    """Extract Posts.xml from the 7z archive and parse questions + answers."""
    try:
        import py7zr
    except ImportError:
        print("ERROR: py7zr is required. Install with: pip install py7zr",
              file=sys.stderr)
        sys.exit(1)

    if not ARCHIVE_PATH.exists():
        print(f"ERROR: Archive not found at {ARCHIVE_PATH}", file=sys.stderr)
        print("This script requires the Stack Exchange dump archive.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = []
    answers = []

    print(f"Opening {ARCHIVE_PATH}...")
    print("Looking for Posts.xml in the archive...")

    with py7zr.SevenZipFile(ARCHIVE_PATH, mode='r') as z:
        # Find Posts.xml in archive
        names = z.getnames()
        posts_files = [n for n in names if n.endswith('Posts.xml')]
        if not posts_files:
            print(f"ERROR: No Posts.xml found in archive. Files: {names[:20]}",
                  file=sys.stderr)
            sys.exit(1)

        print(f"Extracting {posts_files[0]}...")
        extracted = z.read(posts_files)

        for fname, bio in extracted.items():
            print(f"Parsing {fname}...")
            # Use iterparse to stream through XML rows
            context = ET.iterparse(bio, events=("end",))
            for event, elem in context:
                if elem.tag != "row":
                    continue
                post_type = elem.get("PostTypeId")
                if post_type == "1" and len(questions) < MAX_QUESTIONS:
                    # Question
                    questions.append({
                        "id": int(elem.get("Id", 0)),
                        "title": elem.get("Title", ""),
                        "body": (elem.get("Body", "") or "")[:500],
                        "tags": parse_tags(elem.get("Tags", "")),
                        "score": int(elem.get("Score", 0)),
                        "creation_date": elem.get("CreationDate", ""),
                        "answer_count": int(elem.get("AnswerCount", 0)),
                        "accepted_answer_id": elem.get("AcceptedAnswerId"),
                        "owner_id": elem.get("OwnerUserId"),
                    })
                elif post_type == "2" and len(answers) < MAX_ANSWERS:
                    # Answer
                    parent_id = elem.get("ParentId")
                    answers.append({
                        "id": int(elem.get("Id", 0)),
                        "question_id": int(parent_id) if parent_id else 0,
                        "body": (elem.get("Body", "") or "")[:500],
                        "score": int(elem.get("Score", 0)),
                        "creation_date": elem.get("CreationDate", ""),
                        "owner_id": elem.get("OwnerUserId"),
                        "is_accepted": False,  # Will be set below
                    })
                # Free memory
                elem.clear()

                if len(questions) >= MAX_QUESTIONS and len(answers) >= MAX_ANSWERS:
                    break

    # Mark accepted answers
    accepted_ids = {int(q["accepted_answer_id"])
                    for q in questions
                    if q.get("accepted_answer_id")}
    for a in answers:
        if a["id"] in accepted_ids:
            a["is_accepted"] = True

    # Write output
    q_path = OUTPUT_DIR / "questions_sample.jsonl"
    with open(q_path, "w") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")
    print(f"Wrote {len(questions)} questions to {q_path}")

    a_path = OUTPUT_DIR / "answers_sample.jsonl"
    with open(a_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")
    print(f"Wrote {len(answers)} answers to {a_path}")


def extract_from_xml(posts_xml_path: str):
    """Parse a pre-extracted Posts.xml file directly."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = []
    answers = []

    print(f"Parsing {posts_xml_path}...")
    context = ET.iterparse(posts_xml_path, events=("end",))
    for event, elem in context:
        if elem.tag != "row":
            continue
        post_type = elem.get("PostTypeId")
        if post_type == "1" and len(questions) < MAX_QUESTIONS:
            questions.append({
                "id": int(elem.get("Id", 0)),
                "title": elem.get("Title", ""),
                "body": (elem.get("Body", "") or "")[:500],
                "tags": parse_tags(elem.get("Tags", "")),
                "score": int(elem.get("Score", 0)),
                "creation_date": elem.get("CreationDate", ""),
                "answer_count": int(elem.get("AnswerCount", 0)),
                "accepted_answer_id": elem.get("AcceptedAnswerId"),
                "owner_id": elem.get("OwnerUserId"),
            })
        elif post_type == "2" and len(answers) < MAX_ANSWERS:
            parent_id = elem.get("ParentId")
            answers.append({
                "id": int(elem.get("Id", 0)),
                "question_id": int(parent_id) if parent_id else 0,
                "body": (elem.get("Body", "") or "")[:500],
                "score": int(elem.get("Score", 0)),
                "creation_date": elem.get("CreationDate", ""),
                "owner_id": elem.get("OwnerUserId"),
                "is_accepted": False,
            })
        elem.clear()
        if len(questions) >= MAX_QUESTIONS and len(answers) >= MAX_ANSWERS:
            break

    # Mark accepted answers
    accepted_ids = {int(q["accepted_answer_id"])
                    for q in questions
                    if q.get("accepted_answer_id")}
    for a in answers:
        if a["id"] in accepted_ids:
            a["is_accepted"] = True

    q_path = OUTPUT_DIR / "questions_sample.jsonl"
    with open(q_path, "w") as f:
        for q in questions:
            f.write(json.dumps(q) + "\n")
    print(f"Wrote {len(questions)} questions to {q_path}")

    a_path = OUTPUT_DIR / "answers_sample.jsonl"
    with open(a_path, "w") as f:
        for a in answers:
            f.write(json.dumps(a) + "\n")
    print(f"Wrote {len(answers)} answers to {a_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-xml", type=str, default="",
                        help="Path to a pre-extracted Posts.xml file (skip 7z extraction)")
    args = parser.parse_args()

    if args.from_xml:
        extract_from_xml(args.from_xml)
    else:
        extract_from_7z()


if __name__ == "__main__":
    main()
