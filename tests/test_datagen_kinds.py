"""Control kinds (datagen/kinds) and the data-change (state) check."""
import pytest

from datagen import checks, kinds
from datagen.kinds.buttons import family, role_of
from datagen.kinds.filters import date_ranges, search_terms


def _inp(**kw):
    base = {"tag": "input", "type": "text", "css": "#x", "name": "", "id": "", "label": "", "placeholder": "", "value": "",
            "checked": False, "min": None, "max": None, "step": None, "visible": True, "label_css": None,
            "option_text": "", "group_label": "", "onchange": False, "form": {"method": "get", "action": "http://h/sites/s/l", "css": "form", "submit": None},
            "apply_hint": None, "box": [0, 0, 10, 10]}
    base.update(kw)
    return base


def _scan(**kw):
    s = {"title": "Listing", "h1": "", "selects": [], "links": [], "linkgroups": [], "inputs": [], "anchors": [], "dates": [],
         "items": [], "buttons": [], "headings": []}
    s.update(kw)
    return s


def test_registry_covers_the_phase_macros():
    got = set(kinds.supported_macros())
    assert {"filter_by_dropdown", "sort_by_form", "filter_by_options", "filter_by_date_range", "filter_by_slider",
            "search", "navigate_by_route", "toggle_relationship", "feedback_by_react", "delete_from_table",
            "play_by_playback", "feedback_by_star"} <= got
    assert kinds.macro_of({"kind": "select", "role": "sort"}) == "sort_by_form"


def test_choice_group_discovery_and_arguments():
    radios = [_inp(type="radio", name="type", value=v, option_text=t, checked=(v == ""), css=f"#r{i}", group_label="Job Type")
              for i, (v, t) in enumerate([("", "All Types"), ("full", "Full-time"), ("part", "Part-time")])]
    found = kinds.get("choice").discover(_scan(inputs=radios), "/sites/s/l", "s")
    assert len(found) == 1
    ctrl = found[0][1]
    assert ctrl["label"] == "Job Type" and ctrl["selected_index"] == 0
    assert [a["text"] for a in kinds.get("choice").arguments(ctrl)] == ["Full-time", "Part-time"]


def test_post_form_inputs_are_not_listing_filters():
    boxes = [_inp(type="checkbox", name="tags", value=v, option_text=v, form={"method": "post", "action": "x", "css": "f", "submit": None})
             for v in ("a", "b", "c")]
    assert kinds.get("choice").discover(_scan(inputs=boxes), "/p", "s") == []


def test_date_range_pairs_inputs_and_windows_follow_page_dates():
    ins = [_inp(type="date", name="date_from", label="From", css="#f"), _inp(type="date", name="date_to", label="To", css="#t")]
    ctrl = kinds.get("daterange").discover(_scan(inputs=ins, dates=["2026-03-04", "2026-03-20"]), "/sites/s/tx", "s")[0][1]
    assert ctrl["from"]["name"] == "date_from" and ctrl["to"]["name"] == "date_to"
    args = kinds.get("daterange").arguments(ctrl)
    assert args[0]["from"] == "2026-03-01" and args[0]["to"] == "2026-03-31"
    assert kinds.get("daterange").mentions(args[0]) == ["March 1, 2026", "March 31, 2026"]
    assert ("2026-01-01", "2026-01-31") in [(a.isoformat(), b.isoformat()) for a, b in date_ranges([])]
    task = kinds.get("daterange").script_task({"subtask": "s", "control": ctrl, "option": args[0]})
    assert task["from_keys"] == "03012026" and task["native_date"]


def test_slider_arguments_are_on_the_step_grid():
    ctrl = kinds.get("slider").discover(_scan(inputs=[_inp(type="range", name="max_price", min="0", max="1000", step="50", value="1000")]),
                                        "/p", "s")[0][1]
    vals = [float(a["value"]) for a in kinds.get("slider").arguments(ctrl)]
    assert vals and all(v % 50 == 0 and 0 < v < 1000 for v in vals)


def test_search_terms_come_from_listing_items_not_section_headings():
    terms = search_terms(["Category", "Cascadia Coffee Roasters", "Brand", "Lakeport Marina Tour"])
    assert "Cascadia" in terms and "Cascadia Coffee" in terms and "Category" not in terms


