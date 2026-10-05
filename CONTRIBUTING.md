# Contributing to MiniWeb

Setup and the main commands are in [README.md](README.md). The code rules, especially data
access, are in [AGENTS.md](AGENTS.md) and `CLAUDE.md`. They apply to human contributors too.

**The dataset is frozen.** The sites, the database, `data/macros.yaml`, the annotations and the
WebMix training rows are the paper's fixed artifact. Changing any of them needs the
maintainer's sign-off. Agent harness, evaluation and tooling code can change freely.

## Recording a task

1. Log in at `/annotate/login`. Accounts come from `MINIWEB_ANNOTATORS`.
2. Open `/annotate/task`. The tool samples a site and the macros to cover. The dashboard at
   `/annotate/` shows which macros have the fewest tasks.
3. Go to the page where the task starts, then click **Start Recording**. The recorded start
   page is where agents will start.
4. Do the task. Tag each macro's span of actions. If the task asks for an answer
   (`report_information`), type the answer in the field on that macro.
5. Write the instruction so that the task's values (names, amounts, dates) are stated in it,
   and **Submit**. The task is saved to
   `data/annotations/<annotator>/<site>_<hash>/`.
6. Leave **Skip 2FA** on, unless 2FA is the skill being tested.

Tag with the canonical macro names in `data/macros.yaml`, and add a reasoning operation
(`read`, `extremum`, `count`, `compute`, `compare`, `verify`, `spatial`) where the step needs
one. See the tagging conventions in [docs/macro_system.md](docs/macro_system.md).

## Building and checking a verifier

Open the task in the **Verifier Builder** (`/annotate/verify`). Pin the values the instruction
names on each macro's backend check. Then run the validation sources. A verifier is accepted
when it passes the gold recording or a fresh walk, and fails both `empty` and `answer_only`.
Use **Task Review** (`/annotate/task-review`) to re-check tasks whose tags, answer or
instruction changed. The full rules are in [docs/VERIFIER_DESIGN.md](docs/VERIFIER_DESIGN.md).

## Changing a site (with sign-off)

Each site is self-contained in `sites/<site>/`: `routes.py`, `schema.py`,
`templates/<site>/`, `site.json`, `doc/README.md`. Checklist:

- [ ] Every query goes through `app.db`, with `WHERE` + `ORDER BY` + `LIMIT` in SQL; text
      search uses `db.search()`; counts use `db.count()`.
- [ ] Every collection the code reads or writes has a base table in `schema.py`.
- [ ] New ids come from `db.next_id()`.
- [ ] Pages that show user data need a login. Logout pops only the site's own session keys.
- [ ] File inputs work with the simulated file explorer (`app/static/file-explorer.js`).
- [ ] When you add, move or remove a UI control, update its entry in
      `data/macro_locations.yaml`.
- [ ] The verifiers of the site's existing tasks still pass their gold recording or walk.
- [ ] `sites/<site>/doc/README.md` still describes the site.

## Changing macros (with sign-off)

Edit `data/macros.yaml` only. Code that derives macro descriptions reads it, so nothing else
needs a copy. Fold a retired name into the new macro's `aliases:` so that `canon()` migrates
old tags. Then run `pytest tests/test_macro_registry.py`.

## Code changes

- Run the tests before sending a change:
  `PYTHONPATH=. ~/.conda/envs/miniweb/bin/python -m pytest tests/ -q`.
- Add or update tests for new grading, datagen or webmix logic. The existing suites show the
  style.
- Generic utilities (LLM routing, geo, auth, security) go in `helpers/`. Domain code stays in
  its package.
- For a change to grading, compare verdicts on the same episodes before and after: run the
  validation sources in the Verifier Builder, or `python evaluation/macro_judge.py --results
  <study dir>` for the judge.
- Update the package `README.md` in the same change. Add an entry to
  [docs/CHANGELOG.md](docs/CHANGELOG.md) for changes users will notice.

## Removing files

Move files instead of deleting them. Put them in
`~/Documents/MiniWeb-archive/cleanup-<YYYYMMDD>/` under their repo-relative path, and note them
in that folder's `README.md`.
