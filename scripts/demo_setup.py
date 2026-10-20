"""Prepare the public demo (MINIWEB_DEMO=1, src/miniweb/app/demo.py) from the Hugging Face release. The Space runs it on
every start, before the server (deploy/space/start.sh); everything goes under one folder, data/demo/ by default.

    python scripts/demo_setup.py                              # downloads from the Hub
    python scripts/demo_setup.py --no-media                   # without the 8 GB of site images
    python scripts/demo_setup.py --src data/release/miniweb-v1-hf   # from a local copy of the release

Each step is skipped when its output exists:
1. the site database, static images and media (scripts/restore_site_db.py): miniweb.db, static/, media/
2. the human tasks with their recordings (scripts/fetch_tasks.py): annotations/, which the annotation tool shows
3. translation_replay.json: each translation the recordings requested, with the translation the site returned, so
   the demo's translation site answers those requests exactly as recorded
4. the session tables, so the server starts on a ready database
Then the task folders are made read-only. Serve with the variables this prints (start.sh sets them).
"""
import argparse, glob, json, os, stat, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRANSLATE = "/sites/translation/api/translate"


def run(*args):
    print("+", " ".join(args), flush=True)
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)


def recorded_translations(annotations):
    """{(source, target, text): translation} from the tasks' server logs and verification walks."""
    out, conflicts = {}, 0

    def walk(o):
        nonlocal conflicts
        if isinstance(o, dict):
            body, resp = o.get("body"), o.get("response")
            if (o.get("path") == TRANSLATE and isinstance(body, dict) and isinstance(resp, dict)
                    and body.get("text") and resp.get("translated_text")):
                key = (body.get("source", "").strip(), body.get("target", "").strip(), body["text"].strip())
                if out.setdefault(key, resp["translated_text"]) != resp["translated_text"]:
                    conflicts += 1                  # two recordings disagree: the first one read stays
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for f in sorted(glob.glob(os.path.join(annotations, "*", "*", "server_log.json"))
                    + glob.glob(os.path.join(annotations, "*", "*", "verification_walk.json"))):
        with open(f) as fh:
            walk(json.load(fh))
    if conflicts:
        print(f"warning: {conflicts} recorded translations disagree with an earlier recording of the same text")
    return out


def read_only(folder):
    for d, _, files in os.walk(folder):
        for f in files:
            os.chmod(os.path.join(d, f), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        os.chmod(d, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="a local copy of the release (default: download from the Hub)")
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "demo"))
    ap.add_argument("--no-media", action="store_true")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    paths = {"MINIWEB_DB": os.path.join(out, "miniweb.db"), "MINIWEB_DATA_STATIC": os.path.join(out, "static"),
             "MINIWEB_MEDIA_DIR": os.path.join(out, "media"), "MINIWEB_ANNOTATIONS_DIR": os.path.join(out, "annotations"),
             "MINIWEB_TRANSLATION_REPLAY": os.path.join(out, "translation_replay.json")}
    os.makedirs(out, exist_ok=True)

    if not os.path.exists(paths["MINIWEB_DB"]):
        run("scripts/restore_site_db.py", "--db", paths["MINIWEB_DB"], "--static", paths["MINIWEB_DATA_STATIC"],
            "--media", paths["MINIWEB_MEDIA_DIR"], *(["--src", os.path.join(a.src, "site_db")] if a.src else []),
            *(["--no-media"] if a.no_media else []))
    if not os.path.isdir(paths["MINIWEB_ANNOTATIONS_DIR"]):
        run("scripts/fetch_tasks.py", "--out", paths["MINIWEB_ANNOTATIONS_DIR"], "--valset", os.devnull,
            *(["--src", a.src] if a.src else []))
    if not os.path.exists(paths["MINIWEB_TRANSLATION_REPLAY"]):
        rows = [{"source": s, "target": t, "text": x, "translated": y}
                for (s, t, x), y in sorted(recorded_translations(paths["MINIWEB_ANNOTATIONS_DIR"]).items())]
        with open(paths["MINIWEB_TRANSLATION_REPLAY"], "w") as fh:
            json.dump(rows, fh, indent=1, ensure_ascii=False)
        print(f"{len(rows)} recorded translations -> {paths['MINIWEB_TRANSLATION_REPLAY']}")

    os.environ["MINIWEB_DB"] = paths["MINIWEB_DB"]
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from miniweb.app import db
    db.init_db()
    db.close()
    read_only(paths["MINIWEB_ANNOTATIONS_DIR"])

    print("serve with:\n" + "\n".join(f"  {k}={v}" for k, v in paths.items()) + "\n  MINIWEB_DEMO=1")


if __name__ == "__main__":
    main()