def test_nav_links_skip_side_effects_and_repeat_destinations():
    anchors = [{"text": "Orders", "path": "/sites/s/orders", "search": "", "css": "#o", "region": "nav"},
               {"text": "Log out", "path": "/sites/s/logout", "search": "", "css": "#l", "region": "nav"},
               {"text": "Item 12", "path": "/sites/s/item/12", "search": "", "css": "#i12", "region": "main"},
               {"text": "Item 13", "path": "/sites/s/item/13", "search": "", "css": "#i13", "region": "main"}]
    ctrl = kinds.get("navlink").discover(_scan(anchors=anchors), "/sites/s/", "s")[0][1]
    assert [o["value"] for o in ctrl["options"]] == ["/sites/s/orders", "/sites/s/item/12"]
    assert kinds.get("navlink").check(ctrl, ctrl["options"][0])["params"] == {}


def test_button_families_and_roles():
    assert family("♥ Like (12)") == "like" and family("Follow") == "follow"
    assert role_of("delete message") == "delete" and role_of("upvote") == "react" and role_of("save") == "toggle"
    assert role_of("log out") is None
    btn = lambda t, item, css: {"text": t, "aria": "", "css": css, "tag": "button", "region": "main", "item": item,
                                "pressed": None, "form": None, "box": [0, 0, 1, 1]}
    found = kinds.get("button").discover(_scan(buttons=[btn("Follow", "u/ana", "#a"), btn("Follow", "u/bo", "#b"),
                                                         btn("×", "Draft 1", "#x") | {"aria": "Delete draft"},
                                                         btn("Sign out", "", "#s")]), "/sites/s/people", "s")
    got = {(c["family"], c["role"]): [o["text"] for o in c["options"]] for _k, c in found}
    assert got == {("follow", "toggle"): ["u/ana", "u/bo"], ("delete draft", "delete"): ["Draft 1"]}


# ── state checks ──────────────────────────────────────────────────────────────

def _ch(coll, item, op, **changed):
    return {"site": "f", "collection": coll, "item_id": item, "op": op, "changed": {k: [None, v] for k, v in changed.items()},
            "after": None}


def test_state_check_from_the_dry_run_ignores_bookkeeping():
    chk = checks.state_check([_ch("posts", "7", "update", score=42, updated_at="2026-09-28"),
                              _ch("users", "1", "update", last_active="now")], "f",
                             [{"method": "POST", "path": "/sites/f/api/posts/7/vote", "status": 200}])
    assert chk["expect"] == [{"collection": "posts", "op": "update", "item_id": "7", "fields": {"score": "42"}}]
    assert chk["scope"] == ["posts"] and chk["request"]["path"].endswith("/vote")


def test_state_check_needs_the_change_and_nothing_else():
    chk = checks.state_check([_ch("posts", "7", "update", score=42)], "f")
    assert checks.evaluate(chk, [], [_ch("posts", "7", "update", score="42")])[0]          # "42" == 42
    assert not checks.evaluate(chk, [], [])[0]                                            # undone / never done
    assert not checks.evaluate(chk, [], [_ch("posts", "8", "update", score=42)])[0]       # another item
    assert not checks.evaluate(chk, [], [_ch("posts", "7", "update", score=42),
                                         _ch("posts", "9", "delete")])[0]                 # collateral
    assert checks.evaluate(chk, [], [_ch("posts", "7", "update", score=42),
                                     _ch("comments", "1", "insert", body="x")])[0]        # other tables: not in scope


def test_insert_matches_on_content_not_generated_id():
    chk = checks.state_check([_ch("likes", "1187", "insert", id=1187, to_user_id=6, date="2026-09-28")], "f")
    assert chk["expect"][0]["item_id"] is None and chk["expect"][0]["fields"] == {"to_user_id": "6"}
    assert checks.evaluate(chk, [], [_ch("likes", "1190", "insert", id=1190, to_user_id="6", date="x")])[0]
    assert not checks.evaluate(chk, [], [_ch("likes", "1190", "insert", id=1190, to_user_id="7")])[0]


def test_state_verifier_spec_is_the_mutating_request():
    chk = checks.state_check([_ch("posts", "7", "update", score=42)], "f",
                             [{"method": "POST", "path": "/sites/f/api/posts/7/vote", "status": 200}])
    spec = checks.verifier_spec("t", "feedback_by_react", chk)
    leaf = spec["macros"]["feedback_by_react"]["checks"][0]
    assert leaf["method"] == "POST" and leaf["url"] == "/sites/f/api/posts/7/vote"


def test_repeated_query_values_match_lists():
    chk = checks.build_check({"method": "GET", "path": "/sites/s/", "param": "env"}, "prod")
    assert checks.evaluate(chk, [{"method": "GET", "path": "/sites/s/", "query": {"env": ["prod", "dev"]}, "status": 200}])[0]


