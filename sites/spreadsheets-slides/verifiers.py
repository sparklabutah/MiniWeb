"""Per-task HTTP verification functions for spreadsheets-slides."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/files/search?q=budget")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'budget': {count} files found"}


def verify_002(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/1/cell/1/1?sheet=0")
    data = r.json()
    value = data.get("value", "")
    return {"pass": value == "85000", "detail": f"Cell B2 of spreadsheet 1: {value}"}


def verify_003(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/presentations/1")
    pres = r.json()
    slides = pres.get("slides", [])
    if len(slides) < 3:
        return {"pass": False, "detail": f"Presentation 1 has only {len(slides)} slides"}
    title = slides[2].get("title", "")
    return {"pass": title == "Financial Highlights", "detail": f"Slide 3 title: {title}"}


def verify_004(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/2/ref/D6")
    data = r.json()
    value = data.get("value", "")
    return {"pass": value == "47", "detail": f"Cell D6 of spreadsheet 2: {value}"}


def verify_005(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/3/cell/4/2?sheet=0")
    data = r.json()
    value = data.get("value", "")
    return {"pass": value == "Engineering", "detail": f"Row 5 Department: {value}"}


def verify_006(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/8/filter?column=3&min_value=10&max_value=60")
    data = r.json()
    count = data.get("matching_count", 0)
    return {"pass": count > 0, "detail": f"Inventory filter 10-60: {count} items"}


def verify_007(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/1/compute?column=1&operation=sum&sheet=0")
    data = r.json()
    result = data.get("result")
    return {"pass": result is not None, "detail": f"Sum of April column: {result}"}


def verify_008(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/8/extremum?column=5&direction=max")
    data = r.json()
    row_data = data.get("row_data", [])
    product = row_data[1] if len(row_data) > 1 else ""
    value = data.get("value")
    return {"pass": product == "Standing Desk" and value == 349.99,
            "detail": f"Max unit cost: {product} at ${value}"}


def verify_009(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/9/compute_at_threshold?filter_column=4&threshold=2000&compare=gte&compute_column=9&operation=avg")
    data = r.json()
    result = data.get("result")
    matching = data.get("matching_rows", 0)
    return {"pass": result is not None and matching > 0,
            "detail": f"Avg conversions (budget>=2000): {result} from {matching} rows"}


def verify_010(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets?q=Meeting+Notes+Q3")
    results = r.json()
    found = len(results) > 0
    new_id = results[0]["id"] if found else None
    return {"pass": found, "detail": f"'Meeting Notes Q3' found: id={new_id}"}


def verify_011(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/7/ref/B5")
    data = r.json()
    val_b = data.get("value", "")
    r2 = requests.get(f"{base}/api/spreadsheets/7/ref/C5")
    data2 = r2.json()
    val_c = data2.get("value", "")
    return {"pass": val_b == "10" and val_c == "10",
            "detail": f"B5={val_b}, C5={val_c} (expected 10, 10)"}


def verify_012(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/6/ref/C13")
    data = r.json()
    value = data.get("value", "")
    return {"pass": value == "4.0", "detail": f"C13 after edit: {value}"}


def verify_013(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/presentations/3")
    pres = r.json()
    slides = pres.get("slides", [])
    if len(slides) < 3:
        return {"pass": False, "detail": "Not enough slides"}
    title = slides[2].get("title", "")
    return {"pass": title == "Your First Week Agenda",
            "detail": f"Slide 3 title after edit: {title}"}


def verify_014(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/4")
    ss = r.json()
    grid = ss.get("sheets", [{}])[0].get("data", [])
    # After deleting row 8 (RetailMax), CloudNine should now be at what was row 8
    # Check that RetailMax (D007) is no longer present in the data rows
    companies = [row[1] for row in grid[1:] if len(row) > 1 and row[1]]
    return {"pass": "RetailMax" not in companies,
            "detail": f"Companies after delete: {companies}"}


def verify_015(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/3/select?column=2&contains=Engineering")
    data = r.json()
    count = data.get("selected_count", 0)
    return {"pass": count > 0, "detail": f"Engineering employees: {count}"}


def verify_016(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/2/export?format=csv")
    lines = r.text.strip().split("\n")
    # Count non-empty data rows (skip header)
    data_rows = sum(1 for line in lines[1:] if line.strip() and not all(c in ',"' for c in line.strip()))
    return {"pass": data_rows > 0, "detail": f"CSV export: {data_rows} non-empty data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/5/range/B2:B10")
    data = r.json()
    values = data.get("values", [])
    p0_count = sum(1 for row in values for cell in row if cell == "P0")
    return {"pass": p0_count == 3, "detail": f"P0 features: {p0_count}"}


def verify_018(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/spreadsheets/10/extremum?column=5&direction=max")
    data = r.json()
    row_data = data.get("row_data", [])
    desc = row_data[1] if len(row_data) > 1 else ""
    value = data.get("value")
    return {"pass": value == 16.0,
            "detail": f"Max risk score: {value}, description: {desc}"}


def verify_019(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/presentations/5")
    pres = r.json()
    count = pres.get("slides_count", 0)
    titles = [s.get("title", "") for s in pres.get("slides", [])]
    return {"pass": count == 5 and "Security" not in " ".join(titles),
            "detail": f"Slides after delete: {count}, titles: {titles}"}


def verify_020(server_url):
    base = f"{server_url}/sites/spreadsheets-slides"
    r = requests.get(f"{base}/api/export/all?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1  # minus header
    return {"pass": data_rows > 0, "detail": f"All files CSV: {data_rows} data rows"}
