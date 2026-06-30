#!/usr/bin/env python3
"""Chain walker library — Flask test client + HTML→ax_tree parser.

Provides a CLI for Claude Code agents to interact with MiniWeb sites
step-by-step. The agent IS the LLM — no separate API calls needed.

Usage from a Claude Code agent (via Bash):

  # Start a session, get the homepage ax_tree
  python scripts/chain_walker_lib.py observe --site banking

  # Navigate to a page
  python scripts/chain_walker_lib.py get --site banking --url /sites/banking/transactions

  # Submit a form
  python scripts/chain_walker_lib.py post --site banking --url /sites/banking/login \
      --data '{"username":"james_smith","password":"secure111"}'

  # POST JSON to an API
  python scripts/chain_walker_lib.py post_json --site banking --url /sites/banking/api/transfer \
      --data '{"from_account":1,"to_account":2,"amount":100}'

  # Get credentials for a site
  python scripts/chain_walker_lib.py creds --site banking

  # Get known routes for a site
  python scripts/chain_walker_lib.py routes --site banking

  # Save a chain walk result
  python scripts/chain_walker_lib.py save --chain-id banking_easy_001 \
      --result '{"valid":true,...}'
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
DATA_SOURCES_DIR = PROJECT_ROOT / "data_sources"
CHAINS_DIR = PROJECT_ROOT / "annotation" / "chains"
RUNS_DIR = PROJECT_ROOT / "annotation" / "chain_runs"

# Persistent Flask test client across calls (via session file)
_SESSION_DIR = PROJECT_ROOT / "annotation" / ".walker_sessions"


# ---------------------------------------------------------------------------
# HTML → Accessibility Tree
# ---------------------------------------------------------------------------

class AXTreeBuilder(HTMLParser):
    """Parse HTML into a simplified accessibility tree."""

    SKIP_TAGS = {"script", "style", "svg", "noscript", "head"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.headings = []
        self.links = []
        self.forms = []
        self.tables = []
        self.nav_items = []
        self.text_blocks = []

        self._skip_depth = 0
        self._in_title = False
        self._current_form = None
        self._current_table = None
        self._current_row = []
        self._current_heading = None
        self._heading_text = ""
        self._in_nav = False
        self._current_select = None
        self._current_option_text = ""
        self._in_option = False
        self._link_text = ""
        self._current_link = None
        self._text_buffer = []
        self._in_textarea = False
        self._textarea_name = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        tag = tag.lower()

        if self._skip_depth > 0:
            if tag in self.SKIP_TAGS:
                self._skip_depth += 1
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
            return

        if tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._current_heading = tag
            self._heading_text = ""
        elif tag == "a":
            href = attrs_dict.get("href", "")
            self._current_link = href
            self._link_text = ""
        elif tag == "nav":
            self._in_nav = True
        elif tag == "form":
            self._current_form = {
                "action": attrs_dict.get("action", ""),
                "method": attrs_dict.get("method", "GET").upper(),
                "id": attrs_dict.get("id", ""),
                "inputs": [],
                "selects": [],
                "buttons": [],
                "textareas": [],
            }
        elif tag == "input" and self._current_form is not None:
            self._current_form["inputs"].append({
                "type": attrs_dict.get("type", "text"),
                "name": attrs_dict.get("name", ""),
                "value": attrs_dict.get("value", ""),
                "placeholder": attrs_dict.get("placeholder", ""),
            })
        elif tag == "select":
            self._current_select = {
                "name": attrs_dict.get("name", ""),
                "id": attrs_dict.get("id", ""),
                "options": [],
            }
        elif tag == "option" and self._current_select is not None:
            self._in_option = True
            self._current_option_text = ""
            self._current_select["options"].append({
                "value": attrs_dict.get("value", ""),
                "text": "",
                "selected": "selected" in attrs_dict,
            })
        elif tag == "button":
            if self._current_form is not None:
                self._current_form["buttons"].append({
                    "type": attrs_dict.get("type", "submit"),
                    "text": "",
                    "name": attrs_dict.get("name", ""),
                    "value": attrs_dict.get("value", ""),
                })
        elif tag == "textarea":
            self._in_textarea = True
            self._textarea_name = attrs_dict.get("name", "")
        elif tag == "table":
            self._current_table = {"headers": [], "rows": []}
        elif tag == "th" and self._current_table is not None:
            self._current_row.append("")
        elif tag == "td" and self._current_table is not None:
            self._current_row.append("")
        elif tag == "tr" and self._current_table is not None:
            self._current_row = []

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            return

        if tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._current_heading:
            self.headings.append({
                "level": int(self._current_heading[1]),
                "text": self._heading_text.strip(),
            })
            self._current_heading = None
        elif tag == "a" and self._current_link is not None:
            text = self._link_text.strip()
            if text and self._current_link:
                if self._in_nav:
                    self.nav_items.append({"text": text, "href": self._current_link})
                else:
                    self.links.append({"text": text, "href": self._current_link})
            self._current_link = None
        elif tag == "nav":
            self._in_nav = False
        elif tag == "form" and self._current_form is not None:
            self.forms.append(self._current_form)
            self._current_form = None
        elif tag == "select" and self._current_select is not None:
            if self._current_form is not None:
                self._current_form["selects"].append(self._current_select)
            self._current_select = None
        elif tag == "option":
            if self._in_option and self._current_select is not None:
                if self._current_select["options"]:
                    self._current_select["options"][-1]["text"] = self._current_option_text.strip()
            self._in_option = False
        elif tag == "textarea":
            if self._in_textarea and self._current_form is not None:
                self._current_form["textareas"].append({"name": self._textarea_name})
            self._in_textarea = False
        elif tag == "table" and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None
        elif tag == "tr" and self._current_table is not None:
            if self._current_row:
                if not self._current_table["headers"]:
                    self._current_table["headers"] = [c.strip() for c in self._current_row]
                else:
                    self._current_table["rows"].append([c.strip() for c in self._current_row])
            self._current_row = []
        elif tag in ("p", "div", "li", "dd", "dt", "blockquote"):
            if self._text_buffer:
                text = " ".join(self._text_buffer).strip()
                if text and len(text) > 5:
                    self.text_blocks.append(text)
                self._text_buffer = []

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title += text
        elif self._current_heading:
            self._heading_text += " " + text
        elif self._current_link is not None:
            self._link_text += " " + text
        elif self._in_option:
            self._current_option_text += text
        elif self._current_form and self._current_form.get("buttons"):
            self._current_form["buttons"][-1]["text"] += text
        elif self._current_table is not None and self._current_row is not None:
            if self._current_row:
                self._current_row[-1] += " " + text
            else:
                self._current_row.append(text)
        else:
            self._text_buffer.append(text)


def html_to_axtree(html: str) -> dict:
    """Convert HTML string to accessibility tree dict."""
    parser = AXTreeBuilder()
    try:
        parser.feed(html)
    except Exception:
        pass

    for table in parser.tables:
        table["rows"] = table["rows"][:5]
    return {
        "title": parser.title.strip(),
        "headings": parser.headings,
        "nav": parser.nav_items[:20],
        "links": parser.links[:50],
        "forms": parser.forms,
        "tables": parser.tables[:5],
        "text": parser.text_blocks[:30],
    }


def axtree_to_text(axtree: dict) -> str:
    """Render ax_tree as human-readable text for the agent."""
    lines = []

    if axtree.get("title"):
        lines.append(f"Page Title: {axtree['title']}")
        lines.append("")

    if axtree.get("headings"):
        lines.append("== Headings ==")
        for h in axtree["headings"]:
            indent = "  " * (h["level"] - 1)
            lines.append(f"{indent}[H{h['level']}] {h['text']}")
        lines.append("")

    if axtree.get("nav"):
        lines.append("== Navigation ==")
        for item in axtree["nav"]:
            lines.append(f"  [{item['text']}] -> {item['href']}")
        lines.append("")

    if axtree.get("forms"):
        lines.append("== Forms ==")
        for i, form in enumerate(axtree["forms"]):
            lines.append(f"  Form #{i+1}: action={form['action']} method={form['method']}")
            for inp in form.get("inputs", []):
                lines.append(
                    f"    <input type={inp['type']} name={inp['name']} "
                    f"placeholder=\"{inp['placeholder']}\" value=\"{inp['value']}\">"
                )
            for sel in form.get("selects", []):
                opts = [f"{o['text']}({o['value']})" for o in sel["options"][:10]]
                lines.append(f"    <select name={sel['name']}> options: {', '.join(opts)}")
            for ta in form.get("textareas", []):
                lines.append(f"    <textarea name={ta['name']}>")
            for btn in form.get("buttons", []):
                lines.append(f"    <button type={btn['type']}>{btn['text'].strip()}</button>")
        lines.append("")

    if axtree.get("tables"):
        lines.append("== Tables ==")
        for i, table in enumerate(axtree["tables"]):
            if table["headers"]:
                lines.append(f"  Table #{i+1} headers: {' | '.join(table['headers'])}")
                for row in table["rows"][:3]:
                    lines.append(f"    {' | '.join(row)}")
                if len(table["rows"]) > 3:
                    lines.append(f"    ... ({len(table['rows'])} rows total)")
        lines.append("")

    if axtree.get("links"):
        lines.append("== Links ==")
        for link in axtree["links"][:30]:
            lines.append(f"  [{link['text'][:60]}] -> {link['href']}")
        lines.append("")

    if axtree.get("text"):
        lines.append("== Page Text (excerpt) ==")
        for block in axtree["text"][:15]:
            lines.append(f"  {block[:200]}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Site helpers
# ---------------------------------------------------------------------------

def get_site_credentials(site_id: str) -> dict | None:
    """Get first user's login credentials for a site."""
    for subdir in ["", ".pristine"]:
        users_file = DATA_SOURCES_DIR / site_id / subdir / "users.json"
        if users_file.exists():
            try:
                users = json.loads(users_file.read_text())
                if isinstance(users, list) and users:
                    u = users[0]
                    return {"username": u.get("username", u.get("email", "")),
                            "password": u.get("password", "")}
                elif isinstance(users, dict):
                    for k, v in users.items():
                        if isinstance(v, dict):
                            return {"username": v.get("username", v.get("email", k)),
                                    "password": v.get("password", "")}
            except (json.JSONDecodeError, OSError):
                pass
    return None


