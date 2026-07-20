"""Expand conference-review-submission (PeerPortal) base data.

The site ships with 350 papers (349 in iclr-2017, 1 in miniweb-workshop-2026),
6 venues and 4 users.  This script adds 14 archival venues (2012-2015 editions
of ICLR/ICML/NeurIPS/ACL/EMNLP/NAACL/AAAI/CVPR/COLING/IJCAI) and ~4,700
synthetic papers spread across them, each with PeerRead-style review JSON
(DATE / TITLE / IS_META_REVIEW / comments / OTHER_KEYS / RECOMMENDATION /
REVIEWER_CONFIDENCE keys) matching the existing iclr-2017 records.

Deliberate safety properties (annotation tasks must stay valid):
  * INSERT-ONLY: no existing row is updated or deleted.
  * No new papers in iclr-2017 or miniweb-workshop-2026, so the recorded
    review-submission task on paper 306 (its detail page, related-papers list,
    venue listing, stats and counts) is untouched.
  * All new venues have year <= 2015, strictly older than every existing venue
    (min existing year is 2016), so the venues page — sorted by -year — keeps
    its current top ordering; the 14 new venues append below.
  * Each new venue holds < 500 papers, keeping the per-venue stats page
    (which loads a whole venue into Python) under the render budget.
  * New paper ids are numeric strings 10000+, disjoint from existing ids
    (0-793) so the external-content FTS index (content_rowid=id) stays sound.
  * Users table untouched (login/console flows depend on the 4 seed users).

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_conference_review_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "conference-review-submission-expansion-2026-07-20"

rng = random.Random(20260720)

PAPER_ID_START = 10000

# ---------------------------------------------------------------------------
# Venues (all strictly older than the oldest existing venue, neurips-2016)
# ---------------------------------------------------------------------------

VENUES = [
    # id, name, full_name, year, location, dates, deadline, notification,
    # review_visibility, status, n_papers, topic domain key
    ("iclr-2015", "ICLR 2015", "International Conference on Learning Representations",
     2015, "San Diego, USA", "May 7-9, 2015", "December 19, 2014", "March 13, 2015",
     "public", "decisions_posted", 345, "dl"),
    ("iclr-2014", "ICLR 2014", "International Conference on Learning Representations",
     2014, "Banff, Canada", "April 14-16, 2014", "December 20, 2013", "February 25, 2014",
     "public", "decisions_posted", 330, "dl"),
    ("icml-2015", "ICML 2015", "International Conference on Machine Learning",
     2015, "Lille, France", "July 6-11, 2015", "February 6, 2015", "April 27, 2015",
     "after_decision", "archived", 345, "ml"),
    ("icml-2014", "ICML 2014", "International Conference on Machine Learning",
     2014, "Beijing, China", "June 21-26, 2014", "January 31, 2014", "April 9, 2014",
     "after_decision", "archived", 335, "ml"),
    ("neurips-2015", "NeurIPS 2015", "Conference on Neural Information Processing Systems",
     2015, "Montreal, Canada", "December 7-12, 2015", "June 5, 2015", "September 4, 2015",
     "after_decision", "archived", 345, "ml"),
    ("neurips-2014", "NeurIPS 2014", "Conference on Neural Information Processing Systems",
     2014, "Montreal, Canada", "December 8-13, 2014", "June 6, 2014", "September 9, 2014",
     "after_decision", "archived", 330, "ml"),
    ("acl-2015", "ACL 2015", "Annual Meeting of the Association for Computational Linguistics",
     2015, "Beijing, China", "July 26-31, 2015", "February 27, 2015", "April 23, 2015",
     "assigned_only", "archived", 340, "nlp"),
    ("emnlp-2015", "EMNLP 2015", "Conference on Empirical Methods in Natural Language Processing",
     2015, "Lisbon, Portugal", "September 17-21, 2015", "May 29, 2015", "July 24, 2015",
     "assigned_only", "archived", 335, "nlp"),
    ("emnlp-2014", "EMNLP 2014", "Conference on Empirical Methods in Natural Language Processing",
     2014, "Doha, Qatar", "October 25-29, 2014", "June 12, 2014", "August 12, 2014",
     "assigned_only", "archived", 330, "nlp"),
    ("naacl-2015", "NAACL 2015", "Conference of the North American Chapter of the Association for Computational Linguistics",
     2015, "Denver, USA", "May 31 - June 5, 2015", "December 4, 2014", "February 20, 2015",
     "assigned_only", "archived", 335, "nlp"),
    ("aaai-2015", "AAAI 2015", "AAAI Conference on Artificial Intelligence",
     2015, "Austin, USA", "January 25-30, 2015", "September 15, 2014", "November 7, 2014",
     "assigned_only", "archived", 340, "ai"),
    ("cvpr-2015", "CVPR 2015", "IEEE Conference on Computer Vision and Pattern Recognition",
     2015, "Boston, USA", "June 7-12, 2015", "November 14, 2014", "February 27, 2015",
     "after_decision", "archived", 345, "cv"),
    ("coling-2014", "COLING 2014", "International Conference on Computational Linguistics",
     2014, "Dublin, Ireland", "August 23-29, 2014", "March 21, 2014", "May 20, 2014",
     "assigned_only", "archived", 320, "nlp"),
    ("ijcai-2013", "IJCAI 2013", "International Joint Conference on Artificial Intelligence",
     2013, "Beijing, China", "August 3-9, 2013", "January 26, 2013", "April 9, 2013",
     "assigned_only", "archived", 325, "ai"),
]

VENUE_DESCRIPTIONS = {
    "iclr": "The International Conference on Learning Representations is the premier venue for research on all aspects of representation learning, including deep learning, feature learning, and optimization for machine learning.",
    "icml": "ICML is the leading international academic conference in machine learning. Along with NeurIPS and ICLR, it is one of the three primary conferences in this field.",
    "neurips": "NeurIPS is a multi-track machine learning and computational neuroscience conference that includes invited talks, demonstrations, symposia, and oral and poster presentations.",
    "acl": "ACL is the premier international conference in computational linguistics and natural language processing.",
    "emnlp": "EMNLP is a leading conference in natural language processing, emphasizing empirical methods and data-driven approaches to language understanding.",
    "naacl": "NAACL brings together researchers in computational linguistics and natural language processing from across the Americas and beyond.",
    "aaai": "The AAAI Conference on Artificial Intelligence promotes research in artificial intelligence and scientific exchange among AI researchers, practitioners, scientists, and engineers.",
    "cvpr": "CVPR is the premier annual computer vision event comprising the main conference and several co-located workshops and short courses.",
    "coling": "COLING is one of the oldest and most prestigious conferences in computational linguistics, held every two years under the auspices of the International Committee on Computational Linguistics.",
    "ijcai": "IJCAI is the main international gathering of researchers in artificial intelligence, covering the full breadth of AI research.",
}

# ---------------------------------------------------------------------------
# Vocabulary (era-appropriate, 2012-2015)
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Wei", "Yuki", "Marta", "Tomas", "Elena", "Rahul", "Ingrid", "Marco",
    "Sofia", "Daniel", "Mei", "Andrei", "Claire", "Hassan", "Petra", "Kenji",
    "Laura", "Viktor", "Ana", "Jorge", "Nadia", "Sven", "Priyanka", "Olivier",
    "Katarzyna", "Bo", "Fatima", "Lars", "Chiara", "Dmitri", "Hannah", "Tao",
    "Isabelle", "Farid", "Greta", "Hiroshi", "Lucia", "Emil", "Rosa", "Anders",
]
LAST_NAMES = [
    "Chen", "Tanaka", "Kowalski", "Novak", "Petrova", "Iyer", "Larsen",
    "Ricci", "Alves", "Kim", "Zhang", "Popescu", "Dubois", "Karimi",
    "Novotna", "Sato", "Moreno", "Sokolov", "Silva", "Ramirez", "Haddad",
    "Berg", "Nair", "Lambert", "Wozniak", "Liu", "Rahmani", "Nilsson",
    "Bianchi", "Volkov", "Schmidt", "Wang", "Fournier", "Ahmadi", "Lindgren",
    "Yamamoto", "Costa", "Johansson", "Ferreira", "Eriksson",
]

TOPICS = {
    "dl": [
        "Convolutional Networks", "Recurrent Neural Networks", "Autoencoders",
        "Restricted Boltzmann Machines", "Deep Belief Networks", "Dropout Regularization",
        "Rectified Linear Units", "Stochastic Gradient Descent", "Feature Learning",
        "Attention Mechanisms", "Memory Networks", "Curriculum Learning",
        "Adversarial Examples", "Batch Normalization", "Network Distillation",
    ],
    "ml": [
        "Kernel Methods", "Gaussian Processes", "Variational Inference",
        "Bayesian Optimization", "Online Learning", "Bandit Algorithms",
        "Matrix Factorization", "Spectral Clustering", "Random Forests",
        "Submodular Optimization", "Stochastic Optimization", "Metric Learning",
        "Latent Variable Models", "Structured Prediction", "Transfer Learning",
    ],
    "nlp": [
        "Word Embeddings", "Dependency Parsing", "Machine Translation",
        "Sentiment Analysis", "Named Entity Recognition", "Topic Models",
        "Semantic Role Labeling", "Coreference Resolution", "Question Answering",
        "Text Summarization", "Morphological Analysis", "Discourse Parsing",
        "Relation Extraction", "Distributional Semantics", "Language Modeling",
    ],
    "ai": [
        "Monte Carlo Tree Search", "Constraint Satisfaction", "Automated Planning",
        "Knowledge Base Completion", "Probabilistic Graphical Models",
        "Multi-Agent Coordination", "Heuristic Search", "Answer Set Programming",
        "Game-Theoretic Reasoning", "Ontology Alignment", "Reinforcement Learning",
        "Belief Revision", "Preference Elicitation", "Description Logics",
    ],
    "cv": [
        "Object Detection", "Image Segmentation", "Scene Understanding",
        "Optical Flow", "Face Recognition", "Pose Estimation",
        "Image Retrieval", "Action Recognition", "Depth Estimation",
        "Saliency Detection", "Fine-Grained Classification", "Image Captioning",
        "Stereo Matching", "Visual Tracking", "Texture Synthesis",
    ],
}

TITLE_TEMPLATES = [
    "{a} for {b}",
    "{a} via {b}",
    "Learning {a} with {b}",
    "Efficient {a} for Large-Scale {b}",
    "A {adj} Approach to {a}",
    "On the {prop} of {a}",
    "Improving {a} using {b}",
    "Joint {a} and {b}",
    "Scalable {a} with Applications to {b}",
    "Towards {adj} {a}",
    "Revisiting {a}: A {adj} Perspective",
    "{a} Meets {b}: A Unified Framework",
    "Fast and Robust {a}",
    "Semi-Supervised {a} through {b}",
    "Unsupervised {a} by {b}",
]
ADJECTIVES = ["Probabilistic", "Bayesian", "Discriminative", "Generative",
              "Nonparametric", "Structured", "Sparse", "Convex", "Hierarchical",
              "Distributed", "Incremental", "Robust"]
PROPERTIES = ["Convergence", "Sample Complexity", "Expressiveness",
              "Generalization", "Stability", "Identifiability", "Consistency"]

ABSTRACT_OPENERS = [
    "We present a novel method for {a_l} that combines ideas from {b_l} with recent advances in optimization.",
    "This paper studies the problem of {a_l} in settings where labeled data is scarce and annotation is expensive.",
    "We propose a new framework for {a_l} based on {b_l}, addressing key limitations of prior approaches.",
    "Recent progress in {b_l} has opened new opportunities for tackling {a_l} at scale.",
    "We investigate the theoretical foundations of {a_l} and derive new guarantees under mild assumptions.",
]
ABSTRACT_MIDDLES = [
    "Our approach introduces a {adj_l} objective that can be optimized efficiently with standard first-order methods.",
    "The key insight is to exploit structure in the data through a {adj_l} decomposition, which reduces computational cost substantially.",
    "We derive an inference procedure whose per-iteration complexity is linear in the number of training examples.",
    "Unlike previous work, our formulation handles noisy and incomplete observations without additional supervision.",
    "We further show how the model can be trained end-to-end, removing the need for hand-engineered features.",
]
ABSTRACT_CLOSERS = [
    "Experiments on several standard benchmarks demonstrate consistent improvements over strong baselines.",
    "Empirical results show that our method achieves state-of-the-art performance while being an order of magnitude faster.",
    "An extensive evaluation confirms the effectiveness of the proposed approach across diverse datasets.",
    "We release our implementation to facilitate reproducibility and future research.",
    "Ablation studies highlight the contribution of each component of the model.",
]

REVIEW_TITLES_POS = [
    "Solid contribution with convincing experiments",
    "Well-written paper, novel idea",
    "Interesting approach, strong empirical results",
    "Clear exposition and thorough evaluation",
    "Nice combination of theory and practice",
    "Good paper, minor concerns about scalability",
]
REVIEW_TITLES_MID = [
    "Interesting idea but evaluation could be stronger",
    "Reasonable contribution, incremental over prior work",
    "Promising direction, experiments somewhat limited",
    "Decent paper with some clarity issues",
    "Borderline: novelty is modest",
]
REVIEW_TITLES_NEG = [
    "Limited novelty over existing methods",
    "Experimental evaluation is not convincing",
    "Unclear contribution, weak baselines",
    "Major concerns about the experimental setup",
    "Poorly motivated and hard to follow",
]
REVIEW_COMMENTS_POS = [
    "The paper is well organized and the proposed method is clearly motivated. The experiments cover a good range of datasets and the improvements are consistent. I would have liked to see a comparison against more recent baselines, but overall this is a solid contribution.",
    "This work addresses an important problem and the technical development is sound. The analysis in Section 4 is particularly nice. Minor comments: some notation is overloaded, and the related work section could better position the paper.",
    "A clean idea executed well. The empirical results are convincing and the ablations answer most of my questions. I recommend acceptance.",
]
REVIEW_COMMENTS_MID = [
    "The proposed method is reasonable but the novelty relative to prior work is incremental. The experiments show modest gains, and it is unclear whether the improvements are statistically significant. Adding error bars and more baselines would strengthen the paper.",
    "The paper tackles a relevant problem, but the presentation needs work: several definitions are introduced without motivation and the experimental protocol is under-specified. The results are encouraging but not conclusive.",
    "Interesting direction. However, the evaluation is restricted to small datasets and the comparison omits several standard baselines. I lean slightly positive but would not argue strongly for acceptance.",
]
REVIEW_COMMENTS_NEG = [
    "The contribution is difficult to assess because the baselines are weak and the datasets are non-standard. The claimed improvements may simply reflect hyperparameter tuning. I cannot recommend acceptance in the current form.",
    "The paper overlaps substantially with prior work that is not cited, and the technical novelty is limited. The writing also needs significant polishing before publication.",
    "The motivation is unclear and the experimental section does not support the central claims. Important details needed for reproduction are missing.",
]
META_COMMENTS_ACC = [
    "The reviewers agree that the paper makes a solid contribution and the rebuttal addressed the main concerns. Recommendation: accept.",
    "All reviewers found the approach interesting and the evaluation adequate. The authors are encouraged to incorporate the reviewers' suggestions in the camera-ready version. Accept.",
]
META_COMMENTS_REJ = [
    "The reviewers raised substantial concerns about novelty and the strength of the empirical evaluation, and the rebuttal did not fully resolve them. Recommendation: reject.",
    "While the direction is promising, the committee felt the paper is not ready for publication in its current form. We encourage the authors to strengthen the experiments and resubmit.",
]

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Review-period month per venue (roughly between deadline and notification)
REVIEW_MONTHS = {
    "iclr-2015": (2015, [1, 2]), "iclr-2014": (2014, [1, 2]),
    "icml-2015": (2015, [3, 4]), "icml-2014": (2014, [2, 3]),
    "neurips-2015": (2015, [7, 8]), "neurips-2014": (2014, [7, 8]),
    "acl-2015": (2015, [3, 4]), "emnlp-2015": (2015, [6, 7]),
    "emnlp-2014": (2014, [7, 8]), "naacl-2015": (2015, [1, 2]),
    "aaai-2015": (2014, [10, 11]), "cvpr-2015": (2015, [1, 2]),
    "coling-2014": (2014, [4, 5]), "ijcai-2013": (2013, [2, 3]),
}


def make_authors():
    n = rng.choices([2, 3, 4, 5], weights=[30, 40, 20, 10])[0]
    names = set()
    while len(names) < n:
        names.add(f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}")
    return ", ".join(sorted(names, key=lambda _: rng.random()))


def make_title(domain, used_titles):
    topics = TOPICS[domain]
    for _ in range(50):
        a, b = rng.sample(topics, 2)
        tpl = rng.choice(TITLE_TEMPLATES)
        title = tpl.format(a=a, b=b, adj=rng.choice(ADJECTIVES),
                           prop=rng.choice(PROPERTIES))
        if title not in used_titles:
            used_titles.add(title)
            return title, a, b
    # Fall back: disambiguate with an adjective prefix
    title = f"{rng.choice(ADJECTIVES)} {title}"
    used_titles.add(title)
    return title, a, b


def make_abstract(a, b):
    parts = [
        rng.choice(ABSTRACT_OPENERS).format(a_l=a.lower(), b_l=b.lower()),
        rng.choice(ABSTRACT_MIDDLES).format(adj_l=rng.choice(ADJECTIVES).lower()),
        rng.choice(ABSTRACT_CLOSERS),
    ]
    return " ".join(parts)


def make_reviews(venue_id, venue_name, accepted):
    year, months = REVIEW_MONTHS[venue_id]
    n = rng.choices([2, 3, 4], weights=[15, 60, 25])[0]
    reviews = []
    if accepted:
        recs = [rng.randint(6, 9) for _ in range(n)]
    else:
        recs = [rng.randint(2, 5) for _ in range(n)]
        if n >= 3 and rng.random() < 0.35:
            recs[0] = 6  # one dissenting positive review
    for i, rec in enumerate(recs, start=1):
        if rec >= 6:
            title = rng.choice(REVIEW_TITLES_POS)
            comments = rng.choice(REVIEW_COMMENTS_POS)
        elif rec == 5:
            title = rng.choice(REVIEW_TITLES_MID)
            comments = rng.choice(REVIEW_COMMENTS_MID)
        else:
            title = rng.choice(REVIEW_TITLES_NEG)
            comments = rng.choice(REVIEW_COMMENTS_NEG)
        month = rng.choice(months)
        date = f"{rng.randint(1, 28):02d} {MONTH_ABBR[month - 1]} {year}"
        reviews.append({
            "DATE": date,
            "TITLE": title,
            "IS_META_REVIEW": False,
            "comments": comments,
            "OTHER_KEYS": f"{venue_name} conference AnonReviewer{i}",
            "RECOMMENDATION": rec,
            "REVIEWER_CONFIDENCE": rng.randint(2, 5),
        })
    # Meta review for decided venues
    if rng.random() < 0.7:
        month = months[-1]
        reviews.append({
            "DATE": f"{rng.randint(1, 28):02d} {MONTH_ABBR[month - 1]} {year}",
            "TITLE": f"{venue_name} committee final decision",
            "IS_META_REVIEW": True,
            "comments": rng.choice(META_COMMENTS_ACC if accepted else META_COMMENTS_REJ),
            "OTHER_KEYS": f"{venue_name} pcs",
        })
    return reviews


def build_rows():
    """Generate (venue_rows, paper_rows) deterministically."""
    venue_rows = []
    paper_rows = []
    next_id = PAPER_ID_START
    used_titles = set()

    for (vid, name, full_name, year, location, dates, deadline, notification,
         visibility, status, n_papers, domain) in VENUES:
        series = vid.split("-")[0]
        venue_rows.append({
            "id": vid, "name": name, "full_name": full_name, "year": year,
            "type": "conference", "location": location, "dates": dates,
            "website": "", "submission_deadline": deadline,
            "notification_date": notification,
            "review_visibility": visibility, "status": status,
            "description": VENUE_DESCRIPTIONS[series],
        })
        # ~25% acceptance rate for main conferences
        accept_rate = 0.25 if series in ("iclr", "icml", "neurips", "cvpr") else 0.28
        for _ in range(n_papers):
            title, a, b = make_title(domain, used_titles)
            accepted = 1 if rng.random() < accept_rate else 0
            paper_rows.append({
                "id": str(next_id),
                "title": title,
                "authors": make_authors(),
                "abstract": make_abstract(a, b),
                "conference": f"{name} conference submission",
                "venue_id": vid,
                "accepted": accepted,
                "reviews": json.dumps(make_reviews(vid, name, accepted)),
                "histories": "[]",
                "_source_file": f"{next_id}.json",
            })
            next_id += 1
    return venue_rows, paper_rows


def main():
    dry_run = "--dry-run" in sys.argv
    venue_rows, paper_rows = build_rows()

    print(f"Generated {len(venue_rows)} venues, {len(paper_rows)} papers")
    per_venue = {}
    for p in paper_rows:
        per_venue[p["venue_id"]] = per_venue.get(p["venue_id"], 0) + 1
    for vid, cnt in per_venue.items():
        assert cnt < 500, f"{vid} has {cnt} papers (>=500)"
        print(f"  {vid}: {cnt} papers")

    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        # Safety checks against existing data
        existing_vids = {r[0] for r in conn.execute(
            "SELECT id FROM conference_review_submission_venues")}
        clash = existing_vids & {v["id"] for v in venue_rows}
        assert not clash, f"venue id clash: {clash}"
        min_year = conn.execute(
            "SELECT MIN(year) FROM conference_review_submission_venues").fetchone()[0]
        assert all(v["year"] < min_year for v in venue_rows), \
            "new venues must be older than all existing venues"
        pid_clash = conn.execute(
            "SELECT COUNT(*) FROM conference_review_submission_papers "
            "WHERE CAST(id AS INT) >= ?", (PAPER_ID_START,)).fetchone()[0]
        assert pid_clash == 0, "paper id range already in use"
        assert not any(p["venue_id"] in ("iclr-2017", "miniweb-workshop-2026")
                       for p in paper_rows)

        if dry_run:
            print("\n--dry-run: no rows written. Sample paper:")
            print(json.dumps(paper_rows[0], indent=1)[:900])
            return

        vcols = list(venue_rows[0].keys())
        conn.executemany(
            f"INSERT INTO conference_review_submission_venues "
            f"({', '.join('['+c+']' for c in vcols)}) "
            f"VALUES ({', '.join('?' * len(vcols))})",
            [tuple(v[c] for c in vcols) for v in venue_rows])
        pcols = list(paper_rows[0].keys())
        conn.executemany(
            f"INSERT INTO conference_review_submission_papers "
            f"({', '.join('['+c+']' for c in pcols)}) "
            f"VALUES ({', '.join('?' * len(pcols))})",
            [tuple(p[c] for c in pcols) for p in paper_rows])
        # Sync external-content FTS index
        conn.execute(
            "INSERT INTO fts_conference_review_submission_papers"
            "(fts_conference_review_submission_papers) VALUES('rebuild')")
        conn.commit()
        print("Inserted and committed. FTS index rebuilt.")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = {
            "site": "conference-review-submission",
            "date": "2026-07-20",
            "venues": [v["id"] for v in venue_rows],
            "papers": [p["id"] for p in paper_rows],
        }
        (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(backup, indent=1))
        print(f"Backup written to {BACKUP_DIR / 'inserted_ids.json'}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
