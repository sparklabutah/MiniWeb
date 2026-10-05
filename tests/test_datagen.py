"""datagen pure logic: the executor's action wrapper (policy enforcement), coordinate
conventions + jitter + drag paths, backend checks, sampler stratification/caps/dedup,
the filter's dedup/cap/failure pool, the site split, and the training export."""
import json
import random

import pytest

from datagen import actions as A
from datagen import checks


# ── fakes ─────────────────────────────────────────────────────────────────────

class FakeDriver(A.Driver):
    def __init__(self, elements, vp=(1000, 800)):
        self.els, self.vp = elements, vp
        self.scroll_y, self.log, self.shots = 0, [], 0
        self.covered, self.stale = set(), set()

    def viewport(self):
        return self.vp

    def _info(self, key):
        if key in self.stale:
            return None
        i = dict(self.els[key])
        b = i["box"]
        i["box"] = [b[0], b[1] - self.scroll_y, b[2], b[3]]
        return i

    def query(self, css=None, text=None, tag=None, limit=20):
        return [(k, self._info(k)) for k, v in self.els.items()
                if (css is None or v.get("css") == css) and (text is None or text.lower() in v.get("text", "").lower())][:limit]

    def info(self, key):
        return self._info(key)

    def hit(self, key, x, y):
        return key not in self.covered

    def scroll_box(self, key):
        return None

    def focused(self):
        return None

    def screenshot(self):
        self.shots += 1
        return b"\x89PNG\r\n\x1a\nfake"

    def click(self, x, y, button="left", clicks=1):
        self.log.append(("click", x, y))

    def move(self, x, y, steps=1):
        self.log.append(("move", x, y))

    def down(self):
        self.log.append(("down",))

    def up(self):
        self.log.append(("up",))

    def wheel(self, x, y, dx, dy):
        self.scroll_y += dy
        self.log.append(("wheel", dy))

    def press(self, key):
        self.log.append(("key", key))

    def type(self, text):
        self.log.append(("type", text))

    def settle(self):
        pass

    def url(self):
        return "http://localhost:8300/sites/x/"

    def title(self):
        return "x"

    def outline(self, limit=80):
        return ""


def _els():
    return {
        "sel": {"tag": "select", "css": "select[name=cat]", "text": "All", "visible": True, "box": [100, 100, 200, 30]},
        "btn": {"tag": "button", "css": "#go", "text": "Apply", "visible": True, "box": [100, 1500, 120, 40]},
        "hid": {"tag": "button", "css": "#hid", "text": "Hidden", "visible": False, "box": [0, 0, 0, 0]},
    }


@pytest.fixture
def env(tmp_path):
    drv = FakeDriver(_els())
    s = A.Session(drv, A.Recorder(tmp_path, drv.vp), random.Random(1), max_actions=10, time_budget=60)
    return drv, s, A.Dom(s), A.Act(s)


# ── sandbox (static + runtime) ────────────────────────────────────────────────

@pytest.mark.parametrize("code", [
    "import os",
    "from playwright.sync_api import sync_playwright",
    "page.evaluate('1')",
    "act._s.driver.page.goto('http://x')",
    "x = act.__class__",
    "while True:\n    pass",
    "getattr(act, 'click')",
    "dom.one('a').fill('x')",
    "act.goto('http://evil')",
    "class X:\n    pass",
    "open('/etc/passwd')",
    "type(act)",
])
def test_script_policy_rejects_escape_hatches(code):
    with pytest.raises(A.PolicyViolation):
        A.validate_script(code)


def test_script_policy_accepts_a_normal_script():
    A.validate_script("sel = dom.one(css='select')\nfor _ in range(3):\n    act.press('ArrowDown')\n"
                      "act.press('Enter')\nexpect.backend()")


def test_run_script_has_no_dangerous_builtins_and_caps_range(env):
    drv, s, dom, act = env
    logs = []
    A.run_script("print('hi', len([1, 2]))", act=act, dom=dom, expect=None, task={}, log=logs.append)
    assert logs == ["hi 2"]
    with pytest.raises(A.PolicyViolation):
        A.run_script("for i in range(10**6):\n    pass", act=act, dom=dom, expect=None, task={}, log=logs.append)
    # a script's `except Exception` cannot swallow a policy violation
    with pytest.raises(A.PolicyViolation):
        A.run_script("try:\n    act.click(dom.one(css='#go').box)\nexcept Exception:\n    pass",
                     act=act, dom=dom, expect=None, task={}, log=logs.append)


