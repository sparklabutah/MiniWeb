"""Update site.json and doc/README.md for all sites from MiniWeb_website.xlsx."""
import openpyxl, json, os

wb = openpyxl.load_workbook('MiniWeb_website.xlsx')
ws = wb['Subcategory Assignments']
sites_dir = 'sites'
count = 0

for row in ws.iter_rows(min_row=2, values_only=True):
    top_level, subcategory = row[0], row[1]
    if not subcategory:
        continue

    site_id = subcategory.lower().strip()
    site_id = site_id.replace(' & ', '-').replace(' / ', '-').replace('/', '-').replace(' ', '-')
    site_id = site_id.replace('(', '').replace(')', '').replace(',', '').replace("'", '')
    site_id = site_id.replace('+', '-')
    while '--' in site_id:
        site_id = site_id.replace('--', '-')
    site_id = site_id.strip('-')
    if 'q&a' in subcategory.lower():
        site_id = 'qa-knowledge'

    site_dir = os.path.join(sites_dir, site_id)
    if not os.path.isdir(site_dir):
        print(f"SKIP: {site_id}")
        continue

    top = (top_level or 'Other').strip()
    name = subcategory.strip()
    num_macros = int(row[2]) if row[2] else 0
    macros_col = row[5] if row[5] else row[4]
    macros = [m.strip() for m in macros_col.split(',')] if macros_col else []
    data_source = (row[6] or '').strip()
    reviewer = (row[7] or '').strip()

    tags = [t.strip().lower().replace(' ', '-') for t in top.split('/')]
    tags.append(name.lower().replace(' ', '-').replace('/', '-'))

    site_json = {
        "id": site_id,
        "name": name,
        "description": f"{name} - {top}",
        "tags": tags
    }
    with open(os.path.join(site_dir, 'site.json'), 'w') as f:
        json.dump(site_json, f, indent=4)
        f.write('\n')

    doc_dir = os.path.join(site_dir, 'doc')
    os.makedirs(doc_dir, exist_ok=True)

    doc_lines = [
        f"# {name}",
        "",
        f"**Category**: {top}",
        f"**Reviewer**: {reviewer or 'TBD'}",
        f"**Number of macros**: {num_macros}",
        "",
        "## Data Source",
        "",
        data_source if data_source else "TBD -- no data source specified yet.",
        "",
        "## Target Macros",
        "",
        ", ".join(macros) if macros else "TBD",
        "",
        "## Site Description",
        "",
        "TODO: Write a description of:",
        "- What this website is (domain, purpose, target audience)",
        "- How it uses the data files in data/",
        "- What real-world website it should be modeled after",
        "- Whether the domain has temporal/dynamic data (and how it should simulate)",
        "- Any domain-specific behavior or constraints",
        "",
    ]
    with open(os.path.join(doc_dir, 'README.md'), 'w') as f:
        f.write('\n'.join(doc_lines))

    count += 1
    print(f"OK: {site_id}")

print(f"\nDone! Updated {count} sites.")
