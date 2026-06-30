"""Per-macro verification functions for spreadsheets-slides.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/spreadsheets-slides"


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/files/search?q=budget")
    results = r.json()
    ok = len(results) > 0 and results[0].get("relevance_score", 0) > 0
    return {"pass": ok,
            "detail": f"navigate_by_semantic: {len(results)} results, top={results[0]['title'] if results else 'N/A'}"}


def verify_macro_navigate_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/1/cell/1/1?sheet=0")
    data = r.json()
    ok = data.get("value") is not None and "cell_ref" in data
    return {"pass": ok,
            "detail": f"navigate_from_table: cell={data.get('cell_ref')}, value={data.get('value')}"}


def verify_macro_navigate_by_route(server_url):
    r1 = requests.get(f"{_base(server_url)}/spreadsheet/1")
    r2 = requests.get(f"{_base(server_url)}/presentation/1")
    ok = r1.status_code == 200 and r2.status_code == 200
    return {"pass": ok,
            "detail": f"navigate_by_route: spreadsheet={r1.status_code}, presentation={r2.status_code}"}


def verify_macro_extract_by_code(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/1/ref/A1")
    data = r.json()
    ok = data.get("ref") == "A1" and data.get("value") is not None
    # Also test range
    r2 = requests.get(f"{_base(server_url)}/api/spreadsheets/1/range/A1:C3")
    range_data = r2.json()
    ok2 = len(range_data.get("values", [])) > 0
    return {"pass": ok and ok2,
            "detail": f"extract_by_code: A1={data.get('value')}, range has {len(range_data.get('values', []))} rows"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/3")
    ss = r.json()
    grid = ss.get("sheets", [{}])[0].get("data", [])
    ok = len(grid) > 1 and len(grid[0]) > 0
    return {"pass": ok,
            "detail": f"extract_from_table: spreadsheet 3 has {len(grid)} rows, {len(grid[0])} cols"}


def verify_macro_extract_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/8/filter?column=3&min_value=50&max_value=200")
    data = r.json()
    count = data.get("matching_count", 0)
    return {"pass": count > 0,
            "detail": f"extract_by_slider: {count} items with qty 50-200"}


def verify_macro_compute_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/1/compute?column=1&operation=sum&sheet=0")
    data = r.json()
    result = data.get("result")
    ok = result is not None and result > 0
    return {"pass": ok,
            "detail": f"compute_by_query: sum of col 1 = {result}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/4/extremum?column=4&direction=max")
    data = r.json()
    value = data.get("value")
    ok = value is not None and value > 0
    return {"pass": ok,
            "detail": f"compute_by_extremum: max value in col 4 = {value}"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/9/compute_at_threshold?filter_column=4&threshold=1000&compare=gte&compute_column=9&operation=sum")
    data = r.json()
    result = data.get("result")
    matching = data.get("matching_rows", 0)
    ok = result is not None and matching > 0
    return {"pass": ok,
            "detail": f"compute_by_slider: sum={result}, matching={matching}"}


def verify_macro_create_from_free_text(server_url):
    # Create a spreadsheet
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/spreadsheets",
               json={"title": "_macro_test_ss", "owner_id": 1})
    data = r.json()
    ok = r.status_code == 201 and data.get("id") is not None
    # Clean up
    if ok:
        s.delete(f"{_base(server_url)}/api/spreadsheets/{data['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: created id={data.get('id')}"}


def verify_macro_submit_from_table(server_url):
    s = requests.Session()
    r = s.put(f"{_base(server_url)}/api/spreadsheets/7/batch",
              json={"sheet": 0, "updates": [
                  {"row": 9, "col": 9, "value": "_test_marker"}
              ]})
    data = r.json()
    changes = data.get("changes", [])
    ok = len(changes) == 1 and changes[0]["new"] == "_test_marker"
    # Revert
    s.put(f"{_base(server_url)}/api/spreadsheets/7/batch",
          json={"sheet": 0, "updates": [
              {"row": 9, "col": 9, "value": ""}
          ]})
    return {"pass": ok,
            "detail": f"submit_from_table: {len(changes)} changes applied"}


def verify_macro_edit_by_query(server_url):
    # Get old value, set new, then revert
    s = requests.Session()
    r = s.get(f"{_base(server_url)}/api/spreadsheets/1/ref/J1")
    old = r.json().get("value", "")
    r2 = s.put(f"{_base(server_url)}/api/spreadsheets/1/edit",
               json={"ref": "J1", "value": "_macro_test", "sheet": 0})
    data = r2.json()
    ok = data.get("new_value") == "_macro_test"
    # Revert
    s.put(f"{_base(server_url)}/api/spreadsheets/1/edit",
          json={"ref": "J1", "value": old, "sheet": 0})
    return {"pass": ok,
            "detail": f"edit_by_query: set J1 to _macro_test, old was '{old}'"}


def verify_macro_edit_by_form(server_url):
    # Get current slide title, edit, then revert
    s = requests.Session()
    r = s.get(f"{_base(server_url)}/api/presentations/1")
    pres = r.json()
    original_title = pres["slides"][7]["title"]  # last slide
    r2 = s.put(f"{_base(server_url)}/api/presentations/1/slides/7",
               json={"title": "_macro_test_slide"})
    data = r2.json()
    ok = data.get("slide", {}).get("title") == "_macro_test_slide"
    # Revert
    s.put(f"{_base(server_url)}/api/presentations/1/slides/7",
          json={"title": original_title})
    return {"pass": ok,
            "detail": f"edit_by_form: set slide 8 title to _macro_test_slide"}


def verify_macro_delete_from_table(server_url):
    # Delete a known data row from a spreadsheet and verify the response
    # Row 1 (index 1) of spreadsheet 1 is "Salaries" row
    s = requests.Session()
    r = s.delete(f"{_base(server_url)}/api/spreadsheets/1/row/1?sheet=0")
    data = r.json()
    deleted = data.get("deleted_row", [])
    ok = len(deleted) > 0 and deleted[0] == "Salaries"
    # Also verify slide deletion works
    r2 = s.get(f"{_base(server_url)}/api/presentations/1")
    pres = r2.json()
    orig_count = pres["slides_count"]
    r3 = s.delete(f"{_base(server_url)}/api/presentations/1/slides/0")
    data3 = r3.json()
    ok2 = data3.get("remaining_slides", 0) == orig_count - 1
    return {"pass": ok and ok2,
            "detail": f"delete_from_table: row deleted='{deleted[0] if deleted else ''}', slide remaining={data3.get('remaining_slides')}"}


def verify_macro_select_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/3/select?column=2&contains=Engineering")
    data = r.json()
    count = data.get("selected_count", 0)
    ok = count > 0
    return {"pass": ok,
            "detail": f"select_from_table: {count} Engineering rows selected"}


def verify_macro_export_by_dropdown(server_url):
    # CSV export
    r = requests.get(f"{_base(server_url)}/api/spreadsheets/1/export?format=csv")
    ok_csv = r.status_code == 200 and "," in r.text
    # JSON export
    r2 = requests.get(f"{_base(server_url)}/api/spreadsheets/1/export?format=json")
    ok_json = r2.status_code == 200
    data = r2.json()
    ok_data = len(data) > 0
    return {"pass": ok_csv and ok_json and ok_data,
            "detail": f"export_by_dropdown: CSV={ok_csv}, JSON={len(data)} rows"}
