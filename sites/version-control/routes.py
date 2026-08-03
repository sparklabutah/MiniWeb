"""MeridianGit -- version-control platform (GitHub / GitLab style).

Loads repository, user, and activity data from the per-site SQLite tables
(version_control_*) and serves a full code-hosting interface with HTML pages
and JSON APIs.  Session mutations are isolated per user via db.query().
"""
import json
import pathlib
import copy
import hashlib
import random
from datetime import datetime, timedelta

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "version-control"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "version-control",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers — all data lives in SQLite via db.query() / db.save_collection()
# ---------------------------------------------------------------------------

def _load_users():
    users = db.query(SITE, "users")
    for u in users:
        if isinstance(u.get("groups"), str):
            try:
                u["groups"] = json.loads(u["groups"])
            except (json.JSONDecodeError, TypeError):
                u["groups"] = []
    return users


def _load_repos():
    repos = db.query(SITE, "repositories")
    for r in repos:
        if isinstance(r.get("tech_stack"), str):
            try:
                r["tech_stack"] = json.loads(r["tech_stack"])
            except (json.JSONDecodeError, TypeError):
                r["tech_stack"] = []
    return repos


def _load_activities():
    return db.query(SITE, "activities")


def _save_repos(repos):
    db.save_collection(SITE, "repositories", repos)


def _save_activities(activities):
    db.save_collection(SITE, "activities", activities)


def _user_by_id(user_id):
    results = db.query(SITE, "users", where={"root_user_id": user_id}, limit=1)
    if results:
        u = results[0]
        if isinstance(u.get("groups"), str):
            import json as _json
            try:
                u["groups"] = _json.loads(u["groups"])
            except (ValueError, TypeError):
                u["groups"] = []
        return u
    return None


def _user_by_username(username):
    results = db.query(SITE, "users", where={"username": username}, limit=1)
    if results:
        u = results[0]
        if isinstance(u.get("groups"), str):
            import json as _json
            try:
                u["groups"] = _json.loads(u["groups"])
            except (ValueError, TypeError):
                u["groups"] = []
        return u
    return None


def _repo_by_id(repo_id):
    repo = db.get_item(SITE, "repositories", repo_id)
    if repo and isinstance(repo.get("tech_stack"), str):
        import json as _json
        try:
            repo["tech_stack"] = _json.loads(repo["tech_stack"])
        except (ValueError, TypeError):
            repo["tech_stack"] = []
    return repo


def _enrich_repo(repo, users=None):
    """Add owner info and normalised field aliases to repo dict.

    The DB columns use ``star_count``, ``visibility_level``, and
    ``last_activity_at`` but templates reference ``stars``, ``visibility``,
    ``last_activity``, and ``owner_user_id``.  This helper maps them so
    every template and API consumer works correctly.
    """
    if users is None:
        users = _load_users()
    owner = None
    for u in users:
        if u["root_user_id"] == repo.get("creator_id"):
            owner = u
            break
    enriched = dict(repo)
    if owner:
        enriched["owner_name"] = owner["name"]
        enriched["owner_username"] = owner["username"]
        enriched["owner_user_id"] = owner["root_user_id"]
    else:
        enriched["owner_name"] = "Unknown"
        enriched["owner_username"] = "unknown"
        enriched["owner_user_id"] = repo.get("creator_id", 0)
    # Alias DB column names to the names used in templates / API
    enriched["stars"] = repo.get("star_count", repo.get("stars", 0))
    enriched["visibility"] = repo.get("visibility_level", repo.get("visibility", "private"))
    enriched["last_activity"] = repo.get("last_activity_at", repo.get("last_activity", ""))
    return enriched


def _enrich_activity(act, users=None):
    """Add author display info to activity."""
    if users is None:
        users = _load_users()
    enriched = dict(act)
    for u in users:
        if u["root_user_id"] == act.get("author_root_user_id"):
            enriched["author_name"] = u["name"]
            enriched["author_username"] = u["username"]
            break
    else:
        enriched["author_name"] = act.get("username", "Unknown")
        enriched["author_username"] = act.get("username", "unknown")
    return enriched


# Synthetic file trees for repos (generated deterministically from repo data)
_FILE_TREES = {
    "meridianflow-api": [
        {"name": "README.md", "type": "file", "size": 4200},
        {"name": "pyproject.toml", "type": "file", "size": 1800},
        {"name": "Dockerfile", "type": "file", "size": 620},
        {"name": ".gitlab-ci.yml", "type": "file", "size": 950},
        {"name": "src/", "type": "dir", "children": [
            {"name": "main.py", "type": "file", "size": 2100},
            {"name": "config.py", "type": "file", "size": 890},
            {"name": "workflows/", "type": "dir", "children": [
                {"name": "engine.py", "type": "file", "size": 5600},
                {"name": "models.py", "type": "file", "size": 3200},
                {"name": "scheduler.py", "type": "file", "size": 2800},
            ]},
            {"name": "api/", "type": "dir", "children": [
                {"name": "routes.py", "type": "file", "size": 4100},
                {"name": "schemas.py", "type": "file", "size": 1900},
                {"name": "webhooks.py", "type": "file", "size": 3400},
            ]},
        ]},
        {"name": "tests/", "type": "dir", "children": [
            {"name": "test_engine.py", "type": "file", "size": 6200},
            {"name": "test_webhooks.py", "type": "file", "size": 3100},
            {"name": "conftest.py", "type": "file", "size": 1200},
        ]},
    ],
    "meridianvault-engine": [
        {"name": "README.md", "type": "file", "size": 3800},
        {"name": "go.mod", "type": "file", "size": 450},
        {"name": "Makefile", "type": "file", "size": 1200},
        {"name": "cmd/", "type": "dir", "children": [
            {"name": "server/main.go", "type": "file", "size": 1800},
            {"name": "worker/main.go", "type": "file", "size": 1400},
        ]},
        {"name": "internal/", "type": "dir", "children": [
            {"name": "detector/anomaly.go", "type": "file", "size": 4200},
            {"name": "detector/scoring.go", "type": "file", "size": 3600},
            {"name": "pipeline/consumer.go", "type": "file", "size": 2800},
            {"name": "secrets/vault.py", "type": "file", "size": 2100},
        ]},
        {"name": "deploy/", "type": "dir", "children": [
            {"name": "docker-compose.yml", "type": "file", "size": 980},
            {"name": "k8s/deployment.yaml", "type": "file", "size": 1400},
        ]},
    ],
    "meridianlens-analytics": [
        {"name": "README.md", "type": "file", "size": 5100},
        {"name": "package.json", "type": "file", "size": 1200},
        {"name": "tsconfig.json", "type": "file", "size": 680},
        {"name": "backend/", "type": "dir", "children": [
            {"name": "app.py", "type": "file", "size": 2400},
            {"name": "nlq/parser.py", "type": "file", "size": 4800},
            {"name": "nlq/executor.py", "type": "file", "size": 3200},
            {"name": "pipelines/etl.py", "type": "file", "size": 2900},
        ]},
        {"name": "frontend/", "type": "dir", "children": [
            {"name": "src/App.tsx", "type": "file", "size": 3100},
            {"name": "src/components/Dashboard.tsx", "type": "file", "size": 5400},
            {"name": "src/components/Chart.tsx", "type": "file", "size": 2600},
        ]},
    ],
    "shared-gateway": [
        {"name": "README.md", "type": "file", "size": 3200},
        {"name": "package.json", "type": "file", "size": 900},
        {"name": "tsconfig.json", "type": "file", "size": 540},
        {"name": "src/", "type": "dir", "children": [
            {"name": "index.ts", "type": "file", "size": 1600},
            {"name": "auth/oauth2.ts", "type": "file", "size": 3800},
            {"name": "auth/saml.ts", "type": "file", "size": 2900},
            {"name": "middleware/rateLimit.ts", "type": "file", "size": 2100},
            {"name": "middleware/cors.ts", "type": "file", "size": 800},
            {"name": "routing/proxy.ts", "type": "file", "size": 2400},
        ]},
        {"name": "nginx/", "type": "dir", "children": [
            {"name": "nginx.conf", "type": "file", "size": 1800},
            {"name": "ssl/README.md", "type": "file", "size": 400},
        ]},
    ],
    "infrastructure": [
        {"name": "README.md", "type": "file", "size": 4600},
        {"name": "Makefile", "type": "file", "size": 1100},
        {"name": "terraform/", "type": "dir", "children": [
            {"name": "main.tf", "type": "file", "size": 3200},
            {"name": "variables.tf", "type": "file", "size": 2100},
            {"name": "modules/eks/cluster.tf", "type": "file", "size": 4500},
            {"name": "modules/rds/main.tf", "type": "file", "size": 2800},
            {"name": "modules/pgbouncer/main.tf", "type": "file", "size": 1900},
        ]},
        {"name": "k8s/", "type": "dir", "children": [
            {"name": "base/namespace.yaml", "type": "file", "size": 320},
            {"name": "overlays/staging/kustomization.yaml", "type": "file", "size": 580},
            {"name": "overlays/production/kustomization.yaml", "type": "file", "size": 620},
        ]},
        {"name": ".github/workflows/", "type": "dir", "children": [
            {"name": "terraform-plan.yml", "type": "file", "size": 1400},
            {"name": "deploy.yml", "type": "file", "size": 1800},
        ]},
    ],
    "docs-site": [
        {"name": "README.md", "type": "file", "size": 2400},
        {"name": "package.json", "type": "file", "size": 800},
        {"name": "docusaurus.config.ts", "type": "file", "size": 2200},
        {"name": "docs/", "type": "dir", "children": [
            {"name": "intro.md", "type": "file", "size": 1800},
            {"name": "meridianflow/getting-started.md", "type": "file", "size": 3400},
            {"name": "meridianflow/api-reference.md", "type": "file", "size": 8200},
            {"name": "meridianvault/setup.md", "type": "file", "size": 2600},
            {"name": "meridianlens/dashboards.md", "type": "file", "size": 4100},
        ]},
        {"name": "src/", "type": "dir", "children": [
            {"name": "pages/index.tsx", "type": "file", "size": 2800},
            {"name": "css/custom.css", "type": "file", "size": 1200},
        ]},
    ],
    "internal-tools": [
        {"name": "README.md", "type": "file", "size": 3600},
        {"name": "pyproject.toml", "type": "file", "size": 900},
        {"name": "cli/", "type": "dir", "children": [
            {"name": "main.py", "type": "file", "size": 1800},
            {"name": "db_migrate.py", "type": "file", "size": 2400},
            {"name": "load_test.py", "type": "file", "size": 3100},
        ]},
        {"name": "scripts/", "type": "dir", "children": [
            {"name": "dev-setup.sh", "type": "file", "size": 1400},
            {"name": "seed-db.sh", "type": "file", "size": 800},
        ]},
        {"name": "docker/", "type": "dir", "children": [
            {"name": "Dockerfile.dev", "type": "file", "size": 620},
            {"name": "docker-compose.dev.yml", "type": "file", "size": 1100},
        ]},
    ],
    "flownet-research": [
        {"name": "README.md", "type": "file", "size": 6800},
        {"name": "pyproject.toml", "type": "file", "size": 1100},
        {"name": "paper/", "type": "dir", "children": [
            {"name": "flownet-icml2026.tex", "type": "file", "size": 42000},
            {"name": "figures/architecture.pdf", "type": "file", "size": 180000},
            {"name": "figures/ablation.pdf", "type": "file", "size": 95000},
        ]},
        {"name": "src/", "type": "dir", "children": [
            {"name": "model/flownet.py", "type": "file", "size": 5800},
            {"name": "model/attention.py", "type": "file", "size": 3200},
            {"name": "data/loader.py", "type": "file", "size": 2400},
            {"name": "train.py", "type": "file", "size": 4100},
            {"name": "evaluate.py", "type": "file", "size": 2800},
        ]},
        {"name": "notebooks/", "type": "dir", "children": [
            {"name": "ablation_analysis.ipynb", "type": "file", "size": 34000},
            {"name": "visualization.ipynb", "type": "file", "size": 28000},
        ]},
        {"name": "configs/", "type": "dir", "children": [
            {"name": "base.yaml", "type": "file", "size": 1200},
            {"name": "ablation_heads.yaml", "type": "file", "size": 800},
        ]},
    ],
}