# ── forms, uploads, gestures, grids ───────────────────────────────────────────

def test_form_roles_and_fields():
    from datagen.kinds.forms import role_of
    assert role_of("Sign In | /sites/x/login | Welcome", {}) == "authenticate_by_form"
    assert role_of("Place order | /checkout", {}) == "checkout_by_form"
    assert role_of("Save | /sites/x/new | New project", {"create_by_form": ["x"]}) == "create_by_form"
    assert role_of("Send | /sites/x/messages", {}) == "message_from_free_text"
    form = {"method": "post", "action": "http://h/sites/x/new", "css": "#f", "submit": {"css": "#go", "text": "Create"}}
    ins = [_inp(name="title", label="Title", form=form, css="#t"), _inp(type="date", name="due", label="Due", form=form, css="#d")]
    ctrl = kinds.get("form").discover(_scan(inputs=ins, h1="New task"), "/sites/x/new", "x")[0][1]
    assert ctrl["role"] == "create_by_form" and [f["type"] for f in ctrl["fields"]] == ["text", "date"]
    arg = {"index": 0, "value": "h", "text": "t", "values": {"title": "Quarterly plan", "due": "2026-11-03"}}
    kind = kinds.get("form")
    assert kind.mentions(arg) == ["Quarterly plan", "November 3, 2026"]
    task = kind.script_task({"subtask": "s", "control": ctrl, "option": arg})
    assert task["fields"][1]["keys"] == "11032026" and task["submit_css"] == "#go"


def test_get_forms_are_left_to_the_filter_kinds():
    form = {"method": "get", "action": "http://h/sites/x/", "css": "#f", "submit": {"css": "#go", "text": "Save"}}
    assert kinds.get("form").discover(_scan(inputs=[_inp(name="q", form=form)]), "/sites/x/", "x") == []


def test_signature_strokes_stay_inside_the_pad():
    from datagen.kinds.gesture import signature_strokes
    for seed in range(5):
        strokes = signature_strokes(seed)
        assert 2 <= len(strokes) <= 4
        assert all(0 <= x <= 1 and 0 <= y <= 1 for st in strokes for x, y in st)
    assert signature_strokes(1) == signature_strokes(1) and signature_strokes(1) != signature_strokes(2)


def test_grid_cells_keep_numbers_numeric():
    cells = [{"css": f"#c{i}", "text": t, "row": f"R{i}", "col": "Qty", "input": False, "box": []}
             for i, t in enumerate(["12", "7.5", "Pending", "40"])]
    ctrl = kinds.get("gridcell").discover(_scan(cells=cells), "/sites/s/sheet/1", "s")[0][1]
    args = kinds.get("gridcell").arguments(ctrl)
    assert args[0]["new"].isdigit() and args[0]["new"] != "12"
    assert args[2]["new"] in __import__("datagen.kinds.grid", fromlist=["WORDS"]).WORDS


def test_clipboard_check():
    chk = {"kind": "clipboard", "value": "https://x/share/abc"}
    assert checks.evaluate(chk, [], clip=["https://x/share/abc "])[0]
    assert not checks.evaluate(chk, [], clip=["something else"])[0]
    assert checks.verifier_spec("t", "copy_content", chk)["macros"]["copy_content"]["checks"][0]["action"] == "clipboard_write"


def test_drawn_images_only_need_to_exist():
    drawn = lambda uri: {"site": "f", "collection": "filings", "item_id": "1", "op": "update",
                         "changed": {"signature_drawing": [None, uri], "signed": [None, True]}, "after": None}
    chk = checks.state_check([drawn("data:image/png;base64,AAAA")], "f")
    assert chk["expect"][0]["fields"] == {"signature_drawing": checks.ANY, "signed": "1"}
    assert checks.evaluate(chk, [], [drawn("data:image/png;base64,BBBB")])[0]
    assert not checks.evaluate(chk, [], [drawn("")])[0]


def test_form_role_prefers_the_submit_label_over_the_page_title():
    from datagen.kinds.forms import role_of
    assert role_of("Save format | /sites/translation/api/export | Export | LinguaBridge Translation", {}) != "translate_by_query"


