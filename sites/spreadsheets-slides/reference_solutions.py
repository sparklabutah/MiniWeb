"""Per-task reference solutions via Flask test client for spreadsheets-slides."""
import json


def solve_001(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/files/search?q=budget")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/1/cell/1/1?sheet=0")
    data = json.loads(r.data)
    return data["value"]


def solve_003(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/presentations/1")
    pres = json.loads(r.data)
    return pres["slides"][2]["title"]


def solve_004(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/2/ref/D6")
    data = json.loads(r.data)
    return data["value"]


def solve_005(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/3/cell/4/2?sheet=0")
    data = json.loads(r.data)
    return data["value"]


def solve_006(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/8/filter?column=3&min_value=10&max_value=60")
    data = json.loads(r.data)
    return str(data["matching_count"])


def solve_007(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/1/compute?column=1&operation=sum&sheet=0")
    data = json.loads(r.data)
    return str(data["result"])


def solve_008(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/8/extremum?column=5&direction=max")
    data = json.loads(r.data)
    return data["row_data"][1]


def solve_009(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/9/compute_at_threshold?filter_column=4&threshold=2000&compare=gte&compute_column=9&operation=avg")
    data = json.loads(r.data)
    return str(data["result"])


def solve_010(client, base="/sites/spreadsheets-slides"):
    client.post(f"{base}/api/login",
                json={"username": "alice_pm", "password": "pass123"},
                content_type="application/json")
    r = client.post(f"{base}/api/spreadsheets",
                     json={"title": "Meeting Notes Q3", "owner_id": 1},
                     content_type="application/json")
    data = json.loads(r.data)
    return str(data["id"])


def solve_011(client, base="/sites/spreadsheets-slides"):
    r = client.put(f"{base}/api/spreadsheets/7/batch",
                   json={"sheet": 0, "updates": [
                       {"row": 4, "col": 1, "value": "10"},
                       {"row": 4, "col": 2, "value": "10"}
                   ]},
                   content_type="application/json")
    data = json.loads(r.data)
    return str(len(data.get("changes", [])))


def solve_012(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/6/ref/C13")
    old_data = json.loads(r.data)
    old_value = old_data["value"]
    client.put(f"{base}/api/spreadsheets/6/edit",
               json={"ref": "C13", "value": "4.0", "sheet": 0},
               content_type="application/json")
    return old_value


def solve_013(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/presentations/3")
    pres = json.loads(r.data)
    original_title = pres["slides"][2]["title"]
    client.put(f"{base}/api/presentations/3/slides/2",
               json={"title": "Your First Week Agenda"},
               content_type="application/json")
    return original_title


def solve_014(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/4")
    ss = json.loads(r.data)
    row7 = ss["sheets"][0]["data"][7]
    company = row7[1] if len(row7) > 1 else ""
    client.delete(f"{base}/api/spreadsheets/4/row/7")
    return company


def solve_015(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/3/select?column=2&contains=Engineering")
    data = json.loads(r.data)
    return str(data["selected_count"])


def solve_016(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/2/export?format=csv")
    lines = r.data.decode().strip().split("\n")
    data_rows = sum(1 for line in lines[1:] if line.strip() and not all(c in ',"' for c in line.strip()))
    return str(data_rows)


def solve_017(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/5/range/B2:B10")
    data = json.loads(r.data)
    values = data.get("values", [])
    p0_count = sum(1 for row in values for cell in row if cell == "P0")
    return str(p0_count)


def solve_018(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/spreadsheets/10/extremum?column=5&direction=max")
    data = json.loads(r.data)
    return data["row_data"][1]


def solve_019(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/presentations/5")
    pres = json.loads(r.data)
    deleted_title = pres["slides"][4]["title"]
    client.delete(f"{base}/api/presentations/5/slides/4")
    return deleted_title


def solve_020(client, base="/sites/spreadsheets-slides"):
    r = client.get(f"{base}/api/export/all?format=csv")
    lines = r.data.decode().strip().split("\n")
    data_rows = len(lines) - 1
    return str(data_rows)
