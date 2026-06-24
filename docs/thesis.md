# MiniWeb: A Macro-Annotated Web Benchmark for Fine-Grained Agent Evaluation

## Abstract

We present MiniWeb, a large-scale web agent benchmark of 78 fully-local websites spanning 15 domain categories, with 4,680 human-written tasks. Each task is annotated with its constituent **macros** — atomic interaction skills like `search_by_query` or `filter_by_dropdown` — drawn from a closed vocabulary of 163 macros induced from four existing benchmarks. Unlike prior benchmarks that report only aggregate pass rates, MiniWeb enables **skill-decomposed evaluation**: measuring which specific interaction capabilities an agent has or lacks, whether skills transfer across domains, and how macro composition predicts task difficulty. We evaluate N frontier agents and find that (1) per-macro pass rates are remarkably consistent across websites, validating macros as transferable skills; (2) task difficulty is predictable from macro composition; and (3) agents exhibit distinct skill profiles — strengths and blind spots that aggregate scores obscure. MiniWeb and its macro vocabulary are publicly available at [url].

---

## 1. Introduction

Web agent benchmarks have driven rapid progress in autonomous web navigation, yet a fundamental limitation persists: they measure **what** agents accomplish but not **how**. When an agent scores 60% on WebArena (Zhou et al., 2024), we know 488 tasks failed — but not whether the failures stem from inability to use dropdown filters, difficulty composing multi-step workflows, or confusion with specific UI patterns. This opacity makes it difficult to diagnose agent weaknesses, predict performance on unseen websites, or design targeted training curricula.

We argue the root cause is that existing benchmarks are designed **top-down**: researchers select websites, then write tasks, hoping for implicit skill coverage. The resulting task distributions are uncontrolled — some interaction patterns are exercised dozens of times while others appear once or not at all.

MiniWeb takes a **bottom-up** approach. We first derive a structured vocabulary of atomic interaction skills — **macros** — by systematically labeling 15,728 tasks from four existing benchmarks (WebArena, Mind2Web, WebShop, WebVoyager). We then construct 78 websites specifically designed to exercise these macros, and crowdsource 4,680 tasks with explicit macro annotations. This enables a new evaluation paradigm: instead of a single number, MiniWeb produces a **skill profile** — a vector of per-macro pass rates that reveals exactly what an agent can and cannot do.

**Contributions:**
1. A **macro vocabulary** of 163 atomic web interaction skills, empirically induced from four benchmarks with human-in-the-loop deduplication (§2).
2. **MiniWeb**, a benchmark of 78 self-hosted websites across 15 domains with 4,680 macro-annotated tasks and automated verification (§3).
3. A **construction pipeline** combining human design with LLM-assisted code generation and browser-agent validation (§4).
4. **Experiments** demonstrating that macros are transferable skills, that macro composition predicts difficulty, and that skill profiles reveal agent-specific blind spots invisible to aggregate metrics (§5).

---

## 2. Macro Vocabulary

### 2.1 Definition

A **macro** is the smallest web interaction unit that carries a distinct, recurring intent. It occupies the level between raw UI actions (click, type, scroll) and full tasks (multi-step goals).

| Level | Example | Scope |
|-------|---------|-------|
| UI action | Click the "Submit" button | Mechanical — no standalone intent |
| **Macro** | `search_by_query` | Single intent, single verifiable outcome |
| Task | "Find the cheapest flight to Tokyo next Friday" | Chain of 3–6 macros |

Each macro is named `verb_modifier`: the **verb** captures the goal (search, filter, extract, navigate, submit, create, edit, ...) and the **modifier** captures how the target is specified (by_query, by_dropdown, by_slider, by_toggle, by_semantic, from_table, ...).

### 2.2 Vocabulary construction

The vocabulary is induced bottom-up from existing benchmarks, not designed by introspection. The pipeline has three phases, each enforcing an independence invariant:

**Phase 1 — Proposal.** Workers independently label tasks from WebArena (812 tasks), Mind2Web (2,350), WebShop (12,087), and WebVoyager (643) against a seed vocabulary of 18 verbs and 42 modifiers. Workers may propose new terms only when the seed cannot express the intent. Crucially, each worker sees only the frozen seed — never another worker's proposals — ensuring no dataset biases the vocabulary.