def test_nested_drawn_images_only_need_to_exist():
    rec = lambda uri: {"site": "h", "collection": "consent_forms", "item_id": "9", "op": "insert",
                       "changed": {"forms": [None, [{"body": "I consent", "signature": uri}]]}, "after": None}
    chk = checks.state_check([rec("data:image/png;base64,AAAA")], "h")
    assert checks.evaluate(chk, [], [rec("data:image/png;base64,ZZZZ")])[0]
    assert not checks.evaluate(chk, [], [{**rec("x"), "changed": {"forms": [None, [{"body": "other", "signature": "data:image/png;base64,Q"}]]}}])[0]


def test_qa_questions_compute_answers_in_code():
    from datagen.kinds import qa
    tb = {"headers": ["Account", "Type", "Balance", "Rate"],
          "rows": [["Checking", "checking", "$1,200.00", "0.10%"], ["Savings", "savings", "$5,000.50", "4.20%"],
                   ["Loan", "loan", "$300.00", "5.45%"]]}
    recs = qa.table_records(tb)
    assert [r["name"] for r in recs] == ["Checking", "Savings", "Loan"]
    args = qa.questions(recs, "accounts", whole_set=True, seed="t")
    by = {}
    for a in args:
        by.setdefault(a["op"], []).append(a)
    want = {"highest balance": "Savings", "lowest balance": "Loan", "highest rate": "Loan", "lowest rate": "Checking"}
    assert by["extremum"]
    for a in by["extremum"]:
        key = next(k for k in want if k in a["question"])
        assert a["answer"] == want[key] and a["answer"] in a["forbid"]
    for a in by.get("compute", []):
        assert ("combined" in a["question"]) == ("balance" in a["question"])      # rates are never summed
    ent = qa.questions(recs, "accounts", whole_set=True, seed="t", count_entries=True)
    assert ent[0]["answer"] == "3" and set(ent[0]["evidence"]) == {"Checking", "Savings", "Loan"}
    assert qa.questions(recs, "accounts", whole_set=False, seed="t", count_entries=True) == []
    assert qa.number("$1,299.50") == 1299.5 and qa.number("2024-01-02") is None and qa.fmt_like(1500.5, ["$1,200.00"]) == "$1,500.50"


def test_answer_check_needs_right_reply_and_evidence_seen():
    chk = {"kind": "answer", "value": "Savings", "alternatives": [], "evidence": ["Savings", "$5,000.50"], "requires": None}
    assert checks.evaluate(chk, [], answer="Savings", seen=["Checking $1,200.00", "Savings $5,000.50"])[0]
    assert not checks.evaluate(chk, [], answer="Savings", seen=["Checking $1,200.00"])[0]      # never shown
    assert not checks.evaluate(chk, [], answer=None, seen=["Savings $5,000.50"])[0]
    spec = checks.verifier_spec("t", "report_information", chk)
    assert spec["macros"]["report_information"]["checks"][0]["type"] == "answer_matches"


def test_all_registry_macros_have_a_kind():
    from annotation import macros as registry
    from datagen import kinds
    assert set(registry.all_canonical()) <= set(kinds.supported_macros())


def test_playback_scrub_plan_searches_forward_into_the_span():
    from datagen.kinds.playback import scrub_plan
    plan = scrub_plan(745, 770, 1845, "seed")
    assert plan == sorted(plan) and 745 / 1845 <= plan[-1] <= 770 / 1845
    steps = [b - a for a, b in zip(plan, plan[1:-1])]
    assert all(s <= 25 / 1845 + 1e-9 for s in steps)          # never jumps over the span


def test_reveal_finds_the_code_in_a_new_message():
    from datagen.kinds.reveal import code_home, code_message
    changes = [{"site": "email", "collection": "sent_messages", "item_id": "m9", "op": "insert",
                "after": {"subject": "Verification Code: 482913", "folder": "inbox"}, "changed": {}},
               {"site": "banking", "collection": "accounts", "item_id": "1", "op": "update", "changed": {"n": [1, 2]}}]
    code, site, row = code_message(changes)
    assert (code, site) == ("482913", "email") and code_home(site, row) == "/sites/email/"
    # a conversation the site opened in this session has a per-session id: the agent finds it in the list
    assert code_home("instant-messaging", {"conversation_id": "conv-new-x7"}) == "/sites/instant-messaging/"
    assert code_message([changes[1]]) is None


def test_tool_slider_values_snap_to_their_step():
    from datagen.kinds.tools import _snap
    assert _snap({"min": "0", "max": "25000", "step": "500"}, "12345") == "12500"
    assert _snap({"min": "0", "max": "2", "step": "0.05"}, "1.33") == "1.35"


