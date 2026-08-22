"""Fetch + convert the LinguaBridge many-to-many translation model (one-time setup).

Downloads facebook/nllb-200-distilled-600M from Hugging Face and converts it to
an int8 CTranslate2 model at models/nllb200-600M-ct2 (~600MB on disk, ~1GB RAM
at inference, ~100-300ms/sentence on CPU). The site's translator uses it for
all 110 language directions natively (no English pivot, no API key), with the
persistent translation_cache still freezing every output for determinism.

Setup step, like scripts/fetch_brand_fonts.py — run once per machine/deploy:
    ~/.conda/envs/miniweb/bin/python scripts/fetch_translation_model.py

The model directory is gitignored; on Railway either bake this into the image
build or put models/ on the persistent volume. Without the model the site
falls back to the LLM (if keyed) and then the built-in dictionaries.
"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models" / "nllb200-600M-ct2"
HF_REPO = "facebook/nllb-200-distilled-600M"


def main():
    if (MODEL_DIR / "model.bin").exists() and (MODEL_DIR / "sentencepiece.model").exists():
        print(f"model already present at {MODEL_DIR}")
        return

    from huggingface_hub import snapshot_download
    print(f"downloading {HF_REPO} ...")
    src = snapshot_download(HF_REPO, allow_patterns=[
        "*.json", "*.model", "pytorch_model.bin", "*.safetensors", "*.txt"])
    print("converting to CTranslate2 int8 ...")
    MODEL_DIR.parent.mkdir(exist_ok=True)
    tmp = str(MODEL_DIR) + ".tmp"
    subprocess.run([
        sys.executable, "-m", "ctranslate2.converters.transformers",
        "--model", src, "--output_dir", tmp,
        "--quantization", "int8", "--force",
    ], check=True)
    # keep the sentencepiece tokenizer next to the model
    sp = pathlib.Path(src) / "sentencepiece.bpe.model"
    shutil.copy2(sp, pathlib.Path(tmp) / "sentencepiece.model")
    shutil.move(tmp, MODEL_DIR)
    size = sum(f.stat().st_size for f in MODEL_DIR.rglob("*")) / 1e6
    print(f"done: {MODEL_DIR} ({size:.0f} MB)")


if __name__ == "__main__":
    main()