**Phase 2 — Deduplication.** All proposals from all workers are pooled with provenance stripped. A human reviewer clusters semantically similar proposals and decides: merge, split, accept as new, or drop. This is the only point where proposals from different datasets meet.

**Phase 3 — Relabeling.** All 15,728 tasks are re-labeled against the frozen, merged vocabulary. This ensures per-dataset coverage numbers are measured identically.

**Result:** 163 macros (18 verbs × 42 modifiers, sparse). Discovery curve analysis confirms vocabulary saturation — the marginal yield of new macros approaches zero after ~10,000 tasks.

### 2.3 Vocabulary properties

The verb axis captures intent categories: **Navigate & Search** (navigate, search), **Filter & Sort** (filter, sort), **Extract & Reason** (extract, compute, compare, verify), **Create & Edit** (create, edit, delete, post), **Social & Engage** (follow, react, share, report, save, block), **Transact** (add, checkout, pay, book, cancel, redeem), **Configure & Upload** (configure, upload, export, translate), and **Account** (authenticate, register, invite, join).

The modifier axis captures UI affordance: by_query (text input), by_dropdown (selection menu), by_slider (continuous range), by_toggle (binary switch), by_checkbox (multi-select), by_form (structured form), by_semantic (natural language matching), by_route (URL navigation), from_table (tabular data), from_free_text (open text), etc.

---

## 3. The MiniWeb Benchmark

### 3.1 Design principles

1. **Macro-first construction.** Websites are not sampled from the web — they are built to exercise assigned macros from the vocabulary. Each site's target macro set ensures the benchmark has controlled, measurable skill coverage.

2. **Real-world fidelity.** Each website is modeled after a well-known real-world counterpart (e.g., email → Gmail, CRM → Salesforce, e-commerce → Amazon). Sites use real data sources where available (arXiv papers, Enron emails, Wiktionary entries, WebShop products, PeerRead reviews) and synthesized data elsewhere.

3. **Local and reproducible.** Every site is a self-contained Flask application. No live web dependencies, no external APIs needed at evaluation time. The entire benchmark runs on a single machine.

4. **Automated verification.** Every task has a programmatic verifier that checks backend state via HTTP — not browser content — making evaluation deterministic and independent of rendering.

### 3.2 Benchmark statistics

| Property | Value |
|----------|-------|
| Websites | 78 |
| Domain categories | 15 |
| Total tasks | 4,680 (60 per site) |
| Unique macros exercised | 163 |
| Avg. macros per task | 2.8 |
| Avg. macros per site | 18 |
| Task difficulty: easy / medium / hard | 20 / 20 / 20 per site |
| Verification: automated | 100% (all tasks have programmatic verifiers) |

### 3.3 Domain coverage

| Category | Sites | Example sites |
|----------|-------|---------------|
| Shopping & transactional | 11 | e-commerce, grocery, flights-hotels, ticketing, auctions |
| Financial | 4 | banking, credit-card, brokerage, stock-crypto |
| Productivity | 14 | documents, CRM, calendar, cloud-storage, project-mgmt, code-editor |
| Communication | 5 | email, instant-messaging, team-chat, remote-calls, AI-chatbots |
| Social | 6 | forums, dating, classifieds, multimedia-posting, rating-review |
| Media & streaming | 7 | music, video, live, podcasts, books-comics, sports-esports |
| Education | 3 | course-sites, MOOCs, conference-review |
| Search & reference | 5 | search-engines, wikis, Q&A, comparison-aggregators, academic-paper-db |
| Static & informational | 5 | restaurants, business-company, personal-portfolio, project-homepages, help-center |
| Dynamic feeds | 3 | news, blogs, weather |
| Government & civic | 3 | agency-portals, tax-filing, petitions |
| Health | 2 | health-portals, health-fitness-tracking |
| Maps & navigation | 2 | map-services, transit-directions |
| Utilities | 4 | converters, dictionaries, password-managers, URL-shorteners |
| Gaming | 2 | single-player, multiplayer-online |
| Editing | 3 | documents, spreadsheets-slides, handwritten-notes |

### 3.4 Task format

Each task is a JSON object:

```json
{
    "task_id": "e-commerce_042",
    "instruction": "Search for 'wireless headphones', sort by price low-to-high, and add the cheapest one to your cart. What is the item name?",
    "difficulty": "hard",
    "macros": ["search_by_query", "sort_by_ranking", "extract_by_route", "add_by_button"],
    "verifier": "verify_042",
    "expected_answer": null
}
```

- **instruction**: Natural language task description given to the agent. No hints about macros, expected answers, or verification logic.
- **macros**: Ordered list of atomic skills the task exercises. Annotated by human workers.
- **difficulty**: Structurally defined — easy (1 macro), medium (2–3 macros), hard (4+ macros).
- **verifier**: Programmatic function that checks backend state after task completion.

### 3.5 Task annotation protocol

Tasks are crowdsourced by human annotators following a protocol:

1. Annotator receives a website URL and its target macro list.
2. LLM-generated draft task is shown as a starting point.
3. Annotator MUST attempt the task in a live browser — no rubber-stamping.
4. Annotator edits the instruction, confirms/corrects the expected answer.
5. Annotator selects verifiers from a checklist with live pass/fail indicators.
6. Annotator labels the macro chain from the macro library.
7. Each task is auto-validated (verifier must pass with reference solution) before acceptance.

Target: 60 tasks per site (20 easy, 20 medium, 20 hard), balanced across the site's target macros.

---

## 4. Construction Pipeline

Building 78 functional websites is a significant engineering effort. We develop a hybrid human-AI pipeline:

### 4.1 Pipeline stages

```
Macro assignment → Data curation → Site description → Code generation → Validation → Browser-eval loop
    (human)          (human)          (human)          (LLM-assisted)   (automated)   (automated × N)
```

**Stage 1: Macro assignment.** A human reviewer assigns target macros to each site subcategory from the macro bank, guided by the question: "Would a user of the real-world equivalent actually encounter this interaction?"

**Stage 2: Data curation.** For each site, a human contributor either provides a raw external dataset (e.g., arXiv metadata, Enron emails) or writes a description specifying what data to synthesize. Raw data is never reformatted — the site's code includes a runtime interpreter.

**Stage 3: Site description.** The contributor writes a description specifying: what the site is, which real-world site it models, how it uses the data, whether the domain is dynamic or static, and any domain-specific constraints.

**Stage 4: Code generation.** An LLM generates the full site: Flask routes with data interpreter, Jinja2 templates styled after the real-world counterpart, construction-time validation tasks, per-task verifiers, and reference solutions. Each site is a self-contained directory.

**Stage 5: Validation.** An automated pipeline runs each construction-time task in isolation: reset data → run reference solution → run verifier → reset. Target: 20/20 tasks pass.

**Stage 6: Browser-agent eval loop.** A real browser agent attempts all tasks. Failures reveal usability issues — broken navigation, unclear UI, missing affordances. The site is refined and re-validated. This loop runs N times (N=3 in practice).

### 4.2 Session-scoped data isolation

MiniWeb uses an in-memory data overlay instead of Docker containers. All reads/writes to site data files are intercepted at the Python level: writes go to a session-scoped dict (never touching disk), reads check the session dict first then fall back to pristine snapshots. This provides per-user isolation with zero infrastructure — no Docker, no databases, no container orchestration. A single `python run.py` hosts all 78 sites.

---

## 5. Experiments

We evaluate N frontier web agents on MiniWeb and analyze results along three dimensions: skill profiles, skill transferability, and difficulty prediction.

### 5.1 Experimental setup

**Agents:** GPT-4o, Claude Sonnet, Gemini Flash, [open-source model TBD].

**Protocol:** Each agent receives only the task instruction and a browser pointed at the site. The agent interacts with the rendered UI. After completion or timeout (600s), the verifier checks backend state. No hints, no expected answers, no macro labels are provided to the agent.

### 5.2 Skill profiles (macro × agent heatmap)

The primary analytical tool is the **macro × agent heatmap**: a matrix where rows are macros, columns are agents, and cells are pass rates. This reveals universal strengths, universal weaknesses, and agent-specific gaps.

### 5.3 Skill transferability

For each macro that appears on 5+ sites, compute the per-site pass rate for each agent. Measure cross-site consistency using the coefficient of variation. Low CV = transferable skill. High CV = context-dependent.

### 5.4 Difficulty prediction from macro composition