def test_script_must_assert_backend(env):
    drv, s, dom, act = env
    calls = []
    exp = A.Expect(s, lambda: (calls.append(1) or True, "ok"))
    with pytest.raises(A.PolicyViolation, match="expect.backend"):
        A.run_script("act.press('Enter')", act=act, dom=dom, expect=exp, task={}, log=print)
    A.run_script("act.press('Enter')\nexpect.backend()", act=act, dom=dom, expect=exp, task={}, log=print)
    assert calls
    bad = A.Expect(s, lambda: (False, "no request"))
    with pytest.raises(AssertionError):
        A.run_script("expect.backend()", act=act, dom=dom, expect=bad, task={}, log=print)


@pytest.mark.parametrize("key", ["Enter", "ArrowDown", "a", "Control+a", "Shift+Tab", " "])
def test_allowed_keys(key):
    assert A.check_key(key) == key


@pytest.mark.parametrize("key", ["F5", "Control+r", "Alt+ArrowLeft", "Control+l", "Meta+w", ""])
def test_browser_shortcuts_are_violations(key):
    with pytest.raises(A.PolicyViolation):
        A.check_key(key)


# ── the action wrapper ────────────────────────────────────────────────────────

def test_click_records_screenshot_before_and_point_inside_box(env, tmp_path):
    drv, s, dom, act = env
    sel = dom.one(css="select[name=cat]")
    step = act.click(sel)
    assert drv.shots == 1 and (tmp_path / step["screenshot"]).exists()
    assert A.Box(100, 100, 200, 30).contains(step["x"], step["y"])
    assert drv.log[-1][0] == "click" and step["type"] == "click" and step["target"]["tag"] == "select"


def test_hidden_offscreen_occluded_stale_targets_are_refused(env):
    drv, s, dom, act = env
    hidden = dom.find(css="#hid")[0]
    with pytest.raises(A.ActionError, match="hidden"):
        act.click(hidden)
    btn = dom.one(css="#go")                      # y=1500: below the 800px viewport
    with pytest.raises(A.ActionError, match="off-screen"):
        act.click(btn)
    sel = dom.one(css="select[name=cat]")
    drv.covered.add("sel")
    with pytest.raises(A.ActionError, match="covered"):
        act.click(sel)
    drv.stale.add("sel")                          # the page changed under the script
    with pytest.raises(A.ActionError, match="stale"):
        act.click(sel)
    assert s.rec.steps == [] and not any(x[0] == "click" for x in drv.log)


def test_forged_or_foreign_targets_are_violations(env, tmp_path):
    drv, s, dom, act = env
    sel = dom.one(css="select[name=cat]")
    with pytest.raises(A.PolicyViolation):
        act.click(sel.box)                        # a Box is not a target
    other = A.Session(drv, A.Recorder(tmp_path / "o", drv.vp), random.Random(0))
    with pytest.raises(A.PolicyViolation):
        act.click(A.Dom(other).one(css="select[name=cat]"))   # element from another session
    with pytest.raises(A.PolicyViolation):
        sel.text = "x"                            # El is read-only


def test_scroll_into_view_is_recorded_then_click_works(env):
    drv, s, dom, act = env
    btn = act.scroll_into_view(dom.one(css="#go"))
    scrolls = [st for st in s.rec.steps if st["type"] == "scroll"]
    assert scrolls and all(st["dy"] > 0 for st in scrolls)
    assert btn.in_viewport
    step = act.click(btn)
    assert A.Box(*btn.box.as_list()).contains(step["x"], step["y"])
    assert drv.shots == len(s.rec.steps)          # one screenshot per recorded action


def test_action_budget_is_enforced(env):
    drv, s, dom, act = env
    for _ in range(10):
        act.press("ArrowDown")
    with pytest.raises(A.PolicyViolation):
        act.press("ArrowDown")


# ── coordinates, jitter, drags ────────────────────────────────────────────────

def test_coordinate_conventions():
    vp = (1280, 800)
    norm = A.CoordConvention("normalized", scale=1000)
    assert norm.point(640, 400, vp) == (500, 500)
    assert norm.point(-5, 900, vp) == (0, 1000)                 # clamped
    pix = A.CoordConvention("pixel", resolution=(640, 400))
    assert pix.point(640, 400, vp) == (320, 200)
    assert A.CoordConvention("pixel").point(12.4, 7.6, vp) == (12, 8)
    x, y = norm.inverse(*norm.point(333, 222, vp), vp)
    assert abs(x - 333) <= 1.3 and abs(y - 222) <= 0.8
    assert A.CoordConvention.from_dict(pix.to_dict()).resolution == (640, 400)
    with pytest.raises(ValueError):
        A.CoordConvention("polar")


