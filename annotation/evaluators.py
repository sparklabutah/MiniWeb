"""Declarative evaluators for MiniWeb tasks.

Three evaluator types inspired by WebArena-Verified (ServiceNow, 2025):
  1. AgentResponseEvaluator — checks agent's text answer
  2. BackendStateEvaluator — checks site API state
  3. GroundingEvaluator — checks agent actually navigated (anti-cheating)

Each evaluator takes a JSON config and returns (passed: bool, detail: str).
No per-task Python code needed — the harness interprets configs at runtime.
"""

import re
import requests
from annotation.normalizers import normalize, normalize_number, normalize_string


# ---------------------------------------------------------------------------
# AgentResponseEvaluator
# ---------------------------------------------------------------------------

def eval_agent_response(agent_answer, config):
    """Check agent's final text answer against expected value(s).

    Config:
        type: string | number | boolean | date | currency | string_list | url
        expected: "107" or ["107", "one hundred seven"]  (alternatives)
    """
    if not agent_answer:
        return False, "Agent gave no answer"

    value_type = config.get("type", "string")
    expected_raw = config.get("expected")
    if expected_raw is None:
        return True, "No expected answer configured"

    # Handle alternatives: expected can be a list of acceptable values
    alternatives = expected_raw if isinstance(expected_raw, list) else [expected_raw]

    # Normalize agent answer
    if value_type == "number":
        actual = normalize_number(agent_answer)
        if actual is None:
            return False, f"Could not extract number from: '{agent_answer[:100]}'"
        for alt in alternatives:
            expected_num = normalize_number(alt)
            if expected_num is not None and abs(actual - expected_num) < 0.01 * max(abs(expected_num), 1):
                return True, f"Number match: {actual} ≈ {expected_num}"
        return False, f"Number mismatch: got {actual}, expected {alternatives}"
    else:
        actual_norm = normalize(agent_answer, value_type)
        for alt in alternatives:
            expected_norm = normalize(alt, value_type)
            if value_type == "string":
                # For strings, check if expected is contained in actual (agent gives verbose answers)
                if expected_norm in actual_norm or actual_norm == expected_norm:
                    return True, f"String match: '{expected_norm}' found in answer"
            else:
                if actual_norm == expected_norm:
                    return True, f"Match: {actual_norm} == {expected_norm}"
        return False, f"Mismatch: got '{actual_norm}', expected {alternatives}"


# ---------------------------------------------------------------------------
# BackendStateEvaluator
# ---------------------------------------------------------------------------

def eval_backend_state(server_url, config, session=None, flask_client=None):
    """Check site API state after task completion.

    Config:
        method: "GET" (default) or "POST"
        endpoint: "/sites/email/api/folders/sent/count"
        field: ".count" or "[0].name" (dot-notation path into JSON response)
        comparison: equals | contains | not_contains | greater_than | less_than |
                    length_equals | exists | not_exists
        expected: value to compare against
        auth: {username, password, login_url} (optional, for authenticated endpoints)
    """
    method = config.get("method", "GET").upper()
    endpoint = config.get("endpoint", "")
    field_path = config.get("field", "")
    comparison = config.get("comparison", "equals")
    expected = config.get("expected")

    if not endpoint:
        return False, "No endpoint configured"

    try:
        if flask_client and endpoint.startswith("/"):
            # Use Flask test client for internal endpoints (shares session/cookies)
            if method == "POST":
                r = flask_client.post(endpoint, json=config.get("body", {}))
            else:
                r = flask_client.get(endpoint)
            if r.status_code >= 400:
                return False, f"HTTP {r.status_code} from {endpoint}"
            data = r.get_json()
        else:
            # External HTTP request
            url = f"{server_url}{endpoint}" if endpoint.startswith("/") else endpoint
            http = session or requests.Session()
            auth = config.get("auth")
            if auth and not session:
                login_url = auth.get("login_url", f"{server_url}/api/login")
                http.post(login_url, json={"username": auth["username"], "password": auth["password"]})
            if method == "POST":
                r = http.post(url, json=config.get("body", {}))
            else:
                r = http.get(url)
            if r.status_code >= 400:
                return False, f"HTTP {r.status_code} from {endpoint}"
            data = r.json()
    except Exception as e:
        return False, f"Error calling {endpoint}: {e}"

    # Extract field value using dot-notation path
    actual = _extract_field(data, field_path)

    # Compare
    return _compare(actual, expected, comparison)


