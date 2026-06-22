# Academic Paper DB

**Category**: Search & reference
**Reviewer**: Minh
**Number of macros**: 21

## Data Source

Arxiv Bulk Data — full metadata snapshot (JSONL, ~3M papers).
File: `data/291/arxiv-metadata-oai-snapshot.json`

### Data Format

One JSON object per line (JSONL). Each record has these fields:
- `id` — arxiv paper ID (e.g., "0704.0001")
- `submitter` — person who submitted
- `authors` — author string (raw, with LaTeX escapes)
- `authors_parsed` — list of [last, first, suffix] arrays
- `title` — paper title (may contain newlines)
- `comments` — e.g., "37 pages, 15 figures"
- `journal-ref` — journal reference string or null
- `doi` — DOI string or null
- `report-no` — report number or null
- `categories` — space-separated arxiv categories (e.g., "hep-ph", "cs.AI math.CO")
- `license` — license URL or null
- `abstract` — full abstract text
- `versions` — list of {version, created} objects
- `update_date` — last update date string (YYYY-MM-DD)

### Sampling

The full dataset is 5.3GB / 3M papers. The data interpreter reads `config/config.json` to determine how many papers to sample (`num_data_points`, default 200) and uses `random_seed` for deterministic reproducibility. It should sample papers covering diverse categories (cs, physics, math, q-bio, stat, econ, etc.) by stratifying across top-level categories. The sampled subset is what the site serves at runtime.

## Real-World Model

**Google Scholar / Semantic Scholar / arXiv.org** — clean, text-heavy academic search interface. Key UI elements:
- Search bar prominently at top
- Results as a list of paper cards (title, authors, abstract snippet, categories, date)
- Category/subject filters in sidebar or as dropdown
- Date range filter
- Sort options (relevance, date, citation count)
- Paper detail page with full abstract, metadata, related papers
- User features: save papers, follow authors

## Target Macros

navigate_by_dropdown, navigate_by_route, search_by_query, search_by_semantic, search_by_checkbox, search_by_route, filter_by_semantic, filter_by_dropdown, filter_by_date_range, sort_by_ranking, extract_by_query, extract_by_dropdown, extract_from_table, extract_by_route, compute_by_dropdown, compare_from_table, export_by_dropdown, export_by_route, follow_by_toggle, save_by_toggle, authenticate_by_form

## Temporal Dynamics

Not applicable — academic paper databases are append-only archives. No temporal simulation needed. Data is a static snapshot.

## Domain-Specific Notes

- Semantic search: implement simple TF-IDF or keyword-overlap matching over titles and abstracts (no external ML models needed, keep it lightweight)
- Categories use arxiv taxonomy: primary categories like cs.AI, math.CO, hep-ph, etc.
- The site should support browsing by top-level category (cs, math, physics, etc.) and by subcategory
- Authors have LaTeX-encoded names in the raw data — the interpreter should clean these
- Paper IDs follow arxiv format: YYMM.NNNNN (newer) or subject/YYMMNNN (older)