Model task pass rate as a function of its constituent macros. Simplest: P(task) = ∏ P(macro_i). More sophisticated: a learned composition model. Report R² and calibration plots.

### 5.5 Aggregate benchmark results

Standard benchmark table: per-agent pass rates broken down by difficulty level and domain category.

---

## 6. Analysis and Findings

[To be filled after experiments.]

---

## 7. Dataset Details

### 7.1 Data sources

| Dataset | Source | License | Size | Sites using it |
|---------|--------|---------|------|---------------|
| arXiv metadata | arxiv.org | CC0 | 5 GB | academic-paper-db |
| Enron emails | CMU | Public domain | 1.7 GB | email |
| Wiktionary | wiktextract | CC-BY-SA | 22 GB | dictionaries |
| WebShop products | Princeton NLP | MIT | 5.2 GB | e-commerce |
| PeerRead | Yale NLP | CC-BY | 50 MB | conference-review |
| GSMArena phones | back4app | Public | 3 MB | comparison-aggregators |
| Kubernetes docs | CNCF | CC-BY-4.0 | — | documentation-api-docs |

### 7.2 Hosting and reproducibility

MiniWeb is distributed as a single repository. `python run.py` starts a Flask server hosting all 78 websites on `localhost:8080`. No Docker, external databases, or API keys required to serve the benchmark.

### 7.3 Licensing

All MiniWeb code is released under [LICENSE]. Task annotations are released under CC-BY-4.0. External data sources retain their original licenses.

---

## 8. Related Work

**Web agent benchmarks.** WebArena (Zhou et al., 2024) pioneered self-hosted reproducible web benchmarks with 5 websites and 812 tasks. VisualWebArena (Koh et al., 2024) extends it with visual reasoning across 14 websites. WorkArena (Drouin et al., 2024) targets enterprise SaaS with 33 tasks. Mind2Web (Deng et al., 2023) provides 2,350 tasks across ~100 live websites but suffers from reproducibility issues. WebVoyager (He et al., 2024) uses live websites with 643 tasks. AssistantBench (Yoran et al., 2024) focuses on open-web QA. OSWorld (Xie et al., 2024) benchmarks desktop OS agents. **Common limitation:** all report aggregate task-level metrics with no skill decomposition.

**Skill taxonomies for agents.** GAIA (Mialon et al., 2023) defines difficulty levels by required capabilities but does not provide a formal skill vocabulary. AgentBench (Liu et al., 2023) evaluates across environments but without per-skill analysis. MiniWeb is the first to derive a formal interaction skill vocabulary and use it as an evaluation axis.

**Benchmark methodology.** HELM (Liang et al., 2023) advocates for multi-dimensional evaluation of language models. BIG-bench (Srivastava et al., 2023) demonstrated that fine-grained capability measurement reveals model strengths invisible to aggregate metrics. MiniWeb applies this philosophy to web agents.

---

## 9. Limitations

1. **Fidelity gap.** MiniWeb sites are simplified Flask applications, not production websites. They lack JavaScript-heavy interactions (SPAs, real-time updates, complex animations).
2. **Macro granularity.** The vocabulary is a design choice. Finer or coarser decomposition might yield different insights.
3. **Task distribution.** Crowdsourced tasks may not perfectly represent real user behavior.
4. **Static websites.** Domains that inherently require real-time data are simulated.

---

## 10. Conclusion

MiniWeb demonstrates that decomposing web agent evaluation along a structured skill axis — macros — produces richer, more actionable insights than aggregate pass rates. The macro × agent heatmap reveals strengths, weaknesses, and blind spots that single numbers obscure. By constructing websites bottom-up from a macro vocabulary, we achieve controlled skill coverage at scale: 78 websites, 4,680 tasks, 163 macros, fully local and reproducible.

---

## Timeline (targeting ICLR 2027, deadline ~Oct 2026)

| Period | Milestone |
|--------|-----------|
| Jun 2026 | Macro bank finalized (163 macros). 27/78 websites built and validated. |
| Jul 2026 | All 78 websites built. Browser-agent eval on all sites with 3+ agents. |
| Aug 2026 | Task crowdsourcing (4,680 tasks). Per-macro analysis complete. |
| Sep 2026 | SFT transfer experiment. Paper draft complete. |
| Oct 2026 | Internal review, polish, submit to ICLR 2027. |