def get_site_routes(site_id: str) -> list[str]:
    """Extract route patterns from a site's routes.py."""
    routes_file = SITES_DIR / site_id / "routes.py"
    if not routes_file.exists():
        return []
    try:
        content = routes_file.read_text()
        return re.findall(r'@\w+\.route\(["\']([^"\']+)', content)[:30]
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Flask app + test client (created once per process)
# ---------------------------------------------------------------------------

_app = None
_client = None


def _get_app():
    global _app
    if _app is None:
        sys.path.insert(0, str(PROJECT_ROOT))
        os.chdir(str(PROJECT_ROOT))
        from app import create_app
        _app = create_app()
        _app.config["TESTING"] = True
    return _app


def _get_client():
    global _client
    if _client is None:
        app = _get_app()
        _client = app.test_client()
        _client.__enter__()
    return _client


def do_reset():
    """Reset data overlay."""
    client = _get_client()
    client.post("/_reset_data")
    return {"status": "reset"}


def do_get(url: str) -> dict:
    """GET a URL, return ax_tree + metadata."""
    client = _get_client()
    resp = client.get(url, follow_redirects=True)
    html = resp.data.decode("utf-8", errors="replace")
    axtree = html_to_axtree(html)
    return {
        "status_code": resp.status_code,
        "url": url,
        "ax_tree_text": axtree_to_text(axtree),
        "ax_tree": axtree,
    }