def test_map_drag_plan_centres_the_point():
    from datagen.kinds.mapview import drag_plan
    pt = {"w": 800, "h": 600, "x": 1900, "y": -300, "zoom": 13.5}
    plan = drag_plan(pt)
    moved_x = sum((b[0] - a[0]) * 800 for a, b in plan)
    moved_y = sum((b[1] - a[1]) * 600 for a, b in plan)
    assert abs(pt["x"] + moved_x - 400) < 1 and abs(pt["y"] + moved_y - 300) < 1
    assert all(0 <= v <= 1 for a, b in plan for v in (*a, *b))


def test_program_check_matches_the_output_not_the_code():
    chk = {"kind": "request", "method": "POST", "path": "/sites/c/api/execute", "params": {}, "keep": {}, "final": False,
           "response": {"stdout": "21\n", "returncode": 0}}
    run = lambda out, rc=0: [{"method": "POST", "path": "/sites/c/api/execute", "status": 200, "query": {},
                              "body": {"code": "print(21)"}, "response": {"stdout": out, "returncode": rc}}]
    assert checks.evaluate(chk, run("21\n"))[0] and checks.evaluate(chk, run("21"))[0]
    assert not checks.evaluate(chk, run("22\n"))[0] and not checks.evaluate(chk, run("21\n", 1))[0]
    spec = checks.verifier_spec("t", "write_executable_program", chk)
    assert spec["macros"]["write_executable_program"]["checks"][0]["response_fields"]["stdout"] == "21\n"


def test_request_check_with_evidence_needs_it_on_screen():
    chk = {"kind": "request", "method": "GET", "path": "/sites/b/", "params": {"q": "Meridian Systems"}, "keep": {},
           "final": False, "evidence": ["Meridian Systems"]}
    log = [{"method": "GET", "path": "/sites/b/", "status": 200, "query": {"q": "Meridian Systems"}}]
    assert checks.evaluate(chk, log, seen=["news: Meridian Systems Recognized"])[0]
    assert not checks.evaluate(chk, log, seen=["something else"])[0]
    assert checks.evaluate(chk, log)[0]                        # dry runs have no screenshots: request only


def test_nested_timestamps_are_incidental():
    rec = lambda at: {"site": "n", "collection": "notes", "item_id": "1", "op": "update",
                      "changed": {"image_edits": [[], [{"op": "crop", "params": {"x": 0}, "at": at}]]}, "after": None}
    chk = checks.state_check([rec("2026-01-01T00:00:00")], "n")
    assert checks.evaluate(chk, [], [rec("2026-09-27T12:00:00")])[0]


def test_board_columns_and_range_check():
    from datagen.kinds.board import column_of, columns
    items = [{"text": "TO DO", "bold": True, "cls": "wb-element type-text", "x": 40, "y": 20, "w": 80, "h": 24},
             {"text": "DONE", "bold": True, "cls": "wb-element type-text", "x": 400, "y": 20, "w": 80, "h": 24},
             {"text": "Fix badge", "bold": False, "cls": "wb-element type-sticky", "x": 40, "y": 80, "w": 160, "h": 90}]
    cols = columns(items)
    assert [c["text"] for c in cols] == ["TO DO", "DONE"] and column_of(items[2], cols)["text"] == "TO DO"
    chk = {"kind": "request", "method": "PUT", "path": "/b/elements/2/move", "keep": {}, "final": True,
           "params": {"x": {"value": [390, 600], "mode": "between"}, "y": {"value": [44, 800], "mode": "between"}}}
    put = lambda x, y: {"method": "PUT", "path": "/b/elements/2/move", "status": 200, "query": {}, "body": {"x": x, "y": y}}
    assert checks.evaluate(chk, [put(452, 130)])[0]
    assert not checks.evaluate(chk, [put(452, 130), put(60, 130)])[0]        # moved back out: final fails


def test_rank_buttons_and_form_submit_roles():
    from datagen.kinds.buttons import family, role_of as button_role
    from datagen.kinds.forms import role_of as form_role
    assert button_role(family("Move Up")) == "rank" and button_role(family("Move down")) == "rank"
    assert form_role("Place Your Order | /checkout | | Checkout", {}) == "checkout_by_form"


