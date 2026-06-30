# Extracting Data from Docker Images on CHPC Compute Nodes

**NEVER run these on the login node (granite1).** The wiki ZIM is 89 GB and the
GitLab tar is 73 GB — loading/extracting them on a shared login node will OOM
and kill your session.

---

## 1. Allocate a compute node

```bash
# Option A: general partition (32 GB, 4 hours, 8 cores)
salloc -n 8 --mem=32G --time=4:00:00 -A kmarino -p granite

# Option B: your group's nodes (more RAM available, less contention)
salloc -n 8 --mem=32G --time=4:00:00 -A kmarino -p kmarino-gpu-grn
```

Once allocated, you'll land on the compute node automatically.
Verify with `hostname` — it should NOT say `granite1`.

---

## 2. Set up the environment (run once after landing on compute node)

```bash
# Load conda and activate your env
source /scratch/general/vast/u1653932/miniforge3/etc/profile.d/conda.sh
conda activate miniweb-eval

# Load udocker
module load udocker/1.3.10

# Point udocker storage to vast (NOT home — home is only 50 GB)
export UDOCKER_DIR=/scratch/general/vast/u1653932/.udocker

# Set working directory
cd /scratch/general/vast/u1653932/projects/MiniWeb
```

---

## 3a. GitLab extraction

### Step 1: Load the docker image into udocker

```bash
udocker load -i /scratch/general/vast/u1653932/data_sources/gitlab/gitlab-populated-final-port8023.tar
```

This takes 10-20 minutes (streams 73 GB tar, extracts 74 GB of layers to
`$UDOCKER_DIR`). Disk usage: ~74 GB in `$UDOCKER_DIR/layers/`.

Check the loaded image name:
```bash
udocker images
```

### Step 2: Create a container

```bash
udocker create --name=gitlab-extract <IMAGE_NAME_FROM_ABOVE>
```

### Step 3: Extract data via PostgreSQL (no need to start full GitLab)

The fastest approach — talk to PostgreSQL directly, skip the web UI:

```bash
# Dump projects
udocker run gitlab-extract gitlab-psql -c \
    "COPY (SELECT p.id, p.name, p.description,
            n.path AS namespace, p.visibility_level,
            p.star_count, p.forks_count,
            p.last_activity_at, p.creator_id
     FROM projects p
     LEFT JOIN namespaces n ON p.namespace_id = n.id
     ORDER BY p.star_count DESC
     LIMIT 500) TO STDOUT WITH (FORMAT csv, HEADER)" \
    > /scratch/general/vast/u1653932/data_sources/gitlab/gitlab_projects.csv
```

If `gitlab-psql` needs GitLab services running first:
```bash
# Start GitLab services inside the container (wait 2-5 min)
udocker run gitlab-extract gitlab-ctl start postgresql

# Then run the psql query above
udocker run gitlab-extract gitlab-psql -c "..."
```

To also dump issues, merge requests, users, etc.:
```bash
# Issues
udocker run gitlab-extract gitlab-psql -c \
    "COPY (SELECT i.id, i.title, i.description, i.state_id,
            i.author_id, p.name AS project_name,
            i.created_at, i.updated_at
     FROM issues i
     JOIN projects p ON i.project_id = p.id
     ORDER BY i.created_at DESC
     LIMIT 2000) TO STDOUT WITH (FORMAT csv, HEADER)" \
    > /scratch/general/vast/u1653932/data_sources/gitlab/gitlab_issues.csv

# Merge requests
udocker run gitlab-extract gitlab-psql -c \
    "COPY (SELECT mr.id, mr.title, mr.description, mr.state_id,
            mr.author_id, p.name AS project_name,
            mr.source_branch, mr.target_branch,
            mr.created_at, mr.merged_at
     FROM merge_requests mr
     JOIN projects p ON mr.target_project_id = p.id
     ORDER BY mr.created_at DESC
     LIMIT 2000) TO STDOUT WITH (FORMAT csv, HEADER)" \
    > /scratch/general/vast/u1653932/data_sources/gitlab/gitlab_merge_requests.csv

# Users
udocker run gitlab-extract gitlab-psql -c \
    "COPY (SELECT id, username, name, email, created_at, sign_in_count
     FROM users
     ORDER BY id
     LIMIT 500) TO STDOUT WITH (FORMAT csv, HEADER)" \
    > /scratch/general/vast/u1653932/data_sources/gitlab/gitlab_users.csv
```