def test_to_student_strips_privileged_fields():
    vp = (1000, 1000)
    conv = A.CoordConvention("normalized", 1000)
    click = {"type": "click", "x": 100, "y": 200, "button": "left", "target": {"css": "#secret"}, "url": "u"}
    assert A.to_student(click, conv, vp) == {"type": "click", "x": 100, "y": 200}
    assert A.to_student({"type": "scroll", "x": 500, "y": 500, "dx": 0, "dy": 250}, conv, vp)["dy"] == 250
    assert A.to_student({"type": "key", "key": "Enter"}, conv, vp) == {"type": "key", "key": "Enter"}
    assert A.to_student({"type": "type", "text": "Spo"}, conv, vp) == {"type": "type", "text": "Spo"}
    d = A.to_student({"type": "drag", "x": 0, "y": 0, "x2": 1000, "y2": 500, "path": [[1, 2]]}, conv, vp)
    assert d == {"type": "drag", "x": 0, "y": 0, "x2": 1000, "y2": 500}


def test_jitter_stays_inside_the_inset_box_and_varies():
    box = A.Box(10, 20, 200, 40)
    rng = random.Random(3)
    pts = [A.jitter_point(box, rng) for _ in range(2000)]
    assert all(10 + 40 - 1e-6 <= x <= 210 - 40 + 1e-6 and 20 + 8 - 1e-6 <= y <= 60 - 8 + 1e-6 for x, y in pts)
    assert len(set(pts)) > 500
    assert [A.jitter_point(box, random.Random(5)) for _ in range(3)] == [A.jitter_point(box, random.Random(5)) for _ in range(3)]
    assert A.jitter_point(A.Box(5, 5, 1, 1), rng) == (5.5, 5.5)


def test_drag_path_endpoints_and_waypoints():
    rng = random.Random(0)
    path = A.drag_path((10, 10), (300, 200), rng, waypoints=(3, 7))
    assert path[0][:2] == (10, 10) and path[-1][:2] == (300, 200)
    assert 5 <= len(path) <= 9 and all(p[2] >= 1 for p in path)
    assert len({p[:2] for p in path}) == len(path)


# ── backend checks ────────────────────────────────────────────────────────────

def _e(path, status=200, method="GET", **query):
    return {"method": method, "path": path, "query": query, "status": status, "timestamp": "2026-09-27T10:00:00+00:00"}


def test_check_needs_param_keep_and_final_state():
    chk = checks.build_check({"method": "GET", "path": "/sites/s/", "param": "category"}, "Toys", keep={"sort": "new"})
    assert not checks.evaluate(chk, [_e("/sites/s/")])[0]
    assert not checks.evaluate(chk, [_e("/sites/s/", category="Toys")])[0]                  # keep lost
    assert checks.evaluate(chk, [_e("/sites/s", category="toys", sort="new")])[0]           # case/slash tolerant
    assert not checks.evaluate(chk, [_e("/sites/s/", category="Toys", sort="new"), _e("/sites/s/")])[0]  # cleared
    assert not checks.evaluate(chk, [_e("/sites/s/", status=500, category="Toys", sort="new")])[0]
    post = checks.build_check({"method": "POST", "path": "/sites/s/api", "param": "q"}, "x")
    assert checks.evaluate(post, [{"method": "POST", "path": "/sites/s/api", "body": {"q": "x"}, "status": 200}])[0]


def test_check_agrees_with_evaluation_verifier():
    chk = checks.build_check({"method": "GET", "path": "/sites/s/", "param": "category"}, "A & B")
    spec = checks.verifier_spec("t1", "filter_by_dropdown", chk)
    good = [_e("/sites/s/", category="A & B")]
    ok, _detail, report = checks.gate(chk, spec, good)
    assert ok and report["passed"]
    ok, _detail, _report = checks.gate(chk, spec, [_e("/sites/s/", category="A")])
    assert not ok


# ── sampler: stratification, caps, dedup, start states ───────────────────────