# Synthetic commit history per repo
_COMMIT_HISTORIES = {
    "meridianflow-api": [
        {"sha": "a3f8c21", "message": "refactor: migrate workflow executor from asyncio.gather to TaskGroup for structured concurrency", "author": "alex.rivera", "date": "2026-06-25T17:42:00Z", "files_changed": 7, "additions": 234, "deletions": 189},
        {"sha": "b7e2d44", "message": "test: add integration tests for TaskGroup error propagation in multi-step workflows", "author": "alex.rivera", "date": "2026-06-25T18:15:00Z", "files_changed": 3, "additions": 156, "deletions": 12},
        {"sha": "k5f2a88", "message": "fix: add jitter to retry backoff per Alex's review feedback", "author": "natalie.kim", "date": "2026-06-24T14:45:00Z", "files_changed": 2, "additions": 18, "deletions": 6},
        {"sha": "c1d9f88", "message": "feat: implement webhook delivery retry with exponential backoff and jitter", "author": "natalie.kim", "date": "2026-06-23T16:20:00Z", "files_changed": 5, "additions": 312, "deletions": 45},
        {"sha": "9e4b3c1", "message": "chore: bump FastAPI to 0.115.0, update Pydantic models", "author": "alex.rivera", "date": "2026-06-22T10:00:00Z", "files_changed": 4, "additions": 45, "deletions": 38},
        {"sha": "7a2f1d0", "message": "feat: add bulk workflow import endpoint with CSV parsing", "author": "natalie.kim", "date": "2026-06-20T14:30:00Z", "files_changed": 3, "additions": 189, "deletions": 0},
        {"sha": "5c8e9b2", "message": "fix: handle null tenant_id in workflow creation gracefully", "author": "alex.rivera", "date": "2026-06-19T09:15:00Z", "files_changed": 2, "additions": 24, "deletions": 8},
    ],
    "meridianvault-engine": [
        {"sha": "d4a7b12", "message": "fix: correct window boundary calculation in sliding aggregation when events span midnight UTC", "author": "marcus.chen", "date": "2026-06-24T09:50:00Z", "files_changed": 2, "additions": 28, "deletions": 11},
        {"sha": "8f3c6a9", "message": "feat: real-time anomaly scoring pipeline with sliding window aggregation", "author": "marcus.chen", "date": "2026-06-23T18:00:00Z", "files_changed": 8, "additions": 567, "deletions": 123},
        {"sha": "2b1d4e7", "message": "test: add benchmark suite for scoring pipeline throughput", "author": "marcus.chen", "date": "2026-06-22T15:30:00Z", "files_changed": 3, "additions": 245, "deletions": 0},
        {"sha": "6e9a0c3", "message": "refactor: extract Kafka consumer into reusable pipeline module", "author": "marcus.chen", "date": "2026-06-21T11:20:00Z", "files_changed": 5, "additions": 312, "deletions": 278},
    ],
    "meridianlens-analytics": [
        {"sha": "3f7b2a1", "message": "feat: add natural language query parser with SQL generation", "author": "aisha.patel", "date": "2026-06-23T09:55:00Z", "files_changed": 4, "additions": 489, "deletions": 67},
        {"sha": "1c4e8d6", "message": "fix: DuckDB query timeout on large aggregation queries", "author": "aisha.patel", "date": "2026-06-22T16:40:00Z", "files_changed": 2, "additions": 34, "deletions": 12},
        {"sha": "9a5f3b8", "message": "feat: add chart type auto-selection based on data shape", "author": "aisha.patel", "date": "2026-06-21T14:00:00Z", "files_changed": 3, "additions": 178, "deletions": 45},
    ],
    "shared-gateway": [
        {"sha": "j3d7e11", "message": "feat: add X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset headers to gateway responses", "author": "alex.rivera", "date": "2026-06-21T16:55:00Z", "files_changed": 4, "additions": 98, "deletions": 15},
        {"sha": "4b2c9f0", "message": "fix: SAML assertion validation bypass for expired certificates", "author": "alex.rivera", "date": "2026-06-20T10:30:00Z", "files_changed": 2, "additions": 56, "deletions": 23},
        {"sha": "8d1e5a3", "message": "chore: update Node.js to v22 LTS, audit dependencies", "author": "alex.rivera", "date": "2026-06-18T09:00:00Z", "files_changed": 3, "additions": 890, "deletions": 780},
    ],
    "infrastructure": [
        {"sha": "e5c3a99", "message": "infra: upgrade EKS cluster to Kubernetes 1.30, update node group AMIs", "author": "david.petrov", "date": "2026-06-25T20:10:00Z", "files_changed": 4, "additions": 67, "deletions": 52},
        {"sha": "g8d1e33", "message": "infra: add Terraform variables for PgBouncer pool_size and max_client_conn per environment", "author": "david.petrov", "date": "2026-06-23T09:15:00Z", "files_changed": 3, "additions": 44, "deletions": 8},
        {"sha": "f2b8c77", "message": "infra: add PgBouncer deployment with transaction-mode pooling for production RDS instances", "author": "david.petrov", "date": "2026-06-22T15:40:00Z", "files_changed": 6, "additions": 189, "deletions": 23},
        {"sha": "1a3b5c7", "message": "infra: add CloudWatch alarms for RDS connection count thresholds", "author": "david.petrov", "date": "2026-06-20T11:00:00Z", "files_changed": 2, "additions": 78, "deletions": 0},
    ],
    "docs-site": [
        {"sha": "2c4d6e8", "message": "docs: add MeridianLens NLQ quick-start guide", "author": "priya.sharma", "date": "2026-06-20T16:00:00Z", "files_changed": 3, "additions": 234, "deletions": 12},
        {"sha": "5e7f9a1", "message": "docs: update API reference for webhook retry configuration", "author": "natalie.kim", "date": "2026-06-19T14:30:00Z", "files_changed": 2, "additions": 89, "deletions": 34},
        {"sha": "8b0c2d4", "message": "fix: broken links in getting-started guide", "author": "priya.sharma", "date": "2026-06-18T10:15:00Z", "files_changed": 1, "additions": 6, "deletions": 6},
    ],
    "internal-tools": [
        {"sha": "3d5f7a9", "message": "feat: add database migration dry-run mode", "author": "marcus.chen", "date": "2026-06-18T13:45:00Z", "files_changed": 2, "additions": 134, "deletions": 23},
        {"sha": "6f8a0b2", "message": "feat: add load test scenario for concurrent workflow execution", "author": "marcus.chen", "date": "2026-06-17T16:20:00Z", "files_changed": 3, "additions": 267, "deletions": 0},
        {"sha": "9c1d3e5", "message": "fix: dev-setup.sh fails on Apple Silicon due to wrong Docker platform", "author": "alex.rivera", "date": "2026-06-16T11:00:00Z", "files_changed": 1, "additions": 8, "deletions": 3},
    ],
    "flownet-research": [
        {"sha": "h9f4a22", "message": "experiment: add ablation study results for attention head count vs routing accuracy (Table 3)", "author": "aisha.patel", "date": "2026-06-25T22:30:00Z", "files_changed": 4, "additions": 178, "deletions": 32},
        {"sha": "i1c5b66", "message": "paper: update camera-ready draft with reviewer 2 feedback on scalability section", "author": "aisha.patel", "date": "2026-06-24T19:00:00Z", "files_changed": 2, "additions": 89, "deletions": 34},
        {"sha": "4a6c8e0", "message": "experiment: run full training on 8xA100 with final hyperparameters", "author": "aisha.patel", "date": "2026-06-22T08:00:00Z", "files_changed": 3, "additions": 45, "deletions": 12},
        {"sha": "7d9f1b3", "message": "feat: implement multi-head attention routing module", "author": "aisha.patel", "date": "2026-06-20T15:30:00Z", "files_changed": 2, "additions": 356, "deletions": 89},
        {"sha": "0e2g4i6", "message": "data: add preprocessed workflow graph dataset (10K samples)", "author": "aisha.patel", "date": "2026-06-18T10:00:00Z", "files_changed": 5, "additions": 1200, "deletions": 0},
    ],
}

# Synthetic README content per repo
_READMES = {
    "meridianflow-api": """# MeridianFlow API

Core REST and GraphQL API for the MeridianFlow workflow automation platform.

## Architecture

- **FastAPI** application with async request handling
- **PostgreSQL** for persistent storage via SQLAlchemy
- **Redis** for caching and session management
- **Celery** for background task execution

## Quick Start

```bash
pip install -e ".[dev]"
uvicorn src.main:app --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/workflows` | Create a new workflow |
| GET | `/api/v1/workflows/{id}` | Get workflow status |
| POST | `/api/v1/workflows/{id}/execute` | Trigger workflow execution |
| GET | `/api/v1/tenants` | List tenants |

## Testing

```bash
pytest tests/ -v --cov=src
```""",
    "meridianvault-engine": """# MeridianVault Engine

Threat detection engine and secrets management service.

## Components

- **Anomaly Detector**: Real-time event scoring with sliding window aggregation
- **Secrets Vault**: Encrypted at-rest secrets with access audit logging
- **Pipeline**: Kafka consumer for event stream processing

## Build

```bash
make build
make test
```

## Deployment

```bash
docker-compose -f deploy/docker-compose.yml up -d
```""",
    "meridianlens-analytics": """# MeridianLens Analytics

Business intelligence dashboard with natural language querying (NLQ).

## Features

- Natural language to SQL query translation
- Auto-generated visualizations based on data shape
- Real-time data pipeline orchestration with Apache Arrow
- DuckDB for fast analytical queries

## Development

```bash
# Backend
cd backend && pip install -e . && python app.py

# Frontend
cd frontend && npm install && npm run dev
```""",
    "shared-gateway": """# Shared Gateway

API gateway and authentication service for all Meridian products.

## Features

- OAuth2 and SAML SSO authentication
- Rate limiting with configurable per-tenant limits
- Request routing and load balancing
- CORS and security headers

## Configuration

Environment variables:
- `GATEWAY_PORT` - Listen port (default: 8080)
- `REDIS_URL` - Redis connection for rate limiting
- `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` - OAuth2 credentials""",
    "infrastructure": """# Infrastructure

Terraform modules, Kubernetes manifests, and CI/CD pipelines for Meridian cloud infrastructure.

## Structure

```
terraform/          # AWS infrastructure as code
k8s/                # Kubernetes manifests (Kustomize)
.github/workflows/  # CI/CD pipeline definitions
```

## Environments

| Environment | AWS Account | Region |
|-------------|-------------|--------|
| Staging | 123456789012 | us-west-2 |
| Production | 987654321098 | us-west-2, us-east-1 |

## Usage

```bash
cd terraform && terraform init && terraform plan
```""",
    "docs-site": """# Meridian Documentation Site

Public documentation for MeridianFlow, MeridianVault, and MeridianLens.

Built with [Docusaurus](https://docusaurus.io) and deployed to docs.meridiansystems.com.

## Local Development

```bash
npm install
npm run start
```

## Deployment

Automatic deployment via GitLab CI on merge to `main`.""",
    "internal-tools": """# Internal Tools

Developer tooling for the Meridian engineering team.

## CLI Commands

- `meridian db migrate` - Run database migrations
- `meridian db seed` - Seed development database
- `meridian loadtest` - Run load testing scenarios
- `meridian setup` - Initialize development environment

## Development

```bash
pip install -e ".[dev]"
meridian --help
```""",
    "flownet-research": """# FlowNet: Graph Neural Network Approach to Workflow Optimization

Research codebase for our ICML 2026 paper on attention-based task routing in workflow automation systems.

## Abstract

We propose FlowNet, a graph neural network architecture that learns optimal task routing policies for workflow automation. Our approach uses multi-head attention over workflow graph structures to predict execution paths that minimize latency while respecting resource constraints.

## Results

| Model | Routing Accuracy | Latency Reduction |
|-------|-----------------|-------------------|
| Baseline (round-robin) | 67.2% | - |
| GCN | 78.4% | 23.1% |
| GAT | 82.1% | 31.7% |
| **FlowNet (ours)** | **89.3%** | **42.5%** |

## Training

```bash
python src/train.py --config configs/base.yaml
```

## Citation

```bibtex
@inproceedings{patel2026flownet,
  title={FlowNet: Attention-Based Task Routing for Workflow Optimization},
  author={Patel, Aisha and Chen, Marcus},
  booktitle={ICML},
  year={2026}
}
```""",
}

