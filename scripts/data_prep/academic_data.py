#!/usr/bin/env python3
"""
Fetch real papers from the Arxiv API and transform them into the
academic-paper-db site data format (papers, authors, journals, users, citations).

Usage:
    python scripts/data_prep/academic_data.py
"""

import json
import hashlib
import math
import pathlib
import random
import time
import urllib.request
import xml.etree.ElementTree as ET

SITE_DATA_DIR = pathlib.Path("/scratch/general/vast/u1653932/data_sources/academic-paper-db")
PRISTINE_DIR = SITE_DATA_DIR / ".pristine"

ARXIV_BASE = "http://export.arxiv.org/api/query"

# Categories to fetch from, with friendly field/subfield mappings
CATEGORY_MAP = {
    "cs.AI":   ("Computer Science", "Artificial Intelligence"),
    "cs.CL":   ("Computer Science", "Natural Language Processing"),
    "cs.CV":   ("Computer Science", "Computer Vision"),
    "cs.LG":   ("Computer Science", "Machine Learning"),
    "cs.RO":   ("Computer Science", "Robotics"),
    "math.OC": ("Mathematics", "Optimization And Control"),
    "math.ST": ("Mathematics", "Statistics Theory"),
    "math.PR": ("Mathematics", "Probability"),
    "physics.comp-ph": ("Physics", "Computational Physics"),
    "quant-ph":        ("Physics", "Quantum Physics"),
    "stat.ML": ("Mathematics", "Statistical Learning"),
    "eess.SP": ("Engineering", "Signal Processing"),
    "cs.CR":   ("Computer Science", "Cryptography And Security"),
    "physics.data-an": ("Physics", "Data Analysis"),
}

# How many papers to fetch per category
PER_CATEGORY = 18  # ~250 fetched, we'll trim to ~200

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Methodology labels to assign based on keyword heuristics
METHODOLOGY_KEYWORDS = {
    "Experimental": ["experiment", "dataset", "benchmark", "evaluation", "empirical", "results show", "we train", "we test"],
    "Theoretical": ["theorem", "proof", "lemma", "we prove", "bound", "convergence", "asymptotic"],
    "Simulation": ["simulation", "simulated", "monte carlo", "synthetic data", "numerical experiment"],
    "Survey": ["survey", "review", "overview", "comprehensive study", "literature"],
    "Meta-analysis": ["meta-analysis", "meta analysis", "systematic review", "aggregate"],
    "Case Study": ["case study", "real-world application", "deployment"],
}

# Journal names to assign (synthesized plausible venues mapped to fields)
FIELD_JOURNALS = {
    "Computer Science": [
        ("Journal of Artificial Intelligence Research", "AAAI Press", 5.0, True),
        ("IEEE Transactions on Pattern Analysis", "IEEE", 24.3, False),
        ("Neural Computation", "MIT Press", 3.7, True),
        ("ACM Computing Surveys", "ACM", 16.6, True),
    ],
    "Mathematics": [
        ("Annals of Statistics", "IMS", 4.1, False),
        ("SIAM Journal on Optimization", "SIAM", 3.2, False),
        ("Journal of Mathematical Analysis", "Elsevier", 1.8, False),
    ],
    "Physics": [
        ("Physical Review Letters", "APS", 9.2, False),
        ("Journal of Computational Physics", "Elsevier", 4.6, False),
        ("Quantum Science and Technology", "IOP Publishing", 6.7, True),
    ],
    "Engineering": [
        ("IEEE Signal Processing Letters", "IEEE", 3.9, False),
        ("IEEE Transactions on Signal Processing", "IEEE", 5.4, False),
    ],
}