def _sitemap(site, n_filters=2, n_opts=6, page="/p"):
    ctrls = []
    for i in range(n_filters):
        opts = [{"index": 0, "value": "", "text": "All"}] + [
            {"index": j, "value": f"v{j}", "text": f"Option {j}"} for j in range(1, n_opts)]
        ctrls.append({"control_id": f"{site}:select:filter:{i}", "kind": "select", "role": "filter", "css": f"#f{i}",
                      "name": f"f{i}", "label": f"F{i}", "page": f"/sites/{site}{page}", "options": opts,
                      "selected_index": 0, "usable": True, "apply": "auto",
                      "signature": {"method": "GET", "path": f"/sites/{site}{page}", "param": f"f{i}"}})
    return {"site": site, "controls": ctrls}


@pytest.fixture
def five_sites(monkeypatch):
    import annotation.macro_locations as ml
    sites = [f"s{i}" for i in range(5)]
    monkeypatch.setattr(ml, "MACRO_LOCATIONS", {s: {"filter_by_dropdown": ["x"]} for s in sites})
    return sites, {s: _sitemap(s) for s in sites}


def test_sampler_is_stratified_across_sites(five_sites):
    from datagen import sampler
    sites, maps = five_sites
    out, _ = sampler.propose("filter_by_dropdown", 5, train=sites, sitemaps=maps, seed=1, per_site_cap=3,
                             mid_chain_share=0, preset_share=0)
    assert sorted(t["site"] for t in out) == sites                   # one per site before any repeats


def test_sampler_per_site_cap_and_unique_keys(five_sites):
    from datagen import sampler
    sites, maps = five_sites
    out, _ = sampler.propose("filter_by_dropdown", 100, train=sites, sitemaps=maps, per_site_cap=3,
                             mid_chain_share=0, preset_share=0)
    assert len(out) == 15
    assert max(sum(t["site"] == s for t in out) for s in sites) == 3
    keys = [tuple(t["dedup_key"]) for t in out]
    assert len(set(keys)) == len(keys)
    assert all(t["option"]["value"] for t in out)                    # never the empty default option


def test_sampler_excludes_known_keys_and_other_sites(five_sites):
    from datagen import sampler
    sites, maps = five_sites
    first, _ = sampler.propose("filter_by_dropdown", 100, train=sites, sitemaps=maps, per_site_cap=50,
                               mid_chain_share=0, preset_share=0)
    again, _ = sampler.propose("filter_by_dropdown", 100, train=sites, sitemaps=maps, per_site_cap=50,
                               exclude_keys=[t["dedup_key"] for t in first[:7]], mid_chain_share=0, preset_share=0)
    assert len(again) == len(first) - 7
    only, _ = sampler.propose("filter_by_dropdown", 10, train=sites[:2], sitemaps=maps, per_site_cap=50)
    assert {t["site"] for t in only} <= set(sites[:2])


def test_sampler_mid_chain_carries_prefix_and_keep(five_sites):
    from datagen import sampler
    sites, maps = five_sites
    out, _ = sampler.propose("filter_by_dropdown", 5, train=sites, sitemaps=maps, mid_chain_share=1.0)
    for t in out:
        assert t["start"]["kind"] == "mid_chain"
        pre = t["start"]["prefix"]
        assert pre["control"]["signature"]["param"] != t["control"]["signature"]["param"]
        assert t["check"]["keep"] == {pre["control"]["signature"]["param"]: pre["option"]["value"]}


def test_sampler_start_kind_quota_and_prior_counts(five_sites):
    from datagen import sampler
    sites, maps = five_sites
    out, _ = sampler.propose("filter_by_dropdown", 10, train=sites, sitemaps=maps, per_site_cap=2,
                             mid_chain_share=0.5, preset_share=0.0)
    assert sum(t["start"]["kind"] == "mid_chain" for t in out) == 5
    assert sum(t["start"]["kind"] == "mid_chain" for t in out[:4]) == 2       # every prefix keeps the share
    capped, _ = sampler.propose("filter_by_dropdown", 10, train=sites, sitemaps=maps, per_site_cap=2,
                                prior_site_counts={"s0": 2, "s1": 1})
    assert not any(t["site"] == "s0" for t in capped) and sum(t["site"] == "s1" for t in capped) == 1


# ── filter: dedup, per-site cap, failure pool ─────────────────────────────────