def test_new_action_types_survive_trajectory_and_export():
    from datagen.actions import CoordConvention, to_student
    from datagen.trajectory import _NEEDS, pixel_action
    conv = CoordConvention()
    steps = [{"type": "answer", "text": "42"}, {"type": "goto", "url": "/sites/email/"},
             {"type": "draw", "x": 10, "y": 10, "strokes": [[[10, 10], [20, 20]]]},
             {"type": "upload", "x": 5, "y": 5, "file": "Pictures/a.jpg"},
             {"type": "new_tab", "url": "/sites/instant-messaging/"}, {"type": "switch_tab", "index": 0}]
    for s in steps:
        a = pixel_action(s)
        assert all(k in a for k in _NEEDS[s["type"]])
        to_student(a, conv, (1280, 800))


def test_clipboard_check_ignores_the_server_origin():
    chk = {"kind": "clipboard", "value": "http://localhost:8304/sites/forums/post/sd_1"}
    assert checks.evaluate(chk, [], clip=["http://localhost:8305/sites/forums/post/sd_1"])[0]
    assert not checks.evaluate(chk, [], clip=["http://localhost:8305/sites/forums/post/"])[0]


def test_values_with_underscores_are_not_field_name_leaks():
    from datagen import suggester
    t = {"control": {"kind": "form", "role": "authenticate_by_form", "fields": [
            {"css": "#u", "type": "text", "name": "username", "label": "Username"},
            {"css": "#p", "type": "password", "name": "password", "label": "Password"}]},
         "option": {"values": {"username": "marcus_chen", "password": "ClimbHigh95!"}, "text": "sign in"},
         "start": {"kind": "fresh"}}
    assert suggester.validate(t, {"instruction": "Log in as marcus_chen with password ClimbHigh95!"}) is None
    assert suggester.validate(t, {"instruction": "Log in as marcus_chen, set user_name ClimbHigh95!"}) is not None


def test_edit_form_arguments_keep_only_changed_fields():
    from datagen.kinds.forms import _changed
    ctrl = {"fields": [{"css": "#t", "name": "title", "type": "text", "value": "Notes"},
                       {"css": "#c", "name": "content", "type": "textarea", "value": "long body"}]}
    assert _changed(ctrl, {"title": "Weekly Notes", "content": "long body"}) == {"title": "Weekly Notes"}


def test_propose_fill_pass_takes_the_rest_from_richer_sites():
    from datagen import sampler
    opts = lambda n: [{"index": i, "value": str(i), "text": f"Option {i}"} for i in range(n)]
    ctrl = lambda site, n: {"control_id": f"{site}:select:0", "kind": "select", "role": "filter", "usable": True,
                            "css": "select", "name": "cat", "page": f"/sites/{site}/", "page_title": site,
                            "signature": {"method": "GET", "path": f"/sites/{site}/", "param": "cat"}, "options": opts(n)}
    maps = {"a": {"controls": [ctrl("a", 30)]}, "b": {"controls": [ctrl("b", 2)]}}
    import datagen.sitemap as sm
    real = sm.usable_for
    sm.usable_for = lambda site_map, macro: (site_map or {}).get("controls", [])
    try:
        even, _ = sampler.propose("filter_by_dropdown", 12, train=["a", "b"], sitemaps=maps, per_site_cap=3)
        filled, _ = sampler.propose("filter_by_dropdown", 12, train=["a", "b"], sitemaps=maps, per_site_cap=3, fill=True)
    finally:
        sm.usable_for = real
    assert len(even) == 5 and len(filled) == 12


def test_verifier_specs_match_multi_values_and_copied_routes():
    chk = {"kind": "request", "method": "GET", "path": "/sites/u/compare", "params": {"ids": "c-325"}, "keep": {},
           "final": True, "multi": True}
    spec = checks.verifier_spec("t", "compare_by_form", chk)
    run = lambda q: checks.run_verifier(spec, [{"method": "GET", "path": "/sites/u/compare", "status": 200, "query": q,
                                                "timestamp": "2026-09-28T08:00:00Z"}])["passed"]
    assert run({"ids": ["c-100", "c-325"]}) and run({"ids": "c-100,c-325"}) and run({"ids": "c-325"})
    assert not run({"ids": "c-3250"}) and not run({"ids": "c-100"})
    clip = checks.verifier_spec("t", "share_by_form", {"kind": "clipboard", "value": "http://localhost:8304/sites/f/post/x1"})
    ev = lambda v: [{"type": "action", "action": "clipboard_write", "target": "", "value": v}]
    assert checks.run_verifier(clip, [], ev("http://localhost:8305/sites/f/post/x1"))["passed"]
    assert not checks.run_verifier(clip, [], ev("http://localhost:8305/sites/f/post/x2"))["passed"]
