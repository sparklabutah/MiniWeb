#!/usr/bin/env python3
"""Extract a sample of Reddit posts and comments from the Postmill Docker image.

The raw data source is a Docker image tar at:
    data_sources/reddit/postmill-populated-exposed-withimg.tar (~50 GB)

This image contains a PostgreSQL database with the Postmill Reddit clone data.
You cannot read the database directly from the tar -- you must run the container.

Usage (one-time extraction):
    1. Load the Docker image:
       docker load < /scratch/general/vast/u1653932/data_sources/reddit/postmill-populated-exposed-withimg.tar

    2. Start the container (find the image name from `docker images`):
       docker run -d --name postmill-extract <IMAGE_NAME>

    3. Wait for PostgreSQL to start, then dump submissions and comments:
       docker exec postmill-extract psql -U postmill -d postmill -c \\
           "COPY (SELECT id, title, body, \"user\".username AS author,
                   forum.name AS subreddit, submission.upvotes - submission.downvotes AS score,
                   submission.timestamp AS created_utc, submission.comment_count AS num_comments
            FROM submission
            JOIN \"user\" ON submission.user_id = \"user\".id
            JOIN forum ON submission.forum_id = forum.id
            ORDER BY submission.upvotes - submission.downvotes DESC
            LIMIT 500) TO STDOUT WITH (FORMAT csv, HEADER)" > /tmp/reddit_posts.csv

       docker exec postmill-extract psql -U postmill -d postmill -c \\
           "COPY (SELECT c.id, c.submission_id AS post_id, c.body,
                   \"user\".username AS author,
                   c.upvotes - c.downvotes AS score,
                   c.timestamp AS created_utc, c.parent_id AS parent_comment_id
            FROM comment c
            JOIN \"user\" ON c.user_id = \"user\".id
            ORDER BY c.upvotes - c.downvotes DESC
            LIMIT 1000) TO STDOUT WITH (FORMAT csv, HEADER)" > /tmp/reddit_comments.csv

    4. Convert CSV to JSONL:
       python3 scripts/extract_reddit_sample.py --convert \\
           --posts-csv /tmp/reddit_posts.csv \\
           --comments-csv /tmp/reddit_comments.csv

    5. Stop and remove the container:
       docker stop postmill-extract && docker rm postmill-extract

Output files:
    data_sources/reddit/reddit_sample.jsonl
    data_sources/reddit/comments_sample.jsonl
"""
import argparse
import csv
import json
import pathlib
import sys

DATA_SOURCES = pathlib.Path("/scratch/general/vast/u1653932/data_sources")
OUTPUT_DIR = DATA_SOURCES / "reddit"


def convert_csv_to_jsonl(posts_csv: str, comments_csv: str):
    """Convert extracted CSV dumps to JSONL format."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if posts_csv:
        posts_out = OUTPUT_DIR / "reddit_sample.jsonl"
        count = 0
        with open(posts_csv) as f_in, open(posts_out, "w") as f_out:
            reader = csv.DictReader(f_in)
            for row in reader:
                record = {
                    "id": row.get("id", ""),
                    "title": row.get("title", ""),
                    "body": row.get("body", ""),
                    "author": row.get("author", ""),
                    "subreddit": row.get("subreddit", ""),
                    "score": int(row.get("score", 0)),
                    "created_utc": row.get("created_utc", ""),
                    "num_comments": int(row.get("num_comments", 0)),
                }
                f_out.write(json.dumps(record) + "\n")
                count += 1
        print(f"Wrote {count} posts to {posts_out}")

    if comments_csv:
        comments_out = OUTPUT_DIR / "comments_sample.jsonl"
        count = 0
        with open(comments_csv) as f_in, open(comments_out, "w") as f_out:
            reader = csv.DictReader(f_in)
            for row in reader:
                record = {
                    "id": row.get("id", ""),
                    "post_id": row.get("post_id", ""),
                    "body": row.get("body", ""),
                    "author": row.get("author", ""),
                    "score": int(row.get("score", 0)),
                    "created_utc": row.get("created_utc", ""),
                    "parent_comment_id": row.get("parent_comment_id") or None,
                }
                f_out.write(json.dumps(record) + "\n")
                count += 1
        print(f"Wrote {count} comments to {comments_out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--convert", action="store_true",
                        help="Convert CSV dumps to JSONL")
    parser.add_argument("--posts-csv", type=str, default="",
                        help="Path to posts CSV dump")
    parser.add_argument("--comments-csv", type=str, default="",
                        help="Path to comments CSV dump")
    args = parser.parse_args()

    if args.convert:
        if not args.posts_csv and not args.comments_csv:
            print("ERROR: Provide --posts-csv and/or --comments-csv", file=sys.stderr)
            sys.exit(1)
        convert_csv_to_jsonl(args.posts_csv, args.comments_csv)
    else:
        print(__doc__)
        print("Run with --convert to convert CSV dumps to JSONL.")
        print("See the docstring above for full Docker extraction instructions.")


if __name__ == "__main__":
    main()