def test_filter_dedups_caps_and_pools_failures(monkeypatch, tmp_path):
    from datagen import config, filter as F
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(F, "judge", lambda t, d: {"passed": t["task_id"] != "judge-no", "why": "w", "votes": "2/2"})

    def task(tid, site, key):
        return {"task_id": tid, "macro": "m", "site": site, "dedup_key": [site, "GET /p f", key],
                "instruction": "i", "start": {"kind": "fresh"}}
    tasks = [task("a", "s1", "1"), task("dup", "s1", "1"), task("b", "s1", "2"), task("capped", "s1", "3"),
             task("judge-no", "s2", "1"), task("broken", "s2", "2")]
    ok = {"ok": True, "attempt": 1, "dir": "d", "backend": {"detail": "GET"}, "steps": []}
    bad = {"ok": False, "attempt": 1, "dir": "d", "error": "backend check failed: nope", "steps": [1, 2]}
    execs = {t["task_id"]: [ok] for t in tasks}
    execs["broken"] = [bad, dict(bad, attempt=2, error="policy violation: x")]
    kept, surplus, failures, judged = F.run_filter(tasks, execs, "r1", per_site_cap=2, workers=1, log=lambda m: None)
    assert [k["task_id"] for k in kept] == ["a", "b"]
    assert {s["task_id"]: s["dropped"] for s in surplus} == {"dup": "duplicate", "capped": "site_cap"}
    reasons = sorted((f["task_id"], f["reason"]) for f in failures)
    assert reasons == [("broken", "backend_fail"), ("broken", "policy_violation"), ("judge-no", "judge_fail")]
    # keys kept by an earlier run are not kept again
    (config.RUNS_DIR / "r0").mkdir(parents=True)
    (config.RUNS_DIR / "r0" / "kept.jsonl").write_text(json.dumps({"macro": "m", "site": "s1",
                                                                   "dedup_key": ["s1", "GET /p f", "2"]}) + "\n")
    kept2, surplus2, _f, _j = F.run_filter(tasks, execs, "r1", per_site_cap=5, workers=1, log=lambda m: None)
    assert "b" not in [k["task_id"] for k in kept2] and any(s["task_id"] == "b" for s in surplus2)


# ── split ─────────────────────────────────────────────────────────────────────

def test_split_is_deterministic_disjoint_and_covers_target_macros():
    from datagen.split import build_split
    sites = [f"s{i:02d}" for i in range(30)]
    support = {"m1": set(sites[:20]), "m2": set(sites[10:30]), "rare": {"s00", "s01"}}
    human = {"m1": set(sites[:12]), "m2": set(sites[14:26])}
    a = build_split(seed=3, target_macros=("m1", "m2"), min_human_test=3, sites=sites, support=support, human=human)
    b = build_split(seed=3, target_macros=("m1", "m2"), min_human_test=3, sites=sites, support=support, human=human)
    assert a["train"] == b["train"] and a["test"] == b["test"]
    assert set(a["train"]) | set(a["test"]) == set(sites) and not set(a["train"]) & set(a["test"])
    assert len(a["test"]) == 6
    for m in ("m1", "m2"):
        assert len(set(a["test"]) & human[m]) >= 3
        assert len(support[m] - set(a["test"])) >= 12             # train keeps >= 60%
    assert not {"s00", "s01"} & set(a["test"])                  # a 2-site macro keeps both in train


# ── wording validation + reasoning hygiene ───────────────────────────────────

def test_suggester_validation():
    from datagen.suggester import mentions, validate
    t = {"option": {"text": "Price: Low to High"}, "start": {"kind": "fresh"}}
    assert mentions("Sort by price, low to high", "Price: Low to High")
    assert validate(t, {"instruction": "Sort the homes by price low to high"}) is None
    assert validate(t, {"instruction": "Sort the homes by rating"})
    assert validate(t, {"instruction": "Set sort_by to price low to high"})


def test_reasoning_rejects_hidden_machinery():
    from datagen.reasoning import _validate
    f = {"thought": ""}
    assert _validate([{"thought": "The Category menu is open; I pick Toys."}], 1, f) is None
    assert _validate([{"thought": "The guide says to click the select element."}], 1, f)
    assert _validate([{"thought": "Click at x=100 near the red marker"}], 1, f)
    assert _validate([], 1, f)
    assert _validate([{"thought": "I open the html (1200) tag in the Tags menu."}], 1, f) is None   # visible text
    assert _validate([{"thought": "I click the HTML element with the css selector"}], 1, f)
    from datagen.reasoning import _unwrap
    nested = {"thoughts": {"step": 1, "thought": "ok"}, "x": 1}
    assert _unwrap(nested, f) == {"step": 1, "thought": "ok"}


# ── student-neutral trajectories, element side file, optional thoughts ──────

SENTINEL = "SENTINEL-privileged-selector-7f3a"


