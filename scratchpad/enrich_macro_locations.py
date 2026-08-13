"""Batch-enrich macro_locations for all sites (except the 3 already piloted).

For each site: feed the LLM the current location strings + REAL sampled DB data +
the site's form-control markup, and ask it to rewrite each entry richer (location +
outcome + real options/fields + a concrete example), keeping the SAME macro keys.
Writes scratchpad/enriched_<site>.yaml per site; a separate merge step folds them in.

Run:  ~/.conda/envs/miniweb/bin/python scratchpad/enrich_macro_locations.py
"""
import os, sys, re, glob, pathlib, yaml
sys.path.insert(0, ".")
os.chdir(pathlib.Path(__file__).resolve().parent.parent)

import app  # loads .env (LLM creds)
from app.llm import call_llm
from annotation.app import _site_data_samples

DONE = {"e-commerce", "banking", "forums"}   # already piloted
LOC = yaml.safe_load(open("data/macro_locations.yaml"))
SITES = [s for s in LOC if s not in DONE and isinstance(LOC[s], dict) and LOC[s]]

CTRL_RE = re.compile(r"<(select|option|button|input|label|h[1-3])\b[^>]*>([^<]{0,60})", re.I)


def control_markup(site, budget=6000):
    """Lines of form-control markup from the site's templates (options/buttons/fields)."""
    seen, out = set(), []
    for tf in sorted(glob.glob(f"sites/{site}/templates/**/*.html", recursive=True)):
        try:
            txt = pathlib.Path(tf).read_text(errors="ignore")
        except OSError:
            continue
        for m in CTRL_RE.finditer(txt):
            frag = re.sub(r"\s+", " ", m.group(0)).strip()[:120]
            if frag not in seen:
                seen.add(frag); out.append(frag)
            if sum(len(x) for x in out) > budget:
                return "\n".join(out)
    return "\n".join(out)


SYSTEM = (
    "You enrich a benchmark site's macro-location notes so an LLM can later draft "
    "concrete tasks from them. You are given the site's CURRENT notes (a YAML map of "
    "macro -> list of short location strings), REAL data currently on the site, and "
    "the site's form-control markup. Rewrite EACH location string so it carries: the "
    "precise UI location, the OUTCOME, the CONCRETE real options/fields/values (use "
    "the actual dropdown options / field names / statuses from the markup), and a "
    "short EXAMPLE task referencing a REAL entity/value from the data. Keep it to "
    "1-2 sentences per string. CRITICAL: keep EXACTLY the same macro keys and the "
    "same NUMBER of strings under each macro. Output ONLY valid YAML: the single "
    "top-level site key, then each macro -> list of enriched strings. No code fences, "
    "no commentary.")


def enrich(site):
    block = {site: LOC[site]}
    user = yaml.safe_dump({
        "site": site,
        "current_notes": LOC[site],
        "real_site_data": _site_data_samples(site, max_collections=6, rows=4),
        "control_markup": control_markup(site),
    }, sort_keys=False)
    raw = call_llm(user, system=SYSTEM, max_tokens=4000, temperature=0.3)
    if not raw:
        return None, "LLM empty"
    raw = re.sub(r"^```[a-z]*\n?|\n?```$", "", raw.strip())
    try:
        out = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        return None, f"bad YAML: {e}"
    if not isinstance(out, dict) or site not in out or not isinstance(out[site], dict):
        return None, "wrong shape"
    orig_keys, new_keys = set(LOC[site]), set(out[site])
    if orig_keys != new_keys:
        # keep original entries for any macro the LLM dropped/renamed
        for k in orig_keys - new_keys:
            out[site][k] = LOC[site][k]
        for k in new_keys - orig_keys:
            out[site].pop(k, None)
    return out, f"{len(out[site])} macros"


def main():
    ok, fail = 0, []
    for i, site in enumerate(SITES, 1):
        res, msg = enrich(site)
        if res:
            pathlib.Path(f"scratchpad/enriched_{site}.yaml").write_text(
                yaml.safe_dump(res, sort_keys=False, allow_unicode=True, width=1000))
            ok += 1
            print(f"[{i}/{len(SITES)}] {site}: OK ({msg})", flush=True)
        else:
            fail.append((site, msg))
            print(f"[{i}/{len(SITES)}] {site}: FAIL ({msg})", flush=True)
    print(f"\nDONE: {ok}/{len(SITES)} enriched. fails: {fail}")


if __name__ == "__main__":
    main()