# Issues per repo (synthetic)
_ISSUES = {
    1001: [
        {"id": 1, "title": "Workflow execution hangs when step timeout exceeds global timeout", "state": "open", "author": "natalie.kim", "labels": ["bug", "priority:high"], "created_at": "2026-06-24T08:00:00Z", "comments": 3},
        {"id": 2, "title": "Add GraphQL subscription for real-time workflow status updates", "state": "open", "author": "alex.rivera", "labels": ["enhancement", "api"], "created_at": "2026-06-22T14:00:00Z", "comments": 5},
        {"id": 3, "title": "Rate limiting not applied to webhook callback endpoints", "state": "closed", "author": "marcus.chen", "labels": ["bug", "security"], "created_at": "2026-06-18T10:00:00Z", "comments": 2},
    ],
    1002: [
        {"id": 1, "title": "False positive anomaly alerts during maintenance windows", "state": "open", "author": "david.petrov", "labels": ["bug"], "created_at": "2026-06-23T11:00:00Z", "comments": 4},
        {"id": 2, "title": "Add Prometheus metrics exporter for scoring pipeline", "state": "open", "author": "marcus.chen", "labels": ["enhancement", "observability"], "created_at": "2026-06-20T09:00:00Z", "comments": 1},
    ],
    1003: [
        {"id": 1, "title": "NLQ parser fails on queries with multiple JOIN clauses", "state": "open", "author": "aisha.patel", "labels": ["bug"], "created_at": "2026-06-22T15:00:00Z", "comments": 2},
    ],
    1004: [
        {"id": 1, "title": "SAML metadata refresh not working with Azure AD", "state": "open", "author": "alex.rivera", "labels": ["bug", "auth"], "created_at": "2026-06-21T10:00:00Z", "comments": 6},
        {"id": 2, "title": "Add OpenTelemetry tracing to all gateway routes", "state": "open", "author": "david.petrov", "labels": ["enhancement", "observability"], "created_at": "2026-06-19T16:00:00Z", "comments": 3},
    ],
    1005: [
        {"id": 1, "title": "Terraform state lock timeout during concurrent pipeline runs", "state": "open", "author": "david.petrov", "labels": ["bug", "ci-cd"], "created_at": "2026-06-24T07:00:00Z", "comments": 2},
    ],
    1006: [
        {"id": 1, "title": "Search index not updating for newly added pages", "state": "open", "author": "priya.sharma", "labels": ["bug"], "created_at": "2026-06-19T12:00:00Z", "comments": 1},
    ],
    1007: [],
    1008: [
        {"id": 1, "title": "Training diverges with learning rate > 1e-3 on large graphs", "state": "open", "author": "aisha.patel", "labels": ["bug", "training"], "created_at": "2026-06-21T20:00:00Z", "comments": 3},
    ],
}

# Track starred repos per session (in-memory; session-based for simplicity)
# In production you'd persist this.

def _get_starred(repo_id):
    """Check if current session user has starred a repo."""
    starred = session.get("starred_repos", [])
    return repo_id in starred


def _toggle_star(repo_id):
    """Toggle star status for a repo; returns new star state."""
    starred = session.get("starred_repos", [])
    if repo_id in starred:
        starred.remove(repo_id)
        new_state = False
    else:
        starred.append(repo_id)
        new_state = True
    session["starred_repos"] = starred
    return new_state


def _format_size(size_bytes):
    """Format byte size to human readable."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _sort_repos(repos, sort_by="updated"):
    """Sort repository list.

    Works with both enriched dicts (which have ``stars`` / ``last_activity``
    aliases) and raw DB rows (which use ``star_count`` / ``last_activity_at``).
    """
    if sort_by == "stars":
        return sorted(repos, key=lambda r: r.get("stars", r.get("star_count", 0)), reverse=True)
    elif sort_by == "name":
        return sorted(repos, key=lambda r: r.get("name", "").lower())
    else:  # updated
        return sorted(repos, key=lambda r: r.get("last_activity", r.get("last_activity_at", "")), reverse=True)


# ---------------------------------------------------------------------------
# Synthetic repo content generator
# ---------------------------------------------------------------------------
# Most projects/repos have no hand-authored file tree, commits, or README, so
# their detail pages looked empty. Generate realistic, stack-appropriate
# content deterministically from the repo name so every page is populated and
# stable across reloads.

_STACKS = {
    "python": {
        "root": [("README.md", 3800), ("pyproject.toml", 1400), (".gitignore", 520),
                 ("requirements.txt", 340), (".gitlab-ci.yml", 780), ("LICENSE", 1070)],
        "src_dir": "src", "src": [("__init__.py", 60), ("main.py", 2400), ("config.py", 910),
                                    ("models.py", 3100), ("utils.py", 1450)],
        "subdir": ("api", [("routes.py", 2600), ("schemas.py", 1800)]),
        "tests": [("test_main.py", 1700), ("test_models.py", 2050), ("conftest.py", 640)],
        "ext": ".py",
    },
    "node": {
        "root": [("README.md", 3600), ("package.json", 1250), (".gitignore", 480),
                 ("tsconfig.json", 720), (".eslintrc.json", 410), ("LICENSE", 1070)],
        "src_dir": "src", "src": [("index.ts", 1900), ("app.ts", 2600), ("router.ts", 1500),
                                   ("db.ts", 1240)],
        "subdir": ("components", [("Header.tsx", 1600), ("Layout.tsx", 2100)]),
        "tests": [("app.test.ts", 1800), ("router.test.ts", 1350)],
        "ext": ".ts",
    },
    "go": {
        "root": [("README.md", 3400), ("go.mod", 320), ("go.sum", 4800),
                 ("Makefile", 640), (".gitlab-ci.yml", 810), ("LICENSE", 1070)],
        "src_dir": "cmd", "src": [("main.go", 2200), ("server.go", 3100)],
        "subdir": ("internal", [("handler.go", 2700), ("store.go", 2400), ("config.go", 980)]),
        "tests": [("server_test.go", 2050), ("handler_test.go", 1780)],
        "ext": ".go",
    },
    "docs": {
        "root": [("README.md", 4200), ("mkdocs.yml", 680), (".gitignore", 210),
                 ("CONTRIBUTING.md", 1900), ("LICENSE", 1070)],
        "src_dir": "docs", "src": [("index.md", 2400), ("getting-started.md", 3100),
                                    ("configuration.md", 2800), ("faq.md", 1600)],
        "subdir": ("guides", [("deployment.md", 2600), ("upgrading.md", 1900)]),
        "tests": None,
        "ext": ".md",
    },
}

_COMMIT_VERBS = [
    ("feat", ["add pagination to the results endpoint", "implement token refresh flow",
              "add retry with exponential backoff", "support bulk import from CSV",
              "add health-check and readiness probes", "introduce structured logging",
              "add configurable rate limiting", "cache expensive lookups in Redis"]),
    ("fix", ["handle null values in the parser", "correct off-by-one in pagination",
             "resolve race condition on shutdown", "escape user input in query builder",
             "prevent duplicate webhook deliveries", "fix timezone handling in reports"]),
    ("refactor", ["extract client into its own module", "simplify config loading",
                  "split the god object into services", "replace manual JSON with a schema"]),
    ("chore", ["bump dependencies to latest patch", "update CI to the new runner image",
               "tidy up imports and dead code", "add pre-commit hooks"]),
    ("test", ["add integration tests for the API layer", "cover the error paths",
              "add a benchmark for the hot path"]),
    ("docs", ["expand the README with usage examples", "document the configuration options",
              "add an architecture overview"]),
]


def _pick_stack(name, description):
    text = (name + " " + (description or "")).lower()
    if any(k in text for k in ("react", "vue", "node", "npm", "js", "typescript", "frontend", "web", "app", "ui")):
        return "node"
    if any(k in text for k in ("go", "golang", "gateway", "grpc", "kube", "k8s", "operator")):
        return "go"
    if any(k in text for k in ("doc", "docs", "wiki", "book", "guide", "handbook", "paper", "notes")):
        return "docs"
    return "python"  # sensible default (also covers ml/data/api)


def _seeded(name):
    return random.Random(int(hashlib.md5(name.encode()).hexdigest()[:8], 16))


def _generate_file_tree(name, description):
    stack = _STACKS[_pick_stack(name, description)]
    tree = [{"name": n, "type": "file", "size": s} for n, s in stack["root"]]
    src_children = [{"name": n, "type": "file", "size": s} for n, s in stack["src"]]
    sub_name, sub_files = stack["subdir"]
    src_children.append({
        "name": sub_name + "/", "type": "dir",
        "children": [{"name": n, "type": "file", "size": s} for n, s in sub_files],
    })
    tree.append({"name": stack["src_dir"] + "/", "type": "dir", "children": src_children})
    if stack["tests"]:
        tree.append({"name": "tests/", "type": "dir",
                     "children": [{"name": n, "type": "file", "size": s} for n, s in stack["tests"]]})
    return tree


def _generate_commits(name, description, author, last_activity):
    rnd = _seeded(name + "commits")
    try:
        base = datetime.strptime((last_activity or "")[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        base = datetime(2026, 6, 1)
    authors = [a for a in [author, "alex.rivera", "marcus.chen", "aisha.patel", "natalie.kim"] if a]
    commits = []
    day_cursor = 0
    for _ in range(rnd.randint(6, 9)):
        prefix, msgs = rnd.choice(_COMMIT_VERBS)
        day_cursor += rnd.randint(1, 6)
        dt = base - timedelta(days=day_cursor, hours=rnd.randint(0, 20), minutes=rnd.randint(0, 59))
        commits.append({
            "sha": hashlib.md5((name + str(day_cursor) + prefix).encode()).hexdigest()[:7],
            "message": f"{prefix}: {rnd.choice(msgs)}",
            "author": rnd.choice(authors),
            "date": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files_changed": rnd.randint(1, 9),
            "additions": rnd.randint(5, 400),
            "deletions": rnd.randint(0, 180),
        })
    return commits


def _generate_readme(name, description, namespace):
    stack_key = _pick_stack(name, description)
    desc = description or f"{name} is a project maintained by the {namespace or 'team'}."
    install = {
        "python": "pip install -e .",
        "node": "npm install",
        "go": "go build ./...",
        "docs": "mkdocs serve",
    }[stack_key]
    run = {
        "python": "python -m src.main",
        "node": "npm run dev",
        "go": "./bin/server",
        "docs": "mkdocs build",
    }[stack_key]
    return (
        f"# {name}\n\n"
        f"{desc}\n\n"
        f"## Getting started\n\n"
        f"Clone the repository and install the dependencies:\n\n"
        f"```\ngit clone git@meridiangit.dev:{namespace or 'team'}/{name}.git\ncd {name}\n{install}\n```\n\n"
        f"## Running\n\n"
        f"```\n{run}\n```\n\n"
        f"## Contributing\n\n"
        f"Open a merge request against `main`. Please make sure the test suite and "
        f"the CI pipeline pass before requesting review.\n\n"
        f"## License\n\n"
        f"Released under the MIT License."
    )


def _generate_repo_content(repo):
    """Return (files, commits, readme) generated deterministically for a repo."""
    name = repo.get("name", "project")
    description = repo.get("description", "")
    namespace = repo.get("namespace") or repo.get("owner_username") or repo.get("creator_username") or "team"
    author = repo.get("owner_username") or repo.get("creator_username") or "alex.rivera"
    last_activity = repo.get("last_activity") or repo.get("last_activity_at") or ""
    return (
        _generate_file_tree(name, description),
        _generate_commits(name, description, author, last_activity),
        _generate_readme(name, description, namespace),
    )


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Dashboard -- recent activity feed."""
    # Recent activity (synthetic, small table)
    activities = db.query(SITE, "activities", sort="-created_at", limit=10)
    users = db.query(SITE, "users")  # small table: 6 rows
    enriched_activities = [_enrich_activity(a, users) for a in activities]

    # Top repos from projects_raw (real GitLab data) for sidebar
    top_repos = db.query(SITE, "projects_raw", sort="-last_activity_at", limit=5)
    for r in top_repos:
        creator = db.get_item(SITE, "users_raw", r.get("creator_id", 0))
        r["owner_username"] = creator["username"] if creator else "unknown"
        r["stars"] = r.get("star_count", 0)
        r["tech_stack"] = []

    # Recent raw issues and MRs for dashboard sidebar
    recent_issues = db.query(SITE, "issues_raw", sort="-updated_at", limit=5)
    recent_mrs = db.query(SITE, "merge_requests_raw", sort="-updated_at", limit=5)
    issue_count = db.count(SITE, "issues_raw")
    mr_count = db.count(SITE, "merge_requests_raw")
    project_count = db.count(SITE, "projects_raw")
    member_count = db.count(SITE, "users_raw")

    return render_template(
        "version-control/index.html",
        activities=enriched_activities,
        repos=top_repos,
        users=users,
        recent_issues=recent_issues,
        recent_mrs=recent_mrs,
        issue_count=issue_count,
        mr_count=mr_count,
        project_count=project_count,
        member_count=member_count,
    )