def fetch_arxiv(category: str, max_results: int) -> list[dict]:
    """Fetch papers from a single Arxiv category."""
    url = f"{ARXIV_BASE}?search_query=cat:{category}&start=0&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    print(f"  Fetching {category} ({max_results} papers)...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MiniWeb-DataPrep/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
    except Exception as e:
        print(f"    WARNING: Failed to fetch {category}: {e}")
        return []

    entries = root.findall(f"{ATOM_NS}entry")
    papers = []
    for entry in entries:
        title = entry.findtext(f"{ATOM_NS}title", "").strip().replace("\n", " ")
        # Collapse multiple spaces
        while "  " in title:
            title = title.replace("  ", " ")

        abstract = entry.findtext(f"{ATOM_NS}summary", "").strip().replace("\n", " ")
        while "  " in abstract:
            abstract = abstract.replace("  ", " ")
        # Truncate very long abstracts
        if len(abstract) > 800:
            abstract = abstract[:797] + "..."

        published = entry.findtext(f"{ATOM_NS}published", "")
        year = int(published[:4]) if published else 2024

        arxiv_id_url = entry.findtext(f"{ATOM_NS}id", "")
        arxiv_id = arxiv_id_url.split("/abs/")[-1] if "/abs/" in arxiv_id_url else arxiv_id_url

        # Authors
        author_els = entry.findall(f"{ATOM_NS}author")
        author_names = []
        for a in author_els:
            name = a.findtext(f"{ATOM_NS}name", "").strip()
            if name:
                author_names.append(name)

        # Categories
        cat_els = entry.findall(f"{ATOM_NS}category")
        categories = [c.get("term", "") for c in cat_els if c.get("term")]

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": author_names,
            "abstract": abstract,
            "year": year,
            "categories": categories,
            "primary_category": category,
        })

    print(f"    Got {len(papers)} papers")
    return papers


def guess_methodology(abstract: str) -> str:
    abstract_lower = abstract.lower()
    scores = {}
    for method, keywords in METHODOLOGY_KEYWORDS.items():
        scores[method] = sum(1 for kw in keywords if kw in abstract_lower)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "Experimental"  # default
    return best


def extract_keywords(title: str, abstract: str) -> list[str]:
    """Extract plausible keywords from title and abstract."""
    # Common academic stop words
    stop = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "can", "shall", "this", "that", "these",
            "those", "it", "its", "we", "our", "they", "them", "their", "and",
            "or", "but", "in", "on", "at", "to", "for", "of", "with", "by",
            "from", "as", "into", "through", "during", "before", "after",
            "between", "under", "above", "such", "than", "more", "also",
            "not", "no", "nor", "only", "own", "same", "so", "very",
            "each", "every", "both", "few", "most", "other", "some",
            "over", "which", "when", "where", "while", "all", "any",
            "about", "up", "out", "if", "then", "what", "how", "show",
            "paper", "propose", "proposed", "approach", "method", "based",
            "using", "use", "used", "new", "novel", "results", "two", "one",
            "first", "second", "however", "well", "given", "across", "present"}

    words_title = [w.lower().strip(".,;:()[]{}\"'") for w in title.split()]
    words_abstract = [w.lower().strip(".,;:()[]{}\"'") for w in abstract.split()[:150]]

    # Find bigrams and trigrams from title
    bigrams = []
    for i in range(len(words_title) - 1):
        w1, w2 = words_title[i], words_title[i + 1]
        if w1 not in stop and w2 not in stop and len(w1) > 2 and len(w2) > 2:
            bigrams.append(f"{w1} {w2}")

    # Frequent meaningful unigrams
    word_freq = {}
    for w in words_title + words_abstract:
        if w not in stop and len(w) > 3 and w.isalpha():
            word_freq[w] = word_freq.get(w, 0) + 1

    # Title words are more important
    for w in words_title:
        if w not in stop and len(w) > 3 and w.isalpha():
            word_freq[w] = word_freq.get(w, 0) + 3

    top_words = sorted(word_freq, key=word_freq.get, reverse=True)[:6]
    keywords = bigrams[:2] + top_words[:4]
    # Deduplicate
    seen = set()
    result = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result[:5] if result else ["research"]


def synthesize_counts(year: int, rng: random.Random) -> tuple[int, int]:
    """Generate realistic citation and reference counts based on year."""
    age = 2025 - year
    # Older papers have more citations on average
    if age <= 1:
        cite_base = rng.randint(0, 25)
    elif age <= 3:
        cite_base = rng.randint(5, 120)
    elif age <= 5:
        cite_base = rng.randint(15, 350)
    else:
        cite_base = rng.randint(30, 800)

    # Some papers are highly cited (power law tail)
    if rng.random() < 0.08:
        cite_base = int(cite_base * rng.uniform(3, 8))

    reference_count = rng.randint(15, 85)
    return cite_base, reference_count