def _extract_field(data, path):
    """Extract value from JSON using dot-notation path. e.g. '.count', '[0].name', 'length'"""
    if not path or path == ".":
        return data

    if path == "length":
        return len(data) if isinstance(data, (list, dict)) else None

    parts = re.split(r"\.(?![^\[]*\])", path.lstrip("."))
    current = data
    for part in parts:
        if not part:
            continue
        # Array index: [0], [1], etc
        idx_match = re.match(r"\[(\d+)\](.*)", part)
        if idx_match:
            idx = int(idx_match.group(1))
            rest = idx_match.group(2).lstrip(".")
            if isinstance(current, (list, tuple)) and idx < len(current):
                current = current[idx]
                if rest:
                    current = _extract_field(current, rest)
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _compare(actual, expected, comparison):
    """Compare actual vs expected using the specified operator."""
    if comparison == "equals":
        if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            passed = abs(actual - expected) < 0.01 * max(abs(expected), 1)
        else:
            passed = normalize_string(str(actual)) == normalize_string(str(expected))
        return passed, f"equals: actual={actual}, expected={expected}"

    elif comparison == "contains":
        if isinstance(actual, str):
            passed = normalize_string(expected) in normalize_string(actual)
        elif isinstance(actual, (list, tuple)):
            passed = any(normalize_string(str(expected)) == normalize_string(str(v)) for v in actual)
        else:
            passed = False
        return passed, f"contains '{expected}': {passed}"

    elif comparison == "not_contains":
        if isinstance(actual, str):
            passed = normalize_string(expected) not in normalize_string(actual)
        elif isinstance(actual, (list, tuple)):
            passed = all(normalize_string(str(expected)) != normalize_string(str(v)) for v in actual)
        else:
            passed = True
        return passed, f"not_contains '{expected}': {passed}"

    elif comparison == "greater_than":
        a = normalize_number(actual)
        e = normalize_number(expected)
        passed = a is not None and e is not None and a > e
        return passed, f"greater_than: {a} > {e}"

    elif comparison == "less_than":
        a = normalize_number(actual)
        e = normalize_number(expected)
        passed = a is not None and e is not None and a < e
        return passed, f"less_than: {a} < {e}"

    elif comparison == "length_equals":
        length = len(actual) if isinstance(actual, (list, tuple, dict, str)) else None
        passed = length == int(expected)
        return passed, f"length_equals: len={length}, expected={expected}"

    elif comparison == "exists":
        passed = actual is not None and actual != "" and actual != []
        return passed, f"exists: {actual is not None}"

    elif comparison == "not_exists":
        passed = actual is None or actual == "" or actual == []
        return passed, f"not_exists: {actual is None or actual == ''}"

    return False, f"Unknown comparison: {comparison}"


# ---------------------------------------------------------------------------
# GroundingEvaluator
# ---------------------------------------------------------------------------

def eval_grounding(navigation_trace, config):
    """Verify agent actually visited required pages (anti-cheating).

    Config:
        required_urls: ["/sites/e-commerce/", "/sites/e-commerce/product/42"]
        required_actions: ["POST /sites/e-commerce/cart/add"]  (optional)
        check_order: true/false (whether URL visit order matters)
        check_referer: {"/sites/e-commerce/product/42": "/sites/e-commerce/"}  (optional)

    navigation_trace: list of dicts with keys: url, method, referer, timestamp
    """
    if not config:
        return True, "No grounding check configured"

    required_urls = config.get("required_urls", [])
    required_actions = config.get("required_actions", [])
    check_order = config.get("check_order", False)
    check_referer = config.get("check_referer", {})

    if not navigation_trace:
        if required_urls or required_actions:
            return False, "No navigation trace available"
        return True, "No navigation required"

    visited_urls = [e.get("url", "") for e in navigation_trace]

    # Check required URLs were visited
    missing_urls = []
    last_found_idx = -1
    for req_url in required_urls:
        found = False
        for i, visited in enumerate(visited_urls):
            if req_url in visited or visited.endswith(req_url):
                if check_order and i <= last_found_idx:
                    missing_urls.append(f"{req_url} (out of order)")
                else:
                    last_found_idx = i
                    found = True
                    break
        if not found:
            missing_urls.append(req_url)

    if missing_urls:
        return False, f"Missing navigations: {missing_urls}"

    # Check required actions (POST/PUT/DELETE)
    if required_actions:
        trace_actions = [f"{e.get('method', 'GET')} {e.get('url', '')}" for e in navigation_trace]
        missing_actions = []
        for req_action in required_actions:
            found = any(req_action in ta for ta in trace_actions)
            if not found:
                missing_actions.append(req_action)
        if missing_actions:
            return False, f"Missing actions: {missing_actions}"

    # Check referers
    if check_referer:
        for target_url, expected_referer in check_referer.items():
            for event in navigation_trace:
                if target_url in event.get("url", ""):
                    actual_referer = event.get("referer", "")
                    if expected_referer not in actual_referer:
                        return False, f"Wrong referer for {target_url}: got '{actual_referer}', expected '{expected_referer}'"

    return True, f"Grounding verified: {len(required_urls)} URLs, {len(required_actions)} actions"


# ---------------------------------------------------------------------------
# Unified evaluator runner
# ---------------------------------------------------------------------------

def run_eval(config, agent_answer=None, server_url=None, navigation_trace=None, session=None, flask_client=None):
    """Run a single evaluator config block. Returns (passed, detail)."""
    evaluator = config.get("evaluator", "")

    if evaluator == "AgentResponseEvaluator":
        return eval_agent_response(agent_answer, config)
    elif evaluator == "BackendStateEvaluator":
        return eval_backend_state(server_url, config, session=session, flask_client=flask_client)
    elif evaluator == "GroundingEvaluator":
        return eval_grounding(navigation_trace, config)
    else:
        return False, f"Unknown evaluator: {evaluator}"


def run_task_eval(eval_configs, eval_logic="all", **kwargs):
    """Run all evaluator configs for a task. Returns (passed, details_list)."""
    if not eval_configs:
        return True, [("no_eval", True, "No eval configured")]

    results = []
    for cfg in eval_configs:
        passed, detail = run_eval(cfg, **kwargs)
        results.append((cfg.get("evaluator", "unknown"), passed, detail))

    if eval_logic == "all":
        overall = all(r[1] for r in results)
    elif eval_logic == "any":
        overall = any(r[1] for r in results)
    else:
        overall = all(r[1] for r in results)

    return overall, results