@blueprint.route("/repos")
def repos_page():
    """Repository listing with sort and filter.

    Queries the projects_raw table (real GitLab data, 175 projects) with
    SQL-level filtering, sorting, and pagination.
    """
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    sort_by = request.args.get("sort", "updated")
    search = request.args.get("q", "")

    if sort_by == "stars":
        order = "star_count DESC"
    elif sort_by == "name":
        order = "name ASC"
    else:  # updated
        order = "last_activity_at DESC"

    if search:
        # Use FTS for search results; count via a generous search
        all_matches = db.search(SITE, "projects_raw", search, limit=10000)
        total = len(all_matches)
        repos = db.search(SITE, "projects_raw", search, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "projects_raw")
        repos = db.query(SITE, "projects_raw", sort=f"-{'star_count' if sort_by == 'stars' else ('last_activity_at' if sort_by == 'updated' else 'name')}",
                         limit=per_page, offset=offset)
        if sort_by == "name":
            repos = db.query(SITE, "projects_raw", sort="name", limit=per_page, offset=offset)

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Enrich each project with creator username from users_raw
    for repo in repos:
        creator = db.get_item(SITE, "users_raw", repo.get("creator_id", 0))
        repo["creator_username"] = creator["username"] if creator else "unknown"
        repo["creator_name"] = creator["name"] if creator else "Unknown"

    return render_template(
        "version-control/repos.html",
        repos=repos,
        sort_by=sort_by,
        search=search,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@blueprint.route("/repo/<int:repo_id>")
def repo_detail(repo_id):
    """Single repo detail: files, commits, README, issues.

    Checks both projects_raw (real GitLab) and repositories (synthetic) tables.
    """
    # Try projects_raw first (real data), then fall back to synthetic repositories
    repo = db.get_item(SITE, "projects_raw", repo_id)
    is_raw = True
    if not repo:
        repo = _repo_by_id(repo_id)
        is_raw = False
    if not repo:
        abort(404)

    if is_raw:
        # Enrich raw project with creator info from users_raw
        creator = db.get_item(SITE, "users_raw", repo.get("creator_id", 0))
        repo["creator_username"] = creator["username"] if creator else "unknown"
        repo["creator_name"] = creator["name"] if creator else "Unknown"
        repo["owner_user_id"] = repo.get("creator_id", 0)
        repo["owner_username"] = repo.get("creator_username", "unknown")
        repo["owner_name"] = repo.get("creator_name", "Unknown")
        repo["stars"] = repo.get("star_count", 0)
        repo["visibility"] = "public" if repo.get("visibility_level", 0) == 20 else ("internal" if repo.get("visibility_level", 0) == 10 else "private")
        repo["last_activity"] = repo.get("last_activity_at", "")
        repo["forks"] = 0
        repo["default_branch"] = "main"
        repo["tech_stack"] = []
        # Get real issues for this project
        issues = db.query(SITE, "issues_raw",
                          where={"project_name": repo["name"]},
                          sort="-updated_at", limit=20)
        # Convert raw issues to the format the template expects
        for issue in issues:
            issue["state"] = "open" if issue.get("state_id") == 1 else "closed"
            issue["labels"] = []
            issue["comments"] = 0
            author = db.get_item(SITE, "users_raw", issue.get("author_id", 0))
            issue["author"] = author["username"] if author else "unknown"
    else:
        users = _load_users()
        repo = _enrich_repo(repo, users)
        issues = _ISSUES.get(repo_id, [])

    files = _FILE_TREES.get(repo["name"])
    commits = _COMMIT_HISTORIES.get(repo["name"])
    readme = _READMES.get(repo["name"])
    # Fall back to generated content so no repo/project page is empty.
    if not files or not commits or not readme:
        gen_files, gen_commits, gen_readme = _generate_repo_content(repo)
        files = files or gen_files
        commits = commits or gen_commits
        readme = readme or gen_readme
    starred = _get_starred(repo_id)
    return render_template(
        "version-control/repo_detail.html",
        repo=repo,
        files=files,
        commits=commits,
        readme=readme,
        issues=issues,
        starred=starred,
        is_raw=is_raw,
    )


@blueprint.route("/user/<int:user_id>")
def user_profile(user_id):
    """User profile page with their repos and activity.

    Checks both synthetic users and users_raw for the profile.
    Shows projects from projects_raw created by this user.
    """
    # Try synthetic users first
    user = _user_by_id(user_id)
    if user:
        # Show synthetic repos for synthetic users
        user_repos = db.query(SITE, "repositories",
                              where={"creator_id": user_id},
                              sort="-last_activity_at", limit=30)
        for r in user_repos:
            if isinstance(r.get("tech_stack"), str):
                try:
                    r["tech_stack"] = json.loads(r["tech_stack"])
                except (json.JSONDecodeError, TypeError):
                    r["tech_stack"] = []
            r["stars"] = r.get("star_count", 0)
            r["visibility"] = r.get("visibility_level", "private")
            r["last_activity"] = r.get("last_activity_at", "")
        activities = db.query(SITE, "activities",
                              where={"author_root_user_id": user_id},
                              sort="-created_at", limit=10)
        enriched_activities = []
        for a in activities:
            ea = dict(a)
            ea["author_name"] = user["name"]
            ea["author_username"] = user["username"]
            enriched_activities.append(ea)
    else:
        # Try users_raw
        raw_user = db.get_item(SITE, "users_raw", user_id)
        if not raw_user:
            abort(404)
        user = {
            "name": raw_user["name"],
            "username": raw_user["username"],
            "email": raw_user.get("email", ""),
            "role": "member",
            "root_user_id": raw_user["id"],
            "created_at": raw_user.get("created_at", ""),
        }
        # Show projects from projects_raw
        user_repos = db.query(SITE, "projects_raw",
                              where={"creator_id": user_id},
                              sort="-last_activity_at", limit=30)
        for r in user_repos:
            r["stars"] = r.get("star_count", 0)
            r["visibility"] = "public" if r.get("visibility_level", 0) == 20 else ("internal" if r.get("visibility_level", 0) == 10 else "private")
            r["last_activity"] = r.get("last_activity_at", "")
            r["tech_stack"] = []
            r["forks"] = 0
        enriched_activities = []

    return render_template(
        "version-control/user_profile.html",
        user=user,
        repos=user_repos,
        activities=enriched_activities,
    )


@blueprint.route("/activity")
def activity_page():
    """Full activity feed."""
    users = db.query(SITE, "users")  # small table: 6 rows
    activities = db.query(SITE, "activities", sort="-created_at", limit=50)
    enriched = [_enrich_activity(a, users) for a in activities]
    return render_template(
        "version-control/activity.html",
        activities=enriched,
    )


@blueprint.route("/explore")
def explore_page():
    """Explore / discover repos from real GitLab data."""
    sort_by = request.args.get("sort", "stars")
    search = request.args.get("q", "")

    if sort_by == "stars":
        order = "star_count DESC"
        sort_col = "-star_count"
    elif sort_by == "name":
        order = "name ASC"
        sort_col = "name"
    else:  # updated
        order = "last_activity_at DESC"
        sort_col = "-last_activity_at"

    if search:
        repos = db.search(SITE, "projects_raw", search, limit=30)
    else:
        repos = db.query(SITE, "projects_raw", sort=sort_col, limit=30)

    # Enrich with creator info
    for repo in repos:
        creator = db.get_item(SITE, "users_raw", repo.get("creator_id", 0))
        repo["creator_username"] = creator["username"] if creator else "unknown"
        repo["creator_name"] = creator["name"] if creator else "Unknown"
        repo["owner_name"] = repo["creator_name"]
        repo["stars"] = repo.get("star_count", 0)
        repo["visibility"] = "public" if repo.get("visibility_level", 0) == 20 else ("internal" if repo.get("visibility_level", 0) == 10 else "private")
        repo["last_activity"] = repo.get("last_activity_at", "")
        repo["forks"] = 0
        repo["tech_stack"] = []

    return render_template(
        "version-control/explore.html",
        repos=repos,
        sort_by=sort_by,
        search=search,
        all_languages=[],
    )


@blueprint.route("/new-repo")
def new_repo_page():
    """Create repository form."""
    users = db.query(SITE, "users")  # small table: 6 rows
    return render_template(
        "version-control/new_repo.html",
        users=users,
    )


@blueprint.route("/login", methods=["GET"])
def login_page():
    """Login page."""
    return render_template("version-control/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    """Handle login form submission."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    user = _user_by_username(username)
    if user and (not password or password == user.get("password", "password")):
        session["vc_user_id"] = user["root_user_id"]
        session["vc_username"] = user["username"]
        session["vc_name"] = user["name"]
        emit("signup", user_id=user["root_user_id"], site_name="version-control", username=username, password=password, email="")
        return redirect(url_for("version-control.index"))
    return render_template("version-control/login.html", error="Invalid username or password.")


@blueprint.route("/logout")
def logout():
    session.pop("vc_user_id", None)
    session.pop("vc_username", None)
    session.pop("vc_name", None)
    return redirect(url_for("version-control.index"))


# ---------------------------------------------------------------------------
# HTML routes — raw GitLab data (issues, merge requests, projects)
# ---------------------------------------------------------------------------

@blueprint.route("/issues")
def issues_page():
    """Browse all issues from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    state_filter = request.args.get("state", "")
    project_filter = request.args.get("project", "")
    search = request.args.get("q", "")

    where = {}
    if state_filter == "open":
        where["state_id"] = 1
    elif state_filter == "closed":
        where["state_id"] = 2

    if project_filter:
        where["project_name"] = project_filter

    if search:
        all_matches = db.search(SITE, "issues_raw", search, where=where or None, limit=10000)
        total = len(all_matches)
        issues = db.search(SITE, "issues_raw", search, where=where or None, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "issues_raw", where=where)
        issues = db.query(SITE, "issues_raw", where=where,
                          sort="-updated_at", limit=per_page, offset=offset)

    total_pages = max(1, (total + per_page - 1) // per_page)

    # Get distinct project names for filter dropdown (small table)
    projects = db.execute(
        "SELECT DISTINCT project_name FROM version_control_issues_raw "
        "ORDER BY project_name LIMIT 100"
    )
    project_names = [p["project_name"] for p in projects]

    return render_template(
        "version-control/issues.html",
        issues=issues,
        page=page,
        total_pages=total_pages,
        total=total,
        state_filter=state_filter,
        project_filter=project_filter,
        search=search,
        project_names=project_names,
    )


@blueprint.route("/merge-requests")
def merge_requests_page():
    """Browse all merge requests from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    state_filter = request.args.get("state", "")
    project_filter = request.args.get("project", "")
    search = request.args.get("q", "")

    where = {}
    if state_filter == "open":
        where["state_id"] = 1
    elif state_filter == "merged":
        where["state_id"] = 3
    elif state_filter == "closed":
        where["state_id"] = 2

    if project_filter:
        where["project_name"] = project_filter

    if search:
        all_matches = db.search(SITE, "merge_requests_raw", search, where=where or None, limit=10000)
        total = len(all_matches)
        mrs = db.search(SITE, "merge_requests_raw", search, where=where or None, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "merge_requests_raw", where=where)
        mrs = db.query(SITE, "merge_requests_raw", where=where,
                       sort="-updated_at", limit=per_page, offset=offset)

    total_pages = max(1, (total + per_page - 1) // per_page)

    projects = db.execute(
        "SELECT DISTINCT project_name FROM version_control_merge_requests_raw "
        "ORDER BY project_name LIMIT 100"
    )
    project_names = [p["project_name"] for p in projects]

    return render_template(
        "version-control/merge_requests.html",
        merge_requests=mrs,
        page=page,
        total_pages=total_pages,
        total=total,
        state_filter=state_filter,
        project_filter=project_filter,
        search=search,
        project_names=project_names,
    )


@blueprint.route("/projects")
def projects_page():
    """Browse all projects from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    search = request.args.get("q", "")
    sort_by = request.args.get("sort", "activity")

    if sort_by == "stars":
        sort_col = "-star_count"
    elif sort_by == "name":
        sort_col = "name"
    else:
        sort_col = "-last_activity_at"

    if search:
        all_matches = db.search(SITE, "projects_raw", search, limit=10000)
        total = len(all_matches)
        projects = db.search(SITE, "projects_raw", search, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "projects_raw")
        projects = db.query(SITE, "projects_raw", sort=sort_col,
                            limit=per_page, offset=offset)

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "version-control/projects.html",
        projects=projects,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        sort_by=sort_by,
    )


@blueprint.route("/project/<project_name>")
def project_detail(project_name):
    """Detail page for a raw GitLab project with its issues and MRs."""
    projects = db.query(SITE, "projects_raw",
                        where={"name": project_name}, limit=1)
    if not projects:
        abort(404)
    project = projects[0]

    # Recent issues for this project
    issues = db.query(SITE, "issues_raw",
                      where={"project_name": project_name},
                      sort="-updated_at", limit=20)
    issue_count = db.count(SITE, "issues_raw",
                           where={"project_name": project_name})

    # Recent merge requests for this project
    mrs = db.query(SITE, "merge_requests_raw",
                   where={"project_name": project_name},
                   sort="-updated_at", limit=20)
    mr_count = db.count(SITE, "merge_requests_raw",
                        where={"project_name": project_name})

    # Generate repository content (file tree, commits, README) so the project
    # page shows actual code, not just issues/MRs.
    creator = db.get_item(SITE, "users_raw", project.get("creator_id", 0))
    if creator:
        project["creator_username"] = creator.get("username", "")
    files, commits, readme = _generate_repo_content(project)

    return render_template(
        "version-control/project_detail.html",
        project=project,
        issues=issues,
        issue_count=issue_count,
        merge_requests=mrs,
        mr_count=mr_count,
        files=files,
        commits=commits,
        readme=readme,
    )


@blueprint.route("/issue/<int:issue_id>")
def issue_detail(issue_id):
    """Detail page for a single raw GitLab issue with its comments."""
    issue = db.get_item(SITE, "issues_raw", issue_id)
    if not issue:
        abort(404)

    # Get comments (notes) for this issue
    notes = db.execute(
        "SELECT * FROM version_control_notes_raw "
        "WHERE noteable_type = 'Issue' AND noteable_id = ? "
        "ORDER BY created_at ASC LIMIT 50",
        (issue_id,),
    )

    # Look up author
    author = db.get_item(SITE, "users_raw", issue["author_id"])

    return render_template(
        "version-control/issue_detail.html",
        issue=issue,
        notes=notes,
        author=author,
    )


@blueprint.route("/mr/<int:mr_id>")
def mr_detail(mr_id):
    """Detail page for a single raw GitLab merge request with its comments."""
    mr = db.get_item(SITE, "merge_requests_raw", mr_id)
    if not mr:
        abort(404)

    # Get comments (notes) for this MR
    notes = db.execute(
        "SELECT * FROM version_control_notes_raw "
        "WHERE noteable_type = 'MergeRequest' AND noteable_id = ? "
        "ORDER BY created_at ASC LIMIT 50",
        (mr_id,),
    )

    author = db.get_item(SITE, "users_raw", mr["author_id"])

    return render_template(
        "version-control/mr_detail.html",
        mr=mr,
        notes=notes,
        author=author,
    )


@blueprint.route("/members")
def members_page():
    """Browse all GitLab users from the raw data."""
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page
    search = request.args.get("q", "")

    if search:
        all_matches = db.search(SITE, "users_raw", search, limit=10000)
        total = len(all_matches)
        members = db.search(SITE, "users_raw", search, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "users_raw")
        members = db.query(SITE, "users_raw", sort="-sign_in_count",
                           limit=per_page, offset=offset)

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "version-control/members.html",
        members=members,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
    )


# ---------------------------------------------------------------------------
# API routes — raw GitLab data
# ---------------------------------------------------------------------------

@blueprint.route("/api/issues", methods=["GET"])
def api_issues_raw():
    """List issues from the raw GitLab data with filtering and pagination."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 100)
    offset = (page - 1) * per_page
    state_id = request.args.get("state_id", type=int)
    project = request.args.get("project", "")
    author_id = request.args.get("author_id", type=int)
    search = request.args.get("q", "")

    where = {}
    if state_id:
        where["state_id"] = state_id
    if project:
        where["project_name"] = project
    if author_id:
        where["author_id"] = author_id

    if search:
        all_matches = db.search(SITE, "issues_raw", search, where=where or None, limit=10000)
        total = len(all_matches)
        issues = db.search(SITE, "issues_raw", search, where=where or None, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "issues_raw", where=where)
        issues = db.query(SITE, "issues_raw", where=where,
                          sort="-updated_at", limit=per_page, offset=offset)

    return jsonify({"issues": issues, "total": total, "page": page,
                    "per_page": per_page})


@blueprint.route("/api/issues/<int:issue_id>", methods=["GET"])
def api_issue_raw_detail(issue_id):
    """Get a single raw issue with its notes."""
    issue = db.get_item(SITE, "issues_raw", issue_id)
    if not issue:
        return jsonify({"error": "Issue not found"}), 404
    notes = db.execute(
        "SELECT * FROM version_control_notes_raw "
        "WHERE noteable_type = 'Issue' AND noteable_id = ? "
        "ORDER BY created_at ASC LIMIT 50",
        (issue_id,),
    )
    issue["notes"] = notes
    return jsonify(issue)


@blueprint.route("/api/merge-requests", methods=["GET"])
def api_merge_requests_raw():
    """List merge requests from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 100)
    offset = (page - 1) * per_page
    state_id = request.args.get("state_id", type=int)
    project = request.args.get("project", "")
    author_id = request.args.get("author_id", type=int)
    search = request.args.get("q", "")

    where = {}
    if state_id:
        where["state_id"] = state_id
    if project:
        where["project_name"] = project
    if author_id:
        where["author_id"] = author_id

    if search:
        all_matches = db.search(SITE, "merge_requests_raw", search, where=where or None, limit=10000)
        total = len(all_matches)
        mrs = db.search(SITE, "merge_requests_raw", search, where=where or None, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "merge_requests_raw", where=where)
        mrs = db.query(SITE, "merge_requests_raw", where=where,
                       sort="-updated_at", limit=per_page, offset=offset)

    return jsonify({"merge_requests": mrs, "total": total, "page": page,
                    "per_page": per_page})


@blueprint.route("/api/merge-requests/<int:mr_id>", methods=["GET"])
def api_mr_raw_detail(mr_id):
    """Get a single raw merge request with its notes."""
    mr = db.get_item(SITE, "merge_requests_raw", mr_id)
    if not mr:
        return jsonify({"error": "Merge request not found"}), 404
    notes = db.execute(
        "SELECT * FROM version_control_notes_raw "
        "WHERE noteable_type = 'MergeRequest' AND noteable_id = ? "
        "ORDER BY created_at ASC LIMIT 50",
        (mr_id,),
    )
    mr["notes"] = notes
    return jsonify(mr)


@blueprint.route("/api/projects", methods=["GET"])
def api_projects_raw():
    """List projects from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 100)
    offset = (page - 1) * per_page
    search = request.args.get("q", "")

    if search:
        all_matches = db.search(SITE, "projects_raw", search, limit=10000)
        total = len(all_matches)
        projects = db.search(SITE, "projects_raw", search, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "projects_raw")
        projects = db.query(SITE, "projects_raw",
                            sort="-last_activity_at",
                            limit=per_page, offset=offset)

    return jsonify({"projects": projects, "total": total, "page": page,
                    "per_page": per_page})


@blueprint.route("/api/members", methods=["GET"])
def api_members_raw():
    """List users from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 100)
    offset = (page - 1) * per_page
    search = request.args.get("q", "")

    if search:
        all_matches = db.search(SITE, "users_raw", search, limit=10000)
        total = len(all_matches)
        members = db.search(SITE, "users_raw", search, limit=per_page, offset=offset)
    else:
        total = db.count(SITE, "users_raw")
        members = db.query(SITE, "users_raw", sort="-sign_in_count",
                           limit=per_page, offset=offset)

    return jsonify({"members": members, "total": total, "page": page,
                    "per_page": per_page})


@blueprint.route("/api/notes", methods=["GET"])
def api_notes_raw():
    """List notes (comments) from the raw GitLab data."""
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 30, type=int), 100)
    offset = (page - 1) * per_page
    noteable_type = request.args.get("type", "")
    noteable_id = request.args.get("noteable_id", type=int)
    author_id = request.args.get("author_id", type=int)

    where = {}
    if noteable_type:
        where["noteable_type"] = noteable_type
    if noteable_id:
        where["noteable_id"] = noteable_id
    if author_id:
        where["author_id"] = author_id

    total = db.count(SITE, "notes_raw", where=where)
    notes = db.query(SITE, "notes_raw", where=where,
                     sort="-created_at", limit=per_page, offset=offset)

    return jsonify({"notes": notes, "total": total, "page": page,
                    "per_page": per_page})


@blueprint.route("/api/labels", methods=["GET"])
def api_labels_raw():
    """List labels from the raw GitLab data."""
    project = request.args.get("project", "")
    where = {}
    if project:
        where["project_name"] = project
    labels = db.query(SITE, "labels_raw", where=where, limit=100)
    return jsonify({"labels": labels, "total": len(labels)})


# ---------------------------------------------------------------------------
# API routes — synthetic data (original)
# ---------------------------------------------------------------------------

@blueprint.route("/api/repos", methods=["GET"])
def api_repos_list():
    """GET repos with optional filter by user, language, search. Supports sort."""
    users = _load_users()
    repos = _load_repos()
    enriched = [_enrich_repo(r, users) for r in repos]

    # Filters
    user_id = request.args.get("user_id", type=int)
    language = request.args.get("language", "")
    search = request.args.get("q", "")
    sort_by = request.args.get("sort", "updated")

    if user_id:
        enriched = [r for r in enriched if r.get("creator_id") == user_id]
    if language:
        enriched = [r for r in enriched if language in r.get("tech_stack", [])]
    if search:
        q = search.lower()
        enriched = [r for r in enriched if q in r["name"].lower() or q in r.get("description", "").lower()]

    enriched = _sort_repos(enriched, sort_by)
    return jsonify({"repos": enriched, "total": len(enriched)})


@blueprint.route("/api/repos", methods=["POST"])
def api_repos_create():
    """Create a new repository."""
    data = request.get_json(force=True)
    repos = _load_repos()

    # Generate new ID
    max_id = max((r["id"] for r in repos), default=1000)
    new_id = max_id + 1

    new_repo = {
        "id": new_id,
        "name": data.get("name", "untitled"),
        "namespace": data.get("namespace", "meridian-systems/engineering"),
        "description": data.get("description", ""),
        "visibility": data.get("visibility", "private"),
        "default_branch": data.get("default_branch", "main"),
        "stars": 0,
        "forks": 0,
        "last_activity": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "creator_id": data.get("creator_id", 1),
        "tech_stack": data.get("tech_stack", []),
    }
    repos.append(new_repo)
    _save_repos(repos)
    return jsonify(new_repo), 201


@blueprint.route("/api/repos/<int:repo_id>", methods=["GET"])
def api_repo_detail(repo_id):
    """Get single repo by ID with files, commits, readme, issues."""
    users = _load_users()
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    enriched = _enrich_repo(repo, users)
    enriched["files"] = _FILE_TREES.get(repo["name"], [])
    enriched["commits"] = _COMMIT_HISTORIES.get(repo["name"], [])
    enriched["readme"] = _READMES.get(repo["name"], "")
    enriched["issues"] = _ISSUES.get(repo_id, [])
    return jsonify(enriched)


@blueprint.route("/api/repos/<int:repo_id>", methods=["PUT"])
def api_repo_update(repo_id):
    """Update repo fields (name, description, visibility, tech_stack)."""
    repos = _load_repos()
    target = None
    for r in repos:
        if r["id"] == repo_id:
            target = r
            break
    if not target:
        return jsonify({"error": "Repository not found"}), 404

    data = request.get_json(force=True)
    for field in ("name", "description", "visibility", "default_branch", "tech_stack"):
        if field in data:
            target[field] = data[field]
    target["last_activity"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_repos(repos)
    return jsonify(target)


@blueprint.route("/api/repos/<int:repo_id>", methods=["DELETE"])
def api_repo_delete(repo_id):
    """Delete a repository."""
    repos = _load_repos()
    original_len = len(repos)
    repos = [r for r in repos if r["id"] != repo_id]
    if len(repos) == original_len:
        return jsonify({"error": "Repository not found"}), 404
    _save_repos(repos)
    return jsonify({"deleted": True, "id": repo_id})


@blueprint.route("/api/repos/<int:repo_id>/star", methods=["POST"])
def api_repo_star(repo_id):
    """Toggle star on a repo."""
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    new_state = _toggle_star(repo_id)

    # Update star count in data
    repos = _load_repos()
    for r in repos:
        if r["id"] == repo_id:
            if new_state:
                r["stars"] = r.get("stars", 0) + 1
            else:
                r["stars"] = max(0, r.get("stars", 0) - 1)
            break
    _save_repos(repos)
    return jsonify({"starred": new_state, "stars": r["stars"]})


@blueprint.route("/api/repos/<int:repo_id>/fork", methods=["POST"])
def api_repo_fork(repo_id):
    """Fork a repo (creates a copy under a different namespace)."""
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    data = request.get_json(force=True) if request.is_json else {}
    repos = _load_repos()
    max_id = max((r["id"] for r in repos), default=1000)
    forked = dict(repo)
    forked["id"] = max_id + 1
    forked["name"] = f"{repo['name']}-fork"
    forked["namespace"] = data.get("namespace", repo["namespace"])
    forked["stars"] = 0
    forked["forks"] = 0
    forked["last_activity"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    forked["creator_id"] = data.get("creator_id", repo["creator_id"])

    # Increment fork count on original
    for r in repos:
        if r["id"] == repo_id:
            r["forks"] = r.get("forks", 0) + 1
            break
    repos.append(forked)
    _save_repos(repos)
    return jsonify(forked), 201


@blueprint.route("/api/repos/<int:repo_id>/issues", methods=["GET"])
def api_repo_issues_list(repo_id):
    """List issues for a repo."""
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    issues = _ISSUES.get(repo_id, [])
    state = request.args.get("state", "")
    if state:
        issues = [i for i in issues if i["state"] == state]
    return jsonify({"issues": issues, "total": len(issues)})


@blueprint.route("/api/repos/<int:repo_id>/issues", methods=["POST"])
def api_repo_issues_create(repo_id):
    """Create a new issue on a repo."""
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    data = request.get_json(force=True)
    issues = _ISSUES.get(repo_id, [])
    max_issue_id = max((i["id"] for i in issues), default=0)
    new_issue = {
        "id": max_issue_id + 1,
        "title": data.get("title", "Untitled issue"),
        "state": "open",
        "author": data.get("author", "unknown"),
        "labels": data.get("labels", []),
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "comments": 0,
    }
    issues.append(new_issue)
    _ISSUES[repo_id] = issues
    return jsonify(new_issue), 201


@blueprint.route("/api/activity", methods=["GET"])
def api_activity():
    """Activity feed, optionally filtered by user_id or repo name."""
    users = _load_users()
    activities = _load_activities()
    enriched = [_enrich_activity(a, users) for a in activities]

    user_id = request.args.get("user_id", type=int)
    repo = request.args.get("repo", "")
    if user_id:
        enriched = [a for a in enriched if a.get("author_root_user_id") == user_id]
    if repo:
        enriched = [a for a in enriched if a.get("repo") == repo]

    enriched.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    return jsonify({"activities": enriched, "total": len(enriched)})


@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    """List all users."""
    users = _load_users()
    return jsonify({"users": users, "total": len(users)})


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_detail(user_id):
    """Get single user with their repos."""
    user = _user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    repos = _load_repos()
    user_repos = [r for r in repos if r.get("creator_id") == user_id]
    result = dict(user)
    result["repos"] = user_repos
    return jsonify(result)


@blueprint.route("/api/search", methods=["GET"])
def api_search():
    """Search across repos, users, and activity."""
    q = request.args.get("q", "").lower().strip()
    if not q:
        return jsonify({"repos": [], "users": [], "activities": [], "query": ""})

    users = _load_users()
    repos = _load_repos()
    activities = _load_activities()

    matched_repos = [_enrich_repo(r, users) for r in repos
                     if q in r["name"].lower() or q in r.get("description", "").lower()
                     or any(q in t.lower() for t in r.get("tech_stack", []))]
    matched_users = [u for u in users
                     if q in u["name"].lower() or q in u["username"].lower()
                     or q in u.get("email", "").lower()]
    matched_activities = [_enrich_activity(a, users) for a in activities
                          if q in a.get("commit_message", "").lower()
                          or q in a.get("repo", "").lower()
                          or q in a.get("merge_request_title", "").lower()]

    return jsonify({
        "query": q,
        "repos": matched_repos,
        "users": matched_users,
        "activities": matched_activities[:20],
    })


@blueprint.route("/api/stats", methods=["GET"])
def api_stats():
    """Platform statistics."""
    repos = _load_repos()
    users = _load_users()
    activities = _load_activities()

    total_stars = sum(r.get("stars", 0) for r in repos)
    total_forks = sum(r.get("forks", 0) for r in repos)
    lang_counts = {}
    for r in repos:
        for lang in r.get("tech_stack", []):
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    push_count = sum(1 for a in activities if a.get("type") == "push")
    merge_count = sum(1 for a in activities if a.get("type") == "merge")
    review_count = sum(1 for a in activities if a.get("type") == "merge_request_review")

    return jsonify({
        "total_repos": len(repos),
        "total_users": len(users),
        "total_activities": len(activities),
        "total_stars": total_stars,
        "total_forks": total_forks,
        "languages": lang_counts,
        "activity_breakdown": {
            "pushes": push_count,
            "merges": merge_count,
            "reviews": review_count,
        },
    })


# ---------------------------------------------------------------------------
# Synthetic file content for search_by_code
# ---------------------------------------------------------------------------

_FILE_CONTENTS = {
    "meridianflow-api": {
        "src/main.py": 'from fastapi import FastAPI\nfrom src.config import settings\nfrom src.api.routes import router as api_router\n\napp = FastAPI(title="MeridianFlow API", version="2.4.0")\napp.include_router(api_router, prefix="/api/v1")\n\n@app.on_event("startup")\nasync def startup():\n    await init_db()\n    await init_redis()\n',
        "src/config.py": 'from pydantic_settings import BaseSettings\n\nclass Settings(BaseSettings):\n    DATABASE_URL: str = "postgresql://localhost/meridianflow"\n    REDIS_URL: str = "redis://localhost:6379"\n    SECRET_KEY: str = "change-me"\n    WEBHOOK_RETRY_MAX: int = 5\n    WEBHOOK_RETRY_BASE_DELAY: float = 1.0\n',
        "src/workflows/engine.py": 'import asyncio\nfrom typing import List\nfrom .models import Workflow, WorkflowStep\n\nclass WorkflowEngine:\n    """Execute workflow steps using structured concurrency."""\n\n    async def execute(self, workflow: Workflow) -> dict:\n        async with asyncio.TaskGroup() as tg:\n            tasks = [tg.create_task(self._run_step(s)) for s in workflow.steps]\n        return {"results": [t.result() for t in tasks]}\n\n    async def _run_step(self, step: WorkflowStep) -> dict:\n        # Step execution with timeout\n        return await asyncio.wait_for(step.run(), timeout=step.timeout)\n',
        "src/api/webhooks.py": 'import random\nimport asyncio\nfrom src.config import settings\n\nasync def deliver_webhook(url: str, payload: dict, attempt: int = 0):\n    """Deliver webhook with exponential backoff and jitter."""\n    try:\n        resp = await http_client.post(url, json=payload)\n        resp.raise_for_status()\n    except Exception:\n        if attempt < settings.WEBHOOK_RETRY_MAX:\n            delay = settings.WEBHOOK_RETRY_BASE_DELAY * (2 ** attempt)\n            jitter = random.uniform(0, delay * 0.1)\n            await asyncio.sleep(delay + jitter)\n            return await deliver_webhook(url, payload, attempt + 1)\n        raise\n',
        "tests/test_engine.py": 'import pytest\nfrom src.workflows.engine import WorkflowEngine\n\n@pytest.mark.asyncio\nasync def test_taskgroup_error_propagation():\n    engine = WorkflowEngine()\n    # Test that errors in one step cancel siblings\n    with pytest.raises(ExceptionGroup):\n        await engine.execute(failing_workflow)\n\n@pytest.mark.asyncio\nasync def test_parallel_step_execution():\n    engine = WorkflowEngine()\n    result = await engine.execute(parallel_workflow)\n    assert len(result["results"]) == 3\n',
    },
    "meridianvault-engine": {
        "internal/detector/anomaly.go": 'package detector\n\nimport "time"\n\ntype AnomalyDetector struct {\n\tWindowSize  time.Duration\n\tThreshold   float64\n\tscoreBuffer []float64\n}\n\nfunc (d *AnomalyDetector) Score(event Event) float64 {\n\twindowStart := event.Timestamp.Add(-d.WindowSize)\n\t// Correct boundary: use After, not Before\n\tvar windowScores []float64\n\tfor _, s := range d.scoreBuffer {\n\t\tif s.Timestamp.After(windowStart) {\n\t\t\twindowScores = append(windowScores, s.Value)\n\t\t}\n\t}\n\treturn computeZScore(event.Value, windowScores)\n}\n',
        "internal/pipeline/consumer.go": 'package pipeline\n\nimport (\n\t"context"\n\t"github.com/segmentio/kafka-go"\n)\n\ntype KafkaConsumer struct {\n\tReader *kafka.Reader\n\tTopic  string\n}\n\nfunc (c *KafkaConsumer) Consume(ctx context.Context, handler func([]byte) error) error {\n\tfor {\n\t\tmsg, err := c.Reader.ReadMessage(ctx)\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}\n\t\tif err := handler(msg.Value); err != nil {\n\t\t\tlogError("message processing failed", err)\n\t\t}\n\t}\n}\n',
    },
    "meridianlens-analytics": {
        "backend/nlq/parser.py": 'import re\nfrom typing import List, Tuple\n\nclass NLQParser:\n    """Parse natural language queries into SQL."""\n\n    AGGREGATIONS = {"total": "SUM", "average": "AVG", "count": "COUNT", "maximum": "MAX"}\n\n    def parse(self, query: str) -> str:\n        tokens = self._tokenize(query)\n        table = self._identify_table(tokens)\n        agg = self._identify_aggregation(tokens)\n        filters = self._identify_filters(tokens)\n        return self._build_sql(table, agg, filters)\n\n    def _tokenize(self, query: str) -> List[str]:\n        return re.findall(r"\\w+", query.lower())\n',
        "backend/nlq/executor.py": 'import duckdb\n\nclass QueryExecutor:\n    """Execute SQL queries against DuckDB."""\n\n    def __init__(self, db_path: str = ":memory:"):\n        self.conn = duckdb.connect(db_path)\n\n    def execute(self, sql: str, timeout: int = 30) -> list:\n        try:\n            result = self.conn.execute(sql)\n            return result.fetchall()\n        except duckdb.Error as e:\n            raise QueryExecutionError(str(e))\n',
    },
    "shared-gateway": {
        "src/auth/oauth2.ts": 'import { Request, Response, NextFunction } from "express";\n\nexport class OAuth2Provider {\n  private clientId: string;\n  private clientSecret: string;\n\n  async authenticate(req: Request, res: Response, next: NextFunction) {\n    const token = req.headers.authorization?.split(" ")[1];\n    if (!token) return res.status(401).json({ error: "No token provided" });\n    const decoded = await this.verifyToken(token);\n    req.user = decoded;\n    next();\n  }\n}\n',
        "src/middleware/rateLimit.ts": 'import { Redis } from "ioredis";\n\nexport function rateLimiter(redis: Redis, limit: number, windowMs: number) {\n  return async (req: Request, res: Response, next: NextFunction) => {\n    const key = `ratelimit:${req.ip}`;\n    const current = await redis.incr(key);\n    if (current === 1) await redis.pexpire(key, windowMs);\n    const remaining = Math.max(0, limit - current);\n    res.set("X-RateLimit-Limit", String(limit));\n    res.set("X-RateLimit-Remaining", String(remaining));\n    if (current > limit) return res.status(429).json({ error: "Rate limit exceeded" });\n    next();\n  };\n}\n',
    },
    "infrastructure": {
        "terraform/main.tf": 'provider "aws" {\n  region = var.aws_region\n}\n\nmodule "eks" {\n  source          = "./modules/eks"\n  cluster_name    = "meridian-${var.environment}"\n  cluster_version = "1.30"\n  node_groups     = var.node_groups\n}\n\nmodule "rds" {\n  source        = "./modules/rds"\n  instance_class = var.db_instance_class\n  engine_version = "15.4"\n}\n\nmodule "pgbouncer" {\n  source         = "./modules/pgbouncer"\n  pool_size      = var.pgbouncer_pool_size\n  max_client_conn = var.pgbouncer_max_client_conn\n}\n',
        "terraform/variables.tf": 'variable "aws_region" {\n  default = "us-west-2"\n}\n\nvariable "environment" {\n  type = string\n}\n\nvariable "db_instance_class" {\n  default = "db.r6g.xlarge"\n}\n\nvariable "pgbouncer_pool_size" {\n  description = "Number of server connections per pool"\n  type        = number\n  default     = 20\n}\n\nvariable "pgbouncer_max_client_conn" {\n  description = "Maximum number of client connections"\n  type        = number\n  default     = 200\n}\n',
    },
    "flownet-research": {
        "src/model/flownet.py": 'import torch\nimport torch.nn as nn\nfrom torch_geometric.nn import GATConv\n\nclass FlowNet(nn.Module):\n    """Graph neural network for workflow task routing."""\n\n    def __init__(self, in_features, hidden_dim, num_heads=8):\n        super().__init__()\n        self.attention = MultiHeadRoutingAttention(in_features, hidden_dim, num_heads)\n        self.gat1 = GATConv(in_features, hidden_dim, heads=num_heads)\n        self.gat2 = GATConv(hidden_dim * num_heads, hidden_dim)\n        self.classifier = nn.Linear(hidden_dim, 1)\n\n    def forward(self, x, edge_index):\n        h = self.gat1(x, edge_index).relu()\n        h = self.gat2(h, edge_index).relu()\n        routing_scores = self.attention(h)\n        return self.classifier(routing_scores)\n',
        "src/model/attention.py": 'import torch\nimport torch.nn as nn\nimport math\n\nclass MultiHeadRoutingAttention(nn.Module):\n    """Multi-head attention for task routing decisions."""\n\n    def __init__(self, d_model, d_k, num_heads):\n        super().__init__()\n        self.num_heads = num_heads\n        self.d_k = d_k\n        self.W_q = nn.Linear(d_model, d_k * num_heads)\n        self.W_k = nn.Linear(d_model, d_k * num_heads)\n        self.W_v = nn.Linear(d_model, d_k * num_heads)\n\n    def forward(self, x):\n        Q = self.W_q(x).view(-1, self.num_heads, self.d_k)\n        K = self.W_k(x).view(-1, self.num_heads, self.d_k)\n        V = self.W_v(x).view(-1, self.num_heads, self.d_k)\n        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)\n        attn = torch.softmax(scores, dim=-1)\n        return torch.matmul(attn, V).reshape(-1, self.num_heads * self.d_k)\n',
        "src/train.py": 'import argparse\nimport yaml\nimport torch\nfrom model.flownet import FlowNet\nfrom data.loader import WorkflowGraphDataset\n\ndef train(config):\n    dataset = WorkflowGraphDataset(config["data_path"])\n    model = FlowNet(\n        in_features=config["in_features"],\n        hidden_dim=config["hidden_dim"],\n        num_heads=config["num_heads"],\n    )\n    optimizer = torch.optim.AdamW(model.parameters(), lr=config["lr"])\n    for epoch in range(config["epochs"]):\n        for batch in dataset.loader(config["batch_size"]):\n            loss = model(batch.x, batch.edge_index)\n            loss.backward()\n            optimizer.step()\n',
    },
}

# Issue comments (for post_from_free_text)
_ISSUE_COMMENTS = {
    (1001, 1): [
        {"id": 1, "author": "alex.rivera", "body": "I can reproduce this. The step timeout is checked independently but doesn't propagate to the parent workflow timeout.", "created_at": "2026-06-24T09:00:00Z"},
        {"id": 2, "author": "natalie.kim", "body": "I think the fix should be in the WorkflowEngine.execute method. We need to wrap the TaskGroup in a wait_for with the global timeout.", "created_at": "2026-06-24T10:30:00Z"},
        {"id": 3, "author": "marcus.chen", "body": "Agreed with Natalie's approach. We should also emit a metric when the global timeout fires so we can track how often this happens.", "created_at": "2026-06-24T11:15:00Z"},
    ],
    (1001, 2): [
        {"id": 1, "author": "alex.rivera", "body": "I have a draft PR for this using the graphql-ws library. Need to figure out the subscription auth flow.", "created_at": "2026-06-22T15:00:00Z"},
        {"id": 2, "author": "marcus.chen", "body": "For auth, we should reuse the existing JWT validation middleware. The websocket handshake can pass the token as a query parameter.", "created_at": "2026-06-22T16:30:00Z"},
        {"id": 3, "author": "natalie.kim", "body": "Should we also add a Redis pub/sub backend for horizontal scaling? Multiple API instances need to broadcast status changes.", "created_at": "2026-06-23T09:00:00Z"},
        {"id": 4, "author": "alex.rivera", "body": "Good point. I'll add a Redis pub/sub adapter. We already have the Redis dependency.", "created_at": "2026-06-23T10:00:00Z"},
        {"id": 5, "author": "priya.sharma", "body": "Let's scope this for the v2.5 milestone. @alex.rivera can you update the PR description with the Redis pub/sub plan?", "created_at": "2026-06-23T14:00:00Z"},
    ],
    (1002, 1): [
        {"id": 1, "author": "marcus.chen", "body": "We need a maintenance window flag in the anomaly detector config. During maintenance, the detector should suppress alerts.", "created_at": "2026-06-23T12:00:00Z"},
        {"id": 2, "author": "david.petrov", "body": "I can add a /maintenance endpoint to the infrastructure API that the detector polls. That way DevOps controls the window.", "created_at": "2026-06-23T13:00:00Z"},
        {"id": 3, "author": "aisha.patel", "body": "Another option: use a time-series baseline that accounts for periodic maintenance patterns. The model would learn to expect the variance.", "created_at": "2026-06-23T15:00:00Z"},
        {"id": 4, "author": "marcus.chen", "body": "Let's go with David's approach for now since it's simpler. We can add the ML approach later as a follow-up.", "created_at": "2026-06-24T09:00:00Z"},
    ],
    (1004, 1): [
        {"id": 1, "author": "alex.rivera", "body": "Azure AD sends the metadata at a non-standard endpoint. Our SAML library expects the standard /metadata path.", "created_at": "2026-06-21T11:00:00Z"},
        {"id": 2, "author": "david.petrov", "body": "Can we make the metadata URL configurable per identity provider instead of assuming the standard path?", "created_at": "2026-06-21T12:30:00Z"},
        {"id": 3, "author": "alex.rivera", "body": "Yes, I'll add a metadata_url field to the IdP config. That also helps with custom SAML deployments.", "created_at": "2026-06-21T14:00:00Z"},
        {"id": 4, "author": "priya.sharma", "body": "Make sure we add validation that the metadata URL is HTTPS. We don't want to accept plain HTTP metadata.", "created_at": "2026-06-21T15:30:00Z"},
        {"id": 5, "author": "natalie.kim", "body": "Should we also support automatic periodic refresh? Some IdPs rotate their certificates.", "created_at": "2026-06-22T09:00:00Z"},
        {"id": 6, "author": "alex.rivera", "body": "Good idea. I'll add a background task that refreshes metadata every 24h. We'll cache the previous certs for a grace period.", "created_at": "2026-06-22T10:30:00Z"},
    ],
    (1005, 1): [
        {"id": 1, "author": "david.petrov", "body": "This happens when two pipeline runs try to acquire the state lock simultaneously. We need to add a retry mechanism.", "created_at": "2026-06-24T08:00:00Z"},
        {"id": 2, "author": "marcus.chen", "body": "Can we also add a lock timeout parameter? The default 5-minute timeout is too short for our larger applies.", "created_at": "2026-06-24T10:00:00Z"},
    ],
    (1008, 1): [
        {"id": 1, "author": "aisha.patel", "body": "The gradient norm explodes after ~500 steps with lr=5e-3. Adding gradient clipping at 1.0 helps but doesn't fully solve it.", "created_at": "2026-06-22T09:00:00Z"},
        {"id": 2, "author": "marcus.chen", "body": "Have you tried a warmup schedule? Linear warmup for 1000 steps then cosine decay works well for attention models.", "created_at": "2026-06-22T11:00:00Z"},
        {"id": 3, "author": "aisha.patel", "body": "Yes! Warmup + cosine decay with lr=3e-4 peak is stable. Adding it to the base config. Thanks Marcus.", "created_at": "2026-06-22T15:00:00Z"},
    ],
}

# Merge requests / PRs (for submit_by_form, select_by_dropdown context)
_MERGE_REQUESTS = {
    1001: [
        {"id": 847, "title": "feat: add webhook retry logic with exponential backoff", "state": "merged", "author": "natalie.kim", "source_branch": "feature/webhook-retry", "target_branch": "main", "labels": ["feature", "api"], "created_at": "2026-06-23T15:00:00Z", "description": "Implements exponential backoff with jitter for webhook delivery retries."},
        {"id": 851, "title": "refactor: migrate to TaskGroup for structured concurrency", "state": "open", "author": "alex.rivera", "source_branch": "feature/async-workflow-engine", "target_branch": "main", "labels": ["refactor"], "created_at": "2026-06-25T16:00:00Z", "description": "Replaces asyncio.gather with TaskGroup for proper error handling."},
    ],
    1002: [
        {"id": 623, "title": "feat: real-time anomaly scoring pipeline with sliding window aggregation", "state": "merged", "author": "marcus.chen", "source_branch": "feature/anomaly-scoring-v2", "target_branch": "main", "labels": ["feature", "scoring"], "created_at": "2026-06-22T14:00:00Z", "description": "Adds real-time scoring with sliding window aggregation over event streams."},
    ],
    1004: [
        {"id": 312, "title": "feat: add rate limit headers to all API responses", "state": "merged", "author": "alex.rivera", "source_branch": "feature/rate-limit-headers", "target_branch": "main", "labels": ["feature", "gateway"], "created_at": "2026-06-21T15:00:00Z", "description": "Adds X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset headers."},
    ],
    1005: [
        {"id": 198, "title": "infra: deploy PgBouncer connection pooling to staging and production", "state": "merged", "author": "david.petrov", "source_branch": "feature/pgbouncer-pooling", "target_branch": "main", "labels": ["infra", "database"], "created_at": "2026-06-22T14:00:00Z", "description": "Deploys PgBouncer with transaction-mode pooling for all environments."},
    ],
}

# Uploaded files (in-memory storage for upload_by_upload)
_UPLOADED_FILES = {}


# ---------------------------------------------------------------------------
# Additional API routes for macro coverage
# ---------------------------------------------------------------------------

@blueprint.route("/api/search/semantic", methods=["GET"])
def api_search_semantic():
    """Semantic search across repos and activities using keyword overlap scoring.

    Macro: search_by_semantic, extract_by_semantic
    """
    q = request.args.get("q", "").lower().strip()
    if not q:
        return jsonify({"repos": [], "activities": [], "query": ""})

    query_tokens = set(q.split())
    users = _load_users()
    repos = _load_repos()
    activities = _load_activities()

    def _score_text(text):
        text_tokens = set(text.lower().split())
        overlap = query_tokens & text_tokens
        return len(overlap) / max(len(query_tokens), 1)

    scored_repos = []
    for r in repos:
        combined = f"{r['name']} {r.get('description', '')} {' '.join(r.get('tech_stack', []))}"
        score = _score_text(combined)
        if score > 0:
            enriched = _enrich_repo(r, users)
            enriched["relevance_score"] = round(score, 3)
            scored_repos.append(enriched)
    scored_repos.sort(key=lambda x: x["relevance_score"], reverse=True)

    scored_activities = []
    for a in activities:
        combined = f"{a.get('commit_message', '')} {a.get('merge_request_title', '')} {a.get('review_comment', '')}"
        score = _score_text(combined)
        if score > 0:
            enriched = _enrich_activity(a, users)
            enriched["relevance_score"] = round(score, 3)
            scored_activities.append(enriched)
    scored_activities.sort(key=lambda x: x["relevance_score"], reverse=True)

    return jsonify({
        "query": q,
        "repos": scored_repos,
        "activities": scored_activities[:20],
    })


@blueprint.route("/api/search/code", methods=["GET"])
def api_search_code():
    """Search within file contents across all repos.

    Macro: search_by_code
    """
    q = request.args.get("q", "").lower().strip()
    repo_filter = request.args.get("repo", "")
    lang = request.args.get("lang", "")

    if not q:
        return jsonify({"results": [], "query": ""})

    results = []
    for repo_name, files in _FILE_CONTENTS.items():
        if repo_filter and repo_name != repo_filter:
            continue
        for filepath, content in files.items():
            if lang:
                ext = filepath.rsplit(".", 1)[-1] if "." in filepath else ""
                lang_map = {"py": "python", "go": "go", "ts": "typescript", "tf": "terraform", "tsx": "typescript"}
                if lang_map.get(ext, ext) != lang.lower():
                    continue
            if q in content.lower():
                # Find matching lines
                matching_lines = []
                for i, line in enumerate(content.split("\n"), 1):
                    if q in line.lower():
                        matching_lines.append({"line_number": i, "text": line.strip()})
                results.append({
                    "repo": repo_name,
                    "file": filepath,
                    "matches": matching_lines,
                    "match_count": len(matching_lines),
                })
    return jsonify({"results": results, "query": q, "total": len(results)})


@blueprint.route("/api/repos/compare", methods=["GET"])
def api_repos_compare():
    """Compare two or more repos side-by-side in a table format.

    Macro: compare_from_table, extract_from_table
    """
    ids_param = request.args.get("ids", "")
    if not ids_param:
        return jsonify({"error": "Provide repo IDs as ?ids=1001,1002"}), 400

    try:
        repo_ids = [int(x.strip()) for x in ids_param.split(",")]
    except ValueError:
        return jsonify({"error": "Invalid repo ID format"}), 400

    users = _load_users()
    repos = _load_repos()
    comparison = []
    for rid in repo_ids:
        repo = None
        for r in repos:
            if r["id"] == rid:
                repo = r
                break
        if not repo:
            continue
        enriched = _enrich_repo(repo, users)
        commits = _COMMIT_HISTORIES.get(repo["name"], [])
        issues = _ISSUES.get(rid, [])
        enriched["commit_count"] = len(commits)
        enriched["open_issues"] = sum(1 for i in issues if i["state"] == "open")
        enriched["closed_issues"] = sum(1 for i in issues if i["state"] == "closed")
        enriched["latest_commit"] = commits[0]["message"] if commits else ""
        enriched["latest_commit_date"] = commits[0]["date"] if commits else ""
        enriched["total_additions"] = sum(c.get("additions", 0) for c in commits)
        enriched["total_deletions"] = sum(c.get("deletions", 0) for c in commits)
        comparison.append(enriched)

    return jsonify({"repos": comparison, "count": len(comparison)})


@blueprint.route("/api/repos/<int:repo_id>/commits/compare", methods=["GET"])
def api_commits_compare(repo_id):
    """Compare two commits within a repo.

    Macro: compare_from_table
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    sha1 = request.args.get("from", "")
    sha2 = request.args.get("to", "")
    commits = _COMMIT_HISTORIES.get(repo["name"], [])

    commit_a = next((c for c in commits if c["sha"] == sha1), None)
    commit_b = next((c for c in commits if c["sha"] == sha2), None)

    if not commit_a or not commit_b:
        return jsonify({"error": "One or both commit SHAs not found"}), 404

    return jsonify({
        "repo": repo["name"],
        "from": commit_a,
        "to": commit_b,
        "diff_summary": {
            "additions_delta": commit_b["additions"] - commit_a["additions"],
            "deletions_delta": commit_b["deletions"] - commit_a["deletions"],
            "files_changed_delta": commit_b["files_changed"] - commit_a["files_changed"],
        },
    })


@blueprint.route("/api/repos/<int:repo_id>/issues/<int:issue_id>/comments", methods=["GET"])
def api_issue_comments_list(repo_id, issue_id):
    """List comments on an issue.

    Supporting route for post_from_free_text.
    """
    comments = _ISSUE_COMMENTS.get((repo_id, issue_id), [])
    return jsonify({"comments": comments, "total": len(comments)})


@blueprint.route("/api/repos/<int:repo_id>/issues/<int:issue_id>/comments", methods=["POST"])
def api_issue_comments_create(repo_id, issue_id):
    """Post a free-text comment on an issue.

    Macro: post_from_free_text
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    issues = _ISSUES.get(repo_id, [])
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    data = request.get_json(force=True)
    body = data.get("body", "").strip()
    if not body:
        return jsonify({"error": "Comment body is required"}), 400

    comments = _ISSUE_COMMENTS.setdefault((repo_id, issue_id), [])
    max_id = max((c["id"] for c in comments), default=0)
    new_comment = {
        "id": max_id + 1,
        "author": data.get("author", session.get("vc_username", "anonymous")),
        "body": body,
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    comments.append(new_comment)
    issue["comments"] = len(comments)
    return jsonify(new_comment), 201


@blueprint.route("/api/repos/<int:repo_id>/merge_requests", methods=["GET"])
def api_merge_requests_list(repo_id):
    """List merge requests for a repo.

    Supporting route for submit_by_form.
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    mrs = _MERGE_REQUESTS.get(repo_id, [])
    state = request.args.get("state", "")
    if state:
        mrs = [m for m in mrs if m["state"] == state]
    return jsonify({"merge_requests": mrs, "total": len(mrs)})


@blueprint.route("/api/repos/<int:repo_id>/merge_requests", methods=["POST"])
def api_merge_requests_create(repo_id):
    """Create a new merge request (PR).

    Macro: submit_by_form
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    data = request.get_json(force=True)
    mrs = _MERGE_REQUESTS.setdefault(repo_id, [])
    max_id = max((m["id"] for m in mrs), default=0)
    new_mr = {
        "id": max_id + 1,
        "title": data.get("title", "Untitled merge request"),
        "state": "open",
        "author": data.get("author", session.get("vc_username", "unknown")),
        "source_branch": data.get("source_branch", "feature/new-feature"),
        "target_branch": data.get("target_branch", repo["default_branch"]),
        "labels": data.get("labels", []),
        "created_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "description": data.get("description", ""),
    }
    mrs.append(new_mr)
    _add_email(session.get("user_id", 1), "noreply@version-control.lakeport.local",
               "Pull request created",
               f'Merge request "{new_mr["title"]}" has been created targeting {new_mr["target_branch"]}.')
    emit("message", from_user_id=1, to_user_id=1, text=f"New MR: {new_mr['title']} ({new_mr['source_branch']} -> {new_mr['target_branch']})", source_site="version-control")
    return jsonify(new_mr), 201


@blueprint.route("/api/repos/<int:repo_id>/upload", methods=["POST"])
def api_upload_file(repo_id):
    """Upload a file to a repository.

    Macro: upload_by_upload
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file provided"}), 400

    file_path = request.form.get("path", file.filename)
    commit_msg = request.form.get("commit_message", f"Upload {file_path}")
    branch = request.form.get("branch", repo["default_branch"])
    content = file.read().decode("utf-8", errors="replace")

    uploads = _UPLOADED_FILES.setdefault(repo_id, [])
    upload_entry = {
        "id": len(uploads) + 1,
        "path": file_path,
        "size": len(content),
        "branch": branch,
        "commit_message": commit_msg,
        "author": session.get("vc_username", "anonymous"),
        "uploaded_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    uploads.append(upload_entry)

    # Also add to file contents for code search
    _FILE_CONTENTS.setdefault(repo["name"], {})[file_path] = content

    return jsonify(upload_entry), 201


@blueprint.route("/api/repos/<int:repo_id>/uploads", methods=["GET"])
def api_list_uploads(repo_id):
    """List uploaded files for a repo."""
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    uploads = _UPLOADED_FILES.get(repo_id, [])
    return jsonify({"uploads": uploads, "total": len(uploads)})


@blueprint.route("/api/repos/<int:repo_id>/settings", methods=["PUT"])
def api_repo_settings(repo_id):
    """Update repo settings (default branch, visibility, etc.) via dropdown selections.

    Macro: select_by_dropdown, edit_by_form
    """
    repos = _load_repos()
    target = None
    for r in repos:
        if r["id"] == repo_id:
            target = r
            break
    if not target:
        return jsonify({"error": "Repository not found"}), 404

    data = request.get_json(force=True)
    changed = {}
    for field in ("default_branch", "visibility", "namespace"):
        if field in data:
            old = target.get(field)
            target[field] = data[field]
            changed[field] = {"old": old, "new": data[field]}
    target["last_activity"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_repos(repos)
    return jsonify({"repo_id": repo_id, "changes": changed})


@blueprint.route("/api/repos/<int:repo_id>/issues/<int:issue_id>", methods=["PUT"])
def api_issue_update(repo_id, issue_id):
    """Update issue fields (state, labels, title).

    Macro: edit_by_form
    """
    issues = _ISSUES.get(repo_id, [])
    issue = next((i for i in issues if i["id"] == issue_id), None)
    if not issue:
        return jsonify({"error": "Issue not found"}), 404

    data = request.get_json(force=True)
    for field in ("title", "state", "labels"):
        if field in data:
            issue[field] = data[field]
    return jsonify(issue)


@blueprint.route("/api/export/repos", methods=["GET"])
def api_export_repos():
    """Export repository data as JSON or CSV.

    Macro: export_by_route
    """
    fmt = request.args.get("format", "json")
    language = request.args.get("language", "")
    users = _load_users()
    repos = _load_repos()
    enriched = [_enrich_repo(r, users) for r in repos]

    if language:
        enriched = [r for r in enriched if language in r.get("tech_stack", [])]

    if fmt == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "name", "namespace", "description", "visibility",
                         "default_branch", "stars", "forks", "owner_name",
                         "tech_stack", "last_activity"])
        for r in enriched:
            writer.writerow([
                r["id"], r["name"], r["namespace"], r.get("description", ""),
                r.get("visibility", ""), r.get("default_branch", ""),
                r.get("stars", 0), r.get("forks", 0),
                r.get("owner_name", ""),
                ";".join(r.get("tech_stack", [])),
                r.get("last_activity", ""),
            ])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=repos.csv"})

    return jsonify(enriched)


@blueprint.route("/api/export/activity", methods=["GET"])
def api_export_activity():
    """Export activity data as JSON or CSV.

    Macro: export_by_route
    """
    fmt = request.args.get("format", "json")
    users = _load_users()
    activities = _load_activities()
    enriched = [_enrich_activity(a, users) for a in activities]
    enriched.sort(key=lambda a: a.get("created_at", ""), reverse=True)

    repo_filter = request.args.get("repo", "")
    if repo_filter:
        enriched = [a for a in enriched if a.get("repo") == repo_filter]

    if fmt == "csv":
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "type", "author_username", "repo", "commit_message",
                         "merge_request_title", "created_at"])
        for a in enriched:
            writer.writerow([
                a.get("id", ""), a.get("type", ""),
                a.get("author_username", ""), a.get("repo", ""),
                a.get("commit_message", ""), a.get("merge_request_title", ""),
                a.get("created_at", ""),
            ])
        return Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=activity.csv"})

    return jsonify(enriched)