def _accepted(run_dir, tid="t1", with_thoughts=None, fmt=True):
    """A minimal v2 accepted trajectory (+ an elements.json carrying a sentinel)."""
    from datagen import trajectory as T
    d = run_dir / "accepted" / tid
    (d / "screenshots").mkdir(parents=True)
    for n in ("000.png", "001.png", "final.png"):
        (d / "screenshots" / n).write_bytes(b"\x89PNG\r\n\x1a\nx")
    t = {"format": T.FORMAT if fmt else None, "id": tid, "macro": "filter_by_dropdown", "site": "s", "instruction": "do it",
         "subtask": "x", "start_kind": "mid_chain", "viewport": [1280, 800], "history_macro": "sort_by_form",
         "history": [{"i": 0, "screenshot": "screenshots/000.png", "action": {"type": "key", "key": "Enter"}}],
         "steps": [{"i": 1, "screenshot": "screenshots/001.png", "action": {"type": "click", "x": 640, "y": 400,
                                                                           "button": "left"}}],
         "final_screenshot": "screenshots/final.png"}
    (d / "trajectory.json").write_text(json.dumps(t))
    (d / "elements.json").write_text(json.dumps({"format": "datagen.elements/v1", "history": [
        {"i": 0, "element": {"css_path": SENTINEL}}], "steps": [{"i": 1, "element": {"selector": {"css": SENTINEL},
                                                                                     "box": [1, 2, 3, 4]}}]}))
    if with_thoughts:
        T.save_thoughts(d, with_thoughts, [{"thought": "h"}], [{"thought": "s"}])
    return d


def test_export_is_student_neutral_until_export_time(tmp_path):
    from datagen.export import export_training
    _accepted(tmp_path)
    path, n, skipped = export_training(tmp_path, coord={"mode": "pixel", "resolution": [640, 400]})
    row = json.loads(path.read_text())
    assert n == 1 and not skipped and path.name == "train.jsonl"
    assert row["steps"][0] == {"screenshot": "accepted/t1/screenshots/001.png", "action": {"type": "click", "x": 320, "y": 200}}
    assert row["history"][0]["action"] == {"type": "key", "key": "Enter"} and row["thought_style"] == "none"
    assert "site" not in row and "elements" not in row
    path2, _n, _s = export_training(tmp_path)                        # default convention (normalized 0-1000)
    assert json.loads(path2.read_text())["steps"][0]["action"] == {"type": "click", "x": 500, "y": 500}


def test_elements_never_reach_the_exports(tmp_path):
    from datagen.export import export_audit, export_training
    _accepted(tmp_path, with_thoughts="short")
    (tmp_path / "kept.jsonl").write_text(json.dumps({"task_id": "t1", "judge": {"votes": "2/2"}, "backend": "GET"}) + "\n")
    outs = [export_training(tmp_path)[0], export_training(tmp_path, thought_style="short")[0]]
    html_path, k = export_audit(tmp_path, "filter_by_dropdown")
    outs += [html_path, tmp_path / "audit" / "filter_by_dropdown_sample.jsonl"]
    assert k == 1
    for p in outs:
        text = p.read_text()
        assert SENTINEL not in text and "css_path" not in text and "elements.json" not in text, p


def test_thoughts_are_optional_and_per_style(tmp_path):
    from datagen import trajectory as T
    from datagen.export import export_training
    d = _accepted(tmp_path)
    assert T.validate(d) == []                                        # valid with no thoughts at all
    _p, n, skipped = export_training(tmp_path, thought_style="browser_use")
    assert n == 0 and skipped == {"no browser_use thoughts": 1}      # never half-exported
    T.save_thoughts(d, "browser_use", [{"memory": "a"}], [{"memory": "b"}])
    T.save_thoughts(d, "short", [{"thought": "c"}], [{"thought": "d"}])
    assert T.styles(d) == ["browser_use", "short"] and T.validate(d) == []
    p, n, _ = export_training(tmp_path, thought_style="short")
    row = json.loads(p.read_text())
    assert n == 1 and p.name == "train.short.jsonl" and row["steps"][0]["thought"] == {"thought": "d"}
    T.save_thoughts(d, "short", [], [{"thought": "d"}])               # misaligned thoughts are invalid
    assert any("not aligned" in x for x in T.validate(d))


