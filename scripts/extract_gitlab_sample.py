#!/usr/bin/env python3
"""Extract a sample of GitLab projects from the GitLab Docker image.

The raw data source is a Docker image tar at:
    data_sources/gitlab/gitlab-populated-final-port8023.tar (~73 GB)

This image contains a GitLab CE instance with a PostgreSQL database.
You cannot read the database directly from the tar -- you must run the container.

Usage (one-time extraction):
    1. Load the Docker image:
       docker load < /scratch/general/vast/u1653932/data_sources/gitlab/gitlab-populated-final-port8023.tar

    2. Start the container (find the image name from `docker images`):
       docker run -d --name gitlab-extract -p 8023:8023 <IMAGE_NAME>

    3. Wait for GitLab to fully start (can take 2-5 minutes):
       docker logs -f gitlab-extract  # wait for "ready" message

    4. Use the GitLab API to dump projects:
       # Get an API token from the running instance, or use the root token
       # if one was pre-configured in the image.

       curl -s "http://localhost:8023/api/v4/projects?per_page=100&page=1" \\
           --header "PRIVATE-TOKEN: <TOKEN>" | python3 -m json.tool > /tmp/gitlab_page1.json

       # Repeat for additional pages if needed, or use the script below.

    5. Alternatively, dump directly from PostgreSQL:
       docker exec gitlab-extract gitlab-psql -c \\
           "COPY (SELECT p.id, p.name, p.description,
                   n.path AS namespace, p.visibility_level,
                   p.star_count, p.forks_count,
                   p.last_activity_at, p.creator_id
            FROM projects p
            LEFT JOIN namespaces n ON p.namespace_id = n.id
            ORDER BY p.star_count DESC
            LIMIT 500) TO STDOUT WITH (FORMAT csv, HEADER)" > /tmp/gitlab_projects.csv

    6. Convert to JSONL:
       python3 scripts/extract_gitlab_sample.py --convert \\
           --projects-csv /tmp/gitlab_projects.csv

       OR if you used the API:
       python3 scripts/extract_gitlab_sample.py --convert \\
           --projects-json /tmp/gitlab_page1.json

    7. Stop and remove the container:
       docker stop gitlab-extract && docker rm gitlab-extract

Output file:
    data_sources/gitlab/gitlab_sample.jsonl
"""
import argparse
import csv
import json
import pathlib
import sys

DATA_SOURCES = pathlib.Path("/scratch/general/vast/u1653932/data_sources")
OUTPUT_DIR = DATA_SOURCES / "gitlab"

# GitLab visibility levels: 0=private, 10=internal, 20=public
VISIBILITY_MAP = {"0": "private", "10": "internal", "20": "public"}


def convert_csv_to_jsonl(csv_path: str):
    """Convert a PostgreSQL CSV dump of projects to JSONL."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "gitlab_sample.jsonl"
    count = 0

    with open(csv_path) as f_in, open(output_path, "w") as f_out:
        reader = csv.DictReader(f_in)
        for row in reader:
            visibility_raw = row.get("visibility_level", "0")
            visibility = VISIBILITY_MAP.get(str(visibility_raw), "private")
            record = {
                "id": int(row.get("id", 0)),
                "name": row.get("name", ""),
                "description": row.get("description", "") or "",
                "namespace": row.get("namespace", ""),
                "visibility": visibility,
                "star_count": int(row.get("star_count", 0)),
                "forks_count": int(row.get("forks_count", 0)),
                "last_activity_at": row.get("last_activity_at", ""),
                "creator_id": row.get("creator_id", ""),
            }
            f_out.write(json.dumps(record) + "\n")
            count += 1

    print(f"Wrote {count} repos to {output_path}")


def convert_json_to_jsonl(json_path: str):
    """Convert GitLab API JSON response (array of projects) to JSONL."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "gitlab_sample.jsonl"

    with open(json_path) as f:
        projects = json.load(f)

    if not isinstance(projects, list):
        print("ERROR: Expected a JSON array of project objects", file=sys.stderr)
        sys.exit(1)

    count = 0
    with open(output_path, "w") as f_out:
        for proj in projects:
            record = {
                "id": proj.get("id", 0),
                "name": proj.get("name", proj.get("path", "")),
                "description": proj.get("description", "") or "",
                "namespace": proj.get("namespace", {}).get("full_path", ""),
                "visibility": proj.get("visibility", "private"),
                "star_count": proj.get("star_count", 0),
                "forks_count": proj.get("forks_count", 0),
                "last_activity_at": proj.get("last_activity_at", ""),
                "creator_id": proj.get("creator_id", ""),
                "default_branch": proj.get("default_branch", "main"),
            }
            f_out.write(json.dumps(record) + "\n")
            count += 1

    print(f"Wrote {count} repos to {output_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--convert", action="store_true",
                        help="Convert extracted data to JSONL")
    parser.add_argument("--projects-csv", type=str, default="",
                        help="Path to projects CSV dump (from psql)")
    parser.add_argument("--projects-json", type=str, default="",
                        help="Path to projects JSON (from GitLab API)")
    args = parser.parse_args()

    if args.convert:
        if args.projects_csv:
            convert_csv_to_jsonl(args.projects_csv)
        elif args.projects_json:
            convert_json_to_jsonl(args.projects_json)
        else:
            print("ERROR: Provide --projects-csv or --projects-json",
                  file=sys.stderr)
            sys.exit(1)
    else:
        print(__doc__)
        print("Run with --convert to convert extracted data to JSONL.")
        print("See the docstring above for full Docker extraction instructions.")


if __name__ == "__main__":
    main()