def do_post(url: str, data: dict) -> dict:
    """POST form data, return ax_tree + metadata."""
    client = _get_client()
    resp = client.post(url, data=data, follow_redirects=True)
    html = resp.data.decode("utf-8", errors="replace")
    axtree = html_to_axtree(html)
    return {
        "status_code": resp.status_code,
        "url": url,
        "ax_tree_text": axtree_to_text(axtree),
        "ax_tree": axtree,
    }


def do_post_json(url: str, data: dict) -> dict:
    """POST JSON, return response text + metadata."""
    client = _get_client()
    resp = client.post(url, data=json.dumps(data),
                       content_type="application/json", follow_redirects=True)
    text = resp.data.decode("utf-8", errors="replace")
    # Try to parse as JSON for cleaner output
    try:
        parsed = json.loads(text)
        return {"status_code": resp.status_code, "url": url, "response": parsed}
    except json.JSONDecodeError:
        axtree = html_to_axtree(text)
        return {"status_code": resp.status_code, "url": url,
                "ax_tree_text": axtree_to_text(axtree), "ax_tree": axtree}


def do_get_api(url: str) -> dict:
    """GET an API endpoint, return parsed JSON or raw text."""
    client = _get_client()
    resp = client.get(url)
    text = resp.data.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
        # Truncate large responses
        text_repr = json.dumps(parsed, indent=2)
        if len(text_repr) > 3000:
            text_repr = text_repr[:3000] + "\n... (truncated)"
        return {"status_code": resp.status_code, "url": url,
                "response": parsed if len(text_repr) < 3000 else None,
                "response_text": text_repr}
    except json.JSONDecodeError:
        return {"status_code": resp.status_code, "url": url, "response_text": text[:2000]}


