"""Validate + merge scratchpad/enriched_<site>.yaml blocks into data/macro_locations.yaml.

For each enriched file it:
  1. loads it (must be a 1-key YAML map: {site: {macro: [strings]}}),
  2. checks the site exists in macro_locations.yaml and the macro key set is IDENTICAL
     to the current block (no added/dropped macros),
  3. surgically replaces the `^<site>:` ... block (up to the next top-level key) in the
     raw text of macro_locations.yaml, preserving all other sites byte-for-byte.

Usage:
  # dry-run validate only (no write):
  python scratchpad/merge_enriched.py --check
  # validate + merge every enriched_*.yaml, then re-validate whole file (65 sites):
  python scratchpad/merge_enriched.py
  # limit to specific sites:
  python scratchpad/merge_enriched.py site-a site-b
"""
import sys, glob, re, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOC_PATH = ROOT / "data" / "macro_locations.yaml"


def load_loc():
    return yaml.safe_load(LOC_PATH.read_text())


def enriched_files(names):
    if names:
        return [ROOT / "scratchpad" / f"enriched_{n}.yaml" for n in names]
    return sorted(pathlib.Path(p) for p in glob.glob(str(ROOT / "scratchpad" / "enriched_*.yaml")))


def validate(path, loc):
    """Return (site, block, err). block is the dict of enriched macros for the site."""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        return None, None, f"bad YAML: {e}"
    if not isinstance(data, dict) or len(data) != 1:
        return None, None, f"expected 1 top-level site key, got {list(data) if isinstance(data, dict) else type(data)}"
    site = next(iter(data))
    block = data[site]
    if site not in loc:
        return site, None, f"site '{site}' not in macro_locations.yaml"
    if not isinstance(block, dict):
        return site, None, "block is not a map"
    orig, new = set(loc[site]), set(block)
    if orig != new:
        return site, None, f"key mismatch: missing={orig-new} added={new-orig}"
    for k, v in block.items():
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            return site, None, f"macro '{k}' is not a list[str]"
    return site, block, None


def splice(raw, site, block):
    """Replace the `^site:` ... block in raw text with a freshly-dumped block."""
    lines = raw.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if re.match(rf"^{re.escape(site)}:\s*$", ln):
            start = i
            break
    if start is None:
        raise ValueError(f"could not locate '^{site}:' in macro_locations.yaml")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j] and not lines[j][0].isspace() and not lines[j].startswith("#"):
            end = j
            break
    dumped = yaml.safe_dump({site: block}, sort_keys=False, allow_unicode=True, width=1000).rstrip("\n")
    return "\n".join(lines[:start] + dumped.split("\n") + lines[end:])


def main():
    argv = [a for a in sys.argv[1:] if a != "--check"]
    check_only = "--check" in sys.argv
    loc = load_loc()
    files = enriched_files(argv)
    if not files:
        print("no enriched_*.yaml files found")
        return
    valid, errs = [], []
    for f in files:
        if not f.exists():
            errs.append((f.name, "missing")); continue
        site, block, err = validate(f, loc)
        if err:
            errs.append((f.name, err))
        else:
            valid.append((site, block))
            print(f"OK   {site:35s} ({len(block)} macros)")
    for name, err in errs:
        print(f"FAIL {name}: {err}")
    if check_only:
        print(f"\n[check] {len(valid)} valid, {len(errs)} failed. No write.")
        return
    if errs:
        print(f"\nAborting merge: {len(errs)} file(s) failed validation. Fix them first.")
        sys.exit(1)
    raw = LOC_PATH.read_text()
    for site, block in valid:
        raw = splice(raw, site, block)
    # full re-validate before writing
    reparsed = yaml.safe_load(raw)
    assert len(reparsed) == 65, f"expected 65 sites after merge, got {len(reparsed)}"
    for site, block in valid:
        assert set(reparsed[site]) == set(block), f"{site} key mismatch after splice"
    LOC_PATH.write_text(raw)
    print(f"\nMERGED {len(valid)} site(s). macro_locations.yaml now {len(reparsed)} sites, YAML valid.")


if __name__ == "__main__":
    main()