def test_write_thoughts_reads_saved_screens_and_writes_its_style(tmp_path, monkeypatch):
    import helpers.llm
    from PIL import Image
    from datagen import reasoning, trajectory as T
    d = _accepted(tmp_path)
    for n in ("000.png", "001.png", "final.png"):
        Image.new("RGB", (1280, 800), "white").save(d / "screenshots" / n)
    seen = {}

    def fake(prompt, **kw):
        seen["images"] = len(kw.get("images") or [])
        seen["prompt"] = prompt
        return json.dumps({"thoughts": [{"step": 1, "thought": "The menu is open; I confirm."},
                                        {"step": 2, "thought": "I click the Apply button."}]})
    monkeypatch.setattr(helpers.llm, "call_llm", fake)
    reasoning.write_thoughts(d, style="short")
    th = T.load_thoughts(d, "short")
    assert th["history"] == [{"thought": "The menu is open; I confirm."}] and len(th["steps"]) == 1
    assert seen["images"] == 3 and SENTINEL not in seen["prompt"]    # 2 frames + final; no element info
    monkeypatch.setattr(helpers.llm, "call_llm", lambda *a, **k: pytest.fail("must not regenerate"))
    reasoning.write_thoughts(d, style="short")                       # exists -> no call


def test_migrate_v1_keeps_thoughts_verbatim(tmp_path):
    from datagen import trajectory as T
    d = tmp_path / "accepted" / "t1"
    (d / "screenshots").mkdir(parents=True)
    for n in ("003.png", "004.png"):
        (d / "screenshots" / n).write_bytes(b"x")
    th = {"evaluation_previous_goal": "e", "memory": "m", "next_goal": "n"}
    v1 = {"id": "t1", "macro": "sort_by_form", "site": "s", "instruction": "i", "subtask": "x", "start_kind": "fresh",
          "viewport": [1280, 800], "coords": {"mode": "normalized", "scale": 1000}, "thought_style": "browser_use",
          "history": [], "history_macro": None, "final_screenshot": None,
          "steps": [{"screenshot": "screenshots/003.png", "thought": th, "action": {"type": "key", "key": "Enter"},
                     "raw_action": {"type": "key", "key": "Enter"}},
                    {"screenshot": "screenshots/004.png", "thought": dict(th, memory="m2"),
                     "action": {"type": "click", "x": 500, "y": 500}, "raw_action": {"type": "click", "x": 640, "y": 400}}]}
    (d / "trajectory.json").write_text(json.dumps(v1))
    assert T.migrate_v1(d) is True and T.migrate_v1(d) is False       # idempotent
    t = T.load(d)
    assert t["format"] == T.FORMAT and [s["i"] for s in t["steps"]] == [3, 4]
    assert t["steps"][1]["action"] == {"type": "click", "x": 640, "y": 400}   # pixels, not the old convention
    assert T.load_thoughts(d, "browser_use")["steps"] == [th, dict(th, memory="m2")]
    assert json.loads((d / "trajectory.v1.json").read_text()) == v1 and T.validate(d) == []


def test_actions_record_element_side_info(env):
    drv, s, dom, act = env
    drv.describe = lambda key: {"css_path": f"#{key}", "accessible_name": f"name-{key}", "implicit_role": "combobox"}
    drv.scroll_state = lambda key=None: {"window": [0, drv.scroll_y], "container": None}
    drv.element_at = lambda x, y, key=None: {"tag": "span", "css_path": f"#{key} > span", "is_target": False,
                                             "inside_target": True}
    drv.els["sel"]["options"] = [{"index": 0, "value": "", "text": "All", "selected": True},
                                 {"index": 1, "value": "t", "text": "Toys", "selected": False}]
    drv.focused = lambda: ("sel", drv._info("sel"))

    def press(key):                     # Enter commits "Toys"
        drv.els["sel"]["options"] = [dict(o, selected=o["index"] == 1) for o in drv.els["sel"]["options"]]
    drv.press = press
    sel = dom.one(css="select[name=cat]")
    click = act.click(sel)
    el = click["el"]
    assert el["element"]["selector"] == {"css": "select[name=cat]"} and el["element"]["css_path"] == "#sel"
    assert el["element"]["accessible_name"] == "name-sel" and el["element"]["role"] == "combobox"
    assert el["element"]["box"] == [100, 100, 200, 30] and el["point"] == [click["x"], click["y"]]
    assert el["url"].endswith("/sites/x/") and el["scroll"] == {"window": [0, 0], "container": None}
    assert el["at_point"]["css_path"] == "#sel > span"                 # a descendant was under the point
    assert el["select"]["before"] == {"index": 0, "value": "", "label": "All"}
    enter = act.press("Enter")["el"]
    assert enter["element"]["role_in_action"] == "focused" and enter["element"]["selector"] is None
    assert enter["select"]["after"] == {"index": 1, "value": "t", "label": "Toys"}
    btn = act.scroll_into_view(dom.one(css="#go"))
    scroll = [st for st in s.rec.steps if st["type"] == "scroll"][0]["el"]
    assert scroll["element"]["role_in_action"] == "scroll_target" and scroll["element"]["selector"] == {"css": "#go"}
    drv.els["drop"] = {"tag": "div", "css": "#drop", "text": "Drop", "visible": True, "box": [400, 1500, 100, 40]}
    act.drag(btn, dom.one(css="#drop"))                                  # both on screen after the scroll
    drag = s.rec.steps[-1]["el"]["drag"]
    assert drag["start"]["css_path"] == "#btn" and drag["end"]["css_path"] == "#drop"
    assert drag["end"]["role_in_action"] == "drag_target" and len(drag["waypoints"]) >= 5
    assert drag["waypoints"][0] == [round(s.rec.steps[-1]["x"], 1), round(s.rec.steps[-1]["y"], 1)]


