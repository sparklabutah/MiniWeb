# Contributing to MiniWeb

## Annotation Workflow

1. Go to `/annotate/` and log in
2. The sampler picks a site and macros weighted by difficulty and coverage
3. Navigate to the target page in the iframe, then click **Start Recording**
4. Perform the task, tag action ranges to macros
5. Fill in expected outcome and/or QA answer
6. Submit — task saved to `data/annotations/`

### Annotation Guidelines

- **Start on the target page** — navigate there before recording. The starting URL is captured automatically.
- **Don't tag navigation** — `navigate_by_route` is not a task macro. The agent starts on the right page.
- **QA macros** (extract, compute, compare) — use the inline answer field on the macro node instead of tagging scroll actions.
- **Expected outcome** — describe what should be verifiable (admin API checks, state changes, visible results).
- **Ambiguous instructions** — write a shorter, less explicit version in the verify dashboard for harder evaluation.
- **Skip 2FA** — keep the "Skip 2FA" toggle checked unless testing 2FA specifically.

### Macro Difficulty Priorities

Annotate more tasks for harder macros:

| Priority | Category | Examples |
|----------|----------|---------|
| High | Spatial control | Sliders, date pickers, drag-and-drop |
| High | Reasoning | Extract extremum, compute values, compare |
| Medium | State change | Create/edit/delete via forms |
| Medium | Media | File upload, playback controls |
| Low | Simple select | Dropdowns, toggles, checkboxes |
| Low | Trivial | Navigation, login |

## Adding/Fixing Sites

Each site is self-contained in `sites/<id>/`:

```
sites/my-site/
├── site.json          # {"id": "my-site", "name": "My Site", ...}
├── schema.py          # Table definitions
├── routes.py          # Flask blueprint
└── templates/my-site/ # HTML templates
```

### Checklist for site changes

- [ ] All queries use `db.query()` or `db.execute()` with WHERE/LIMIT
- [ ] Login gate on pages that show user-specific data
- [ ] Consistent nav across all templates within the site
- [ ] No export buttons on social/messaging sites
- [ ] File upload inputs work with the simulated file picker
- [ ] Update `annotation/macro_locations.py` if adding/removing UI elements

## Running Evaluation

```bash
# Against annotated tasks
python evaluation/run_annotated.py --model claude-cli --timeout 300

# With ambiguous instructions
python evaluation/run_annotated.py --model claude-cli --ambiguous

# Specific task
python evaluation/run_annotated.py --model claude-cli --task-id crm_bf9346
```