def save_chain_result(chain_id: str, site_id: str, result: dict):
    """Save chain walk result to annotation/chain_runs/<site>/<chain_id>/."""
    run_dir = RUNS_DIR / site_id / chain_id
    run_dir.mkdir(parents=True, exist_ok=True)

    trajectory = result.pop("trajectory", [])
    (run_dir / "status.json").write_text(json.dumps(result, indent=2))
    (run_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2))


# ---------------------------------------------------------------------------
# CLI interface for Claude Code agents
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Chain walker CLI for Claude Code agents")
    sub = parser.add_subparsers(dest="command")

    # observe: GET homepage
    p_obs = sub.add_parser("observe", help="GET site homepage and show ax_tree")
    p_obs.add_argument("--site", required=True)

    # get: GET any URL
    p_get = sub.add_parser("get", help="GET a URL and show ax_tree")
    p_get.add_argument("--url", required=True)

    # post: POST form data
    p_post = sub.add_parser("post", help="POST form data")
    p_post.add_argument("--url", required=True)
    p_post.add_argument("--data", required=True, help="JSON string of form data")

    # post_json: POST JSON
    p_pj = sub.add_parser("post_json", help="POST JSON data")
    p_pj.add_argument("--url", required=True)
    p_pj.add_argument("--data", required=True, help="JSON string")

    # api: GET API endpoint
    p_api = sub.add_parser("api", help="GET an API endpoint")
    p_api.add_argument("--url", required=True)

    # creds: show credentials
    p_creds = sub.add_parser("creds", help="Show site credentials")
    p_creds.add_argument("--site", required=True)

    # routes: show known routes
    p_routes = sub.add_parser("routes", help="Show site route patterns")
    p_routes.add_argument("--site", required=True)

    # reset: reset data overlay
    p_reset = sub.add_parser("reset", help="Reset data overlay")

    # chains: list chains for a site
    p_chains = sub.add_parser("chains", help="List chains for a site")
    p_chains.add_argument("--site", required=True)
    p_chains.add_argument("--difficulty", choices=["easy", "medium", "hard"])
    p_chains.add_argument("--max", type=int, default=None)
    p_chains.add_argument("--skip-done", action="store_true", default=True)

    # save: save a chain result
    p_save = sub.add_parser("save", help="Save chain walk result")
    p_save.add_argument("--chain-id", required=True)
    p_save.add_argument("--site", required=True)
    p_save.add_argument("--result", required=True, help="JSON string of result")

    args = parser.parse_args()

    if args.command == "observe":
        result = do_get(f"/sites/{args.site}/")
        print(result["ax_tree_text"])

    elif args.command == "get":
        result = do_get(args.url)
        print(f"[HTTP {result['status_code']}]")
        print(result["ax_tree_text"])

    elif args.command == "post":
        data = json.loads(args.data)
        result = do_post(args.url, data)
        print(f"[HTTP {result['status_code']}]")
        print(result.get("ax_tree_text", ""))

    elif args.command == "post_json":
        data = json.loads(args.data)
        result = do_post_json(args.url, data)
        print(f"[HTTP {result['status_code']}]")
        if "response" in result:
            print(json.dumps(result["response"], indent=2)[:2000])
        else:
            print(result.get("ax_tree_text", ""))

    elif args.command == "api":
        result = do_get_api(args.url)
        print(f"[HTTP {result['status_code']}]")
        print(result.get("response_text", "")[:3000])

    elif args.command == "creds":
        creds = get_site_credentials(args.site)
        if creds:
            print(json.dumps(creds))
        else:
            print("No credentials found")

    elif args.command == "routes":
        routes = get_site_routes(args.site)
        base = f"/sites/{args.site}"
        for r in routes:
            print(f"  {base}{r}")

    elif args.command == "reset":
        print(json.dumps(do_reset()))

    elif args.command == "chains":
        chain_file = CHAINS_DIR / f"{args.site}.json"
        if not chain_file.exists():
            print(f"No chains for {args.site}")
            return
        chains = json.loads(chain_file.read_text())
        if args.difficulty:
            chains = [c for c in chains if c["difficulty"] == args.difficulty]
        if args.skip_done:
            chains = [c for c in chains
                      if not (RUNS_DIR / args.site / c["chain_id"] / "status.json").exists()]
        if args.max:
            chains = chains[:args.max]
        for c in chains:
            print(json.dumps(c))

    elif args.command == "save":
        result = json.loads(args.result)
        save_chain_result(args.chain_id, args.site, result)
        print(f"Saved to {RUNS_DIR / args.site / args.chain_id}/")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