def test_elements_file_aligns_with_trajectory(tmp_path, env):
    from datagen import elements, trajectory as T
    drv, s, dom, act = env
    s.rec.span = "prefix"
    act.press("Tab")
    s.rec.span = "target"
    act.click(dom.one(css="select[name=cat]"))
    act.press("Enter")
    s.rec.final(b"\x89PNG\r\n\x1a\nx")
    doc = elements.write_attempt(s.rec.dir, s.rec.steps)
    task = {"task_id": "t9", "macro": "filter_by_dropdown", "site": "x", "instruction": "i", "subtask": "st",
            "start": {"kind": "mid_chain", "prefix": {"macro": "sort_by_form"}}}
    rec = {"steps": s.rec.steps, "final_screenshot": "shots/final.png"}
    traj = T.build(task, rec, s.rec.dir, tmp_path / "accepted" / "t9")
    e = json.loads((tmp_path / "accepted" / "t9" / "elements.json").read_text())
    assert doc["complete"] and e["complete"] and e["source"] == "recorded"
    for part in ("history", "steps"):
        assert [x["i"] for x in e[part]] == [x["i"] for x in traj[part]]
        assert [x["screenshot"] for x in e[part]] == [x["screenshot"] for x in traj[part]]
    assert len(traj["history"]) == 1 and len(traj["steps"]) == 2 and T.validate(tmp_path / "accepted" / "t9") == []


def test_backfill_is_partial_and_uses_only_logs(tmp_path):
    from datagen import elements
    d = tmp_path / "a1"
    d.mkdir()
    task = {"control": {"kind": "select", "css": "#cat", "label": "Category", "apply": "button",
                        "apply_button": {"css": "#go", "text": "Apply"}, "signature": {"param": "category"},
                        "options": [{"index": 0, "value": "", "text": "All"}, {"index": 2, "value": "toys", "text": "Toys"}]},
            "option": {"index": 2, "value": "toys", "text": "Toys"}, "start": {"kind": "fresh"}}
    steps = [{"i": 0, "span": "target", "screenshot": "shots/000.png", "type": "click", "x": 10, "y": 20, "url": "u",
              "target": {"tag": "select", "id": "cat", "label": "Category", "text": "All", "box": [1, 2, 3, 4]}},
             {"i": 1, "span": "target", "screenshot": "shots/001.png", "type": "key", "key": "Enter", "url": "u"},
             {"i": 2, "span": "target", "screenshot": "shots/002.png", "type": "click", "x": 5, "y": 6, "url": "u",
              "target": {"tag": "button", "text": "Apply", "box": [0, 0, 9, 9]}}]
    (d / "attempt.json").write_text(json.dumps({"steps": steps}))
    (d / "server_log.json").write_text(json.dumps([{"method": "GET", "path": "/p", "query": {"category": "toys"}, "status": 200}]))
    doc = elements.backfill_attempt(d, task)
    assert doc["complete"] is False and doc["missing"] and doc["source"] == "backfill"
    click, enter, apply = doc["steps"]
    assert click["element"]["css_path"] == "#cat" and click["element"]["css_path_inferred"]
    assert click["select"]["before"] == {"index": 0, "value": "", "label": "All"} and click["scroll"] is None
    assert enter["element"]["role_in_action"] == "focused" and enter["element"]["inferred"]
    assert enter["select"]["after"]["value"] == "toys" and enter["select"]["confirmed_by_server_log"]
    assert apply["element"]["css_path"] == "#go" and click["point"] == [10, 20] and enter["point"] is None