@blueprint.route("/api/repos/<int:repo_id>/files", methods=["GET"])
def api_repo_files(repo_id):
    """Get file tree for a repo, optionally with content.

    Supporting route for extract_by_route, search_by_code.
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    files = _FILE_TREES.get(repo["name"], [])
    include_content = request.args.get("content", "") == "true"

    if include_content:
        contents = _FILE_CONTENTS.get(repo["name"], {})
        return jsonify({"files": files, "content": contents})
    return jsonify({"files": files})


@blueprint.route("/api/repos/<int:repo_id>/file", methods=["GET"])
def api_repo_file_content(repo_id):
    """Get content of a specific file in a repo.

    Supporting route for extract_by_route, search_by_code.
    """
    repo = _repo_by_id(repo_id)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404

    path = request.args.get("path", "")
    if not path:
        return jsonify({"error": "File path required (?path=src/main.py)"}), 400

    contents = _FILE_CONTENTS.get(repo["name"], {})
    if path not in contents:
        return jsonify({"error": f"File not found: {path}"}), 404

    return jsonify({"repo": repo["name"], "path": path, "content": contents[path]})


# ---------------------------------------------------------------------------
# Name-based API routes (lookup by name/username instead of integer ID)
# ---------------------------------------------------------------------------

def _repo_by_name(name):
    """Look up a repository by name (case-insensitive)."""
    repos = _load_repos()
    for r in repos:
        if r["name"].lower() == name.lower():
            return r
    return None


@blueprint.route("/api/repos/by-name/<name>", methods=["GET"])
def api_repo_by_name(name):
    """Get a single repo by name with files, commits, readme, issues."""
    users = _load_users()
    repo = _repo_by_name(name)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    enriched = _enrich_repo(repo, users)
    enriched["files"] = _FILE_TREES.get(repo["name"], [])
    enriched["commits"] = _COMMIT_HISTORIES.get(repo["name"], [])
    enriched["readme"] = _READMES.get(repo["name"], "")
    enriched["issues"] = _ISSUES.get(repo["id"], [])
    return jsonify(enriched)


@blueprint.route("/api/users/by-username/<username>", methods=["GET"])
def api_user_by_username(username):
    """Get a user by username with their repos."""
    user = _user_by_username(username)
    if not user:
        return jsonify({"error": "User not found"}), 404
    repos = _load_repos()
    user_repos = [r for r in repos if r.get("creator_id") == user["root_user_id"]]
    result = dict(user)
    result["repos"] = user_repos
    return jsonify(result)


@blueprint.route("/api/repos/by-name/<name>/tree", methods=["GET"])
def api_repo_tree_by_name(name):
    """List files in a repo by name."""
    repo = _repo_by_name(name)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    files = _FILE_TREES.get(repo["name"], [])
    include_content = request.args.get("content", "") == "true"
    if include_content:
        contents = _FILE_CONTENTS.get(repo["name"], {})
        return jsonify({"repo": repo["name"], "files": files, "content": contents})
    return jsonify({"repo": repo["name"], "files": files})


@blueprint.route("/api/repos/by-name/<name>/issues", methods=["GET"])
def api_repo_issues_by_name(name):
    """List issues for a repo by name."""
    repo = _repo_by_name(name)
    if not repo:
        return jsonify({"error": "Repository not found"}), 404
    issues = _ISSUES.get(repo["id"], [])
    state = request.args.get("state", "")
    if state:
        issues = [i for i in issues if i["state"] == state]
    return jsonify({"repo": repo["name"], "issues": issues, "total": len(issues)})


@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export repos or activity as JSON or CSV.

    Query params:
        type: 'repos' (default) or 'activity'
        format: 'json' (default) or 'csv'
        language: filter repos by language (optional)
        repo: filter activity by repo name (optional)
    """
    export_type = request.args.get("type", "repos").strip()
    if export_type == "activity":
        return api_export_activity()
    return api_export_repos()