def main():
    rng = random.Random(42)

    # Step 1: Fetch papers from Arxiv
    print("=" * 60)
    print("Fetching papers from Arxiv API...")
    print("=" * 60)

    all_raw_papers = []
    for cat in CATEGORY_MAP:
        papers = fetch_arxiv(cat, PER_CATEGORY)
        all_raw_papers.extend(papers)
        time.sleep(3.5)  # Be polite to the API

    print(f"\nTotal raw papers fetched: {len(all_raw_papers)}")

    # Deduplicate by arxiv_id
    seen_ids = set()
    unique_papers = []
    for p in all_raw_papers:
        if p["arxiv_id"] not in seen_ids:
            seen_ids.add(p["arxiv_id"])
            unique_papers.append(p)

    print(f"After dedup: {len(unique_papers)}")

    # Shuffle and limit to ~200
    rng.shuffle(unique_papers)
    unique_papers = unique_papers[:200]
    print(f"Using {len(unique_papers)} papers")

    # Step 2: Build author registry (deduplicate by name)
    print("\nBuilding author registry...")
    author_name_to_id = {}
    authors_list = []
    author_id_counter = 1

    affiliations = [
        "Stanford University", "MIT", "Carnegie Mellon University",
        "UC Berkeley", "Harvard University", "University of Oxford",
        "ETH Zurich", "University of Toronto", "Tsinghua University",
        "Max Planck Institute", "Google Research", "DeepMind",
        "Microsoft Research", "Meta AI", "University of Cambridge",
        "Princeton University", "Caltech", "University of Tokyo",
        "EPFL", "INRIA", "Seoul National University",
        "University of Michigan", "Georgia Tech", "Columbia University",
        "University of Washington", "NYU", "Imperial College London",
        "TU Munich", "Chinese Academy of Sciences", "University of Montreal",
    ]

    for raw_p in unique_papers:
        for aname in raw_p["authors"][:5]:  # limit authors per paper
            if aname not in author_name_to_id:
                field, _ = CATEGORY_MAP.get(raw_p["primary_category"], ("Computer Science", "General"))
                author_name_to_id[aname] = author_id_counter
                authors_list.append({
                    "id": author_id_counter,
                    "name": aname,
                    "affiliation": rng.choice(affiliations),
                    "h_index": rng.randint(5, 85),
                    "total_citations": rng.randint(200, 25000),
                    "paper_count": rng.randint(8, 150),
                    "fields": [field],
                    "email": aname.split()[-1].lower() + str(author_id_counter) + "@research.edu",
                })
                author_id_counter += 1

    # Limit to 80 authors (take the most-referenced ones + random sample)
    # Count how many papers each author appears in
    author_paper_count = {}
    for raw_p in unique_papers:
        for aname in raw_p["authors"][:5]:
            aid = author_name_to_id.get(aname)
            if aid:
                author_paper_count[aid] = author_paper_count.get(aid, 0) + 1

    # Sort by frequency, keep top 80
    sorted_authors = sorted(authors_list, key=lambda a: author_paper_count.get(a["id"], 0), reverse=True)
    kept_authors = sorted_authors[:80]
    kept_author_ids = {a["id"] for a in kept_authors}

    # Renumber authors 1..N
    old_to_new_author = {}
    for i, a in enumerate(kept_authors, 1):
        old_to_new_author[a["id"]] = i
        a["id"] = i

    print(f"Authors: {len(kept_authors)}")

    # Step 3: Build journal registry
    print("Building journal registry...")
    journal_list = []
    journal_name_to_id = {}
    journal_id = 1
    for field, jlist in FIELD_JOURNALS.items():
        for jname, publisher, impact, oa in jlist:
            journal_name_to_id[jname] = journal_id
            journal_list.append({
                "id": journal_id,
                "name": jname,
                "publisher": publisher,
                "impact_factor": impact,
                "field": field,
                "is_open_access": oa,
                "paper_count": 0,
            })
            journal_id += 1

    print(f"Journals: {len(journal_list)}")

    # Step 4: Build papers
    print("Building paper records...")
    papers_out = []
    skipped = 0

    for idx, raw_p in enumerate(unique_papers, 1):
        field, subfield = CATEGORY_MAP.get(raw_p["primary_category"], ("Computer Science", "General"))

        # Map authors to kept IDs
        paper_author_ids = []
        for aname in raw_p["authors"][:5]:
            old_id = author_name_to_id.get(aname)
            if old_id and old_id in kept_author_ids:
                new_id = old_to_new_author[old_id]
                paper_author_ids.append(new_id)

        if not paper_author_ids:
            # Assign a random author from the same field
            field_authors = [a for a in kept_authors if field in a["fields"]]
            if not field_authors:
                field_authors = kept_authors[:5]
            paper_author_ids = [rng.choice(field_authors)["id"]]

        # Pick a journal
        field_journals = FIELD_JOURNALS.get(field, FIELD_JOURNALS["Computer Science"])
        jname, _, _, _ = rng.choice(field_journals)
        jid = journal_name_to_id[jname]

        citation_count, reference_count = synthesize_counts(raw_p["year"], rng)
        keywords = extract_keywords(raw_p["title"], raw_p["abstract"])
        methodology = guess_methodology(raw_p["abstract"])

        paper = {
            "id": idx,
            "title": raw_p["title"],
            "authors": paper_author_ids,
            "abstract": raw_p["abstract"],
            "journal": jname,
            "year": raw_p["year"],
            "volume": rng.randint(1, 150),
            "issue": rng.randint(1, 12),
            "pages": f"{rng.randint(1, 500)}-{rng.randint(501, 999)}",
            "doi": f"10.{rng.randint(1000,9999)}/arxiv.{raw_p['arxiv_id'].replace('/', '.')}",
            "keywords": keywords,
            "field": field,
            "subfield": subfield,
            "citation_count": citation_count,
            "reference_count": reference_count,
            "pdf_url": f"https://arxiv.org/pdf/{raw_p['arxiv_id']}",
            "is_open_access": rng.random() < 0.55,
            "methodology": methodology,
        }
        papers_out.append(paper)

    print(f"Papers: {len(papers_out)}")

    # Update journal paper_count
    for p in papers_out:
        jid = journal_name_to_id[p["journal"]]
        for j in journal_list:
            if j["id"] == jid:
                j["paper_count"] += 1

    # Update author paper_count / total_citations / fields
    author_by_id = {a["id"]: a for a in kept_authors}
    for a in kept_authors:
        a["paper_count"] = 0
        a["total_citations"] = 0
        a["fields"] = set()
    for p in papers_out:
        for aid in p["authors"]:
            if aid in author_by_id:
                author_by_id[aid]["paper_count"] += 1
                author_by_id[aid]["total_citations"] += p["citation_count"]
                author_by_id[aid]["fields"].add(p["field"])
    for a in kept_authors:
        a["fields"] = sorted(a["fields"])
        if a["paper_count"] == 0:
            a["paper_count"] = rng.randint(5, 30)
        a["h_index"] = min(a["h_index"], a["paper_count"])

    # Step 5: Build citations (realistic network)
    print("Building citation network...")
    citations_out = []
    cit_id = 1
    paper_ids = [p["id"] for p in papers_out]

    # Group papers by field for more realistic intra-field citations
    field_papers = {}
    for p in papers_out:
        field_papers.setdefault(p["field"], []).append(p["id"])

    for p in papers_out:
        # Each paper cites 1-5 other papers (that exist in our dataset)
        same_field = [pid for pid in field_papers.get(p["field"], []) if pid != p["id"]]
        other_field = [pid for pid in paper_ids if pid != p["id"] and pid not in same_field]

        num_cites = rng.randint(1, min(5, len(same_field) + len(other_field)))
        # 70% same-field, 30% cross-field
        cited_ids = set()
        for _ in range(num_cites):
            if same_field and (rng.random() < 0.7 or not other_field):
                cited_ids.add(rng.choice(same_field))
            elif other_field:
                cited_ids.add(rng.choice(other_field))

        for cited_id in cited_ids:
            citations_out.append({
                "id": cit_id,
                "citing_paper_id": p["id"],
                "cited_paper_id": cited_id,
            })
            cit_id += 1

    print(f"Citations: {len(citations_out)}")

    # Step 6: Build users
    print("Building users...")
    users_out = [
        {
            "id": 1,
            "username": "jsmith_researcher",
            "name": "John Smith",
            "email": "j.smith@university.edu",
            "password_hash": "pbkdf2:sha256:research123",
            "saved_papers": sorted(rng.sample(paper_ids, min(8, len(paper_ids)))),
            "reading_list": sorted(rng.sample(paper_ids, min(6, len(paper_ids)))),
            "following_authors": sorted(rng.sample(range(1, len(kept_authors) + 1), 4)),
            "alerts": ["deep learning", "transformers"],
        },
        {
            "id": 2,
            "username": "emily_bio",
            "name": "Emily Watson",
            "email": "e.watson@biolab.org",
            "password_hash": "pbkdf2:sha256:biology456",
            "saved_papers": sorted(rng.sample(paper_ids, min(6, len(paper_ids)))),
            "reading_list": sorted(rng.sample(paper_ids, min(5, len(paper_ids)))),
            "following_authors": sorted(rng.sample(range(1, len(kept_authors) + 1), 3)),
            "alerts": ["quantum computing", "optimization"],
        },
        {
            "id": 3,
            "username": "physicist_alex",
            "name": "Alex Kowalski",
            "email": "a.kowalski@physics.eu",
            "password_hash": "pbkdf2:sha256:physics789",
            "saved_papers": sorted(rng.sample(paper_ids, min(7, len(paper_ids)))),
            "reading_list": sorted(rng.sample(paper_ids, min(4, len(paper_ids)))),
            "following_authors": sorted(rng.sample(range(1, len(kept_authors) + 1), 3)),
            "alerts": ["quantum computing", "superconductivity"],
        },
        {
            "id": 4,
            "username": "ml_maya",
            "name": "Maya Patel",
            "email": "m.patel@mlresearch.org",
            "password_hash": "pbkdf2:sha256:mldata012",
            "saved_papers": sorted(rng.sample(paper_ids, min(5, len(paper_ids)))),
            "reading_list": sorted(rng.sample(paper_ids, min(5, len(paper_ids)))),
            "following_authors": sorted(rng.sample(range(1, len(kept_authors) + 1), 4)),
            "alerts": ["machine learning", "computer vision"],
        },
        {
            "id": 5,
            "username": "math_liu",
            "name": "Wei Liu",
            "email": "w.liu@mathcenter.cn",
            "password_hash": "pbkdf2:sha256:mathpi345",
            "saved_papers": sorted(rng.sample(paper_ids, min(6, len(paper_ids)))),
            "reading_list": sorted(rng.sample(paper_ids, min(4, len(paper_ids)))),
            "following_authors": sorted(rng.sample(range(1, len(kept_authors) + 1), 3)),
            "alerts": ["optimization", "probability"],
        },
    ]

    print(f"Users: {len(users_out)}")

    # Step 7: Write output
    print("\n" + "=" * 60)
    print(f"Writing data to {SITE_DATA_DIR}")
    print("=" * 60)

    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    def write_json(name, data):
        path = SITE_DATA_DIR / name
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False))
        print(f"  Wrote {name}: {len(data)} records")

    write_json("papers.json", papers_out)
    write_json("authors.json", kept_authors)
    write_json("journals.json", journal_list)
    write_json("users.json", users_out)
    write_json("citations.json", citations_out)

    # Also update .pristine
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["papers.json", "authors.json", "journals.json", "users.json", "citations.json"]:
        src = SITE_DATA_DIR / name
        dst = PRISTINE_DIR / name
        dst.write_text(src.read_text())
    print(f"\n  Copied to .pristine/")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    fields = {}
    for p in papers_out:
        fields[p["field"]] = fields.get(p["field"], 0) + 1
    for f, c in sorted(fields.items()):
        print(f"  {f}: {c} papers")
    print(f"  Total papers: {len(papers_out)}")
    print(f"  Total authors: {len(kept_authors)}")
    print(f"  Total journals: {len(journal_list)}")
    print(f"  Total citations: {len(citations_out)}")
    print(f"  Total users: {len(users_out)}")
    print("\nDone!")


if __name__ == "__main__":
    main()