### Step 4: Convert to JSONL

```bash
python scripts/extract_gitlab_sample.py --convert \
    --projects-csv /scratch/general/vast/u1653932/data_sources/gitlab/gitlab_projects.csv
```

### Step 5: Cleanup (free ~74 GB disk)

```bash
udocker rm gitlab-extract
udocker rmi <IMAGE_NAME>
```

---

## 3b. Wiki ZIM extraction

### Install libzim

```bash
pip install libzim
```

### Extract articles (streaming, low memory)

```python
# Run with: python scripts/extract_wiki_from_zim.py
# (Create this script or run interactively)

from libzim.reader import Archive
import json, re, pathlib

ZIM_PATH = "/scratch/general/vast/u1653932/data_sources/wiki/wikipedia_en_all_maxi_2022-05.zim"
OUTPUT = "/scratch/general/vast/u1653932/data_sources/wiki/wiki_sample.jsonl"
MAX_ARTICLES = 500  # adjust as needed

zim = Archive(ZIM_PATH)  # mmap-based, does NOT load 89 GB into RAM

count = 0
with open(OUTPUT, "w") as f:
    for i in range(zim.entry_count):
        entry = zim._get_entry_by_id(i)
        # Only article namespace (typically "A/" or just articles)
        if not entry.is_redirect:
            try:
                item = entry.get_item()
                content = bytes(item.content).decode("utf-8", errors="replace")
                # Skip non-article entries (metadata, images, etc.)
                if not content.strip().startswith("<") and not content.strip().startswith("{"):
                    continue
                record = {
                    "title": entry.title,
                    "path": entry.path,
                    "content": content[:10000],  # truncate long articles
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
                if count % 100 == 0:
                    print(f"  Extracted {count} articles...")
                if count >= MAX_ARTICLES:
                    break
            except Exception:
                continue

print(f"Done. Wrote {count} articles to {OUTPUT}")
```

**Memory usage**: libzim uses mmap — only pages actually accessed are loaded.
Typical RSS stays under 2-4 GB even for the 89 GB file.

### Alternative: use the enwikinews dump instead (3.6 GB, much smaller)

The `enwikinews` dump at `data_sources/enwikinews/` contains MediaWiki XML
dumps that can be parsed with `mwxml` or simple XML streaming:

```bash
pip install mwxml

python -c "
import mwxml, bz2, json

dump = mwxml.Dump.from_file(
    bz2.open('/scratch/general/vast/u1653932/data_sources/enwikinews/enwikinews-20260501-pages-articles.xml.bz2')
)
count = 0
with open('/scratch/general/vast/u1653932/data_sources/wiki/wikinews_sample.jsonl', 'w') as f:
    for page in dump:
        for rev in page:
            record = {'id': page.id, 'title': page.title, 'text': rev.text[:5000] if rev.text else ''}
            f.write(json.dumps(record) + '\n')
            count += 1
            break  # latest revision only
        if count >= 500:
            break
print(f'Wrote {count} articles')
"
```

---

## 4. When done

```bash
exit  # releases the SLURM allocation
```

---

## Quick reference: memory requirements

| Task                          | `--mem=` | Why                                      |
|-------------------------------|----------|------------------------------------------|
| `udocker load` (GitLab 73GB) | 16G      | Streams tar, low RSS                     |
| Run GitLab container          | 32G      | PostgreSQL + Redis + Puma + Sidekiq      |
| Wiki ZIM via libzim           | 16G      | mmap-based, only pages-in-use are in RAM |
| enwikinews XML parse          | 8G       | Streaming bz2 decompression              |
| **Both GitLab + Wiki**        | **32G**  | Do them sequentially                     |
