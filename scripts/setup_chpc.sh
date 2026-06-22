#!/usr/bin/env bash
# =============================================================================
# MiniWeb — CHPC contributor setup
#
# Run once after cloning the repo:
#   bash scripts/setup_chpc.sh
#
# Creates the conda environment, symlinks shared data, and prepares .env.
# =============================================================================
set -euo pipefail

SHARED_DATA="/scratch/general/vast/u1653932/data_sources"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONDA_BIN="/scratch/general/vast/u1653932/miniforge3/condabin/conda"

echo "============================================================"
echo "  MiniWeb CHPC Setup"
echo "============================================================"
echo "  Repo:  $REPO_ROOT"
echo "  Data:  $SHARED_DATA"
echo ""

# ── 1. Check group membership ────────────────────────────────────────────────
if id -nG | grep -qw kmarino; then
    echo "[OK] You are in the 'kmarino' group."
else
    echo "[WARN] You are NOT in the 'kmarino' group."
    echo "       Ask the PI to add you, or shared data will be inaccessible."
fi

# ── 2. Check shared data access ──────────────────────────────────────────────
echo ""
echo "Checking shared data..."
ALL_OK=true
for label_path in \
    "arXiv metadata:$SHARED_DATA/arxiv/arxiv-metadata-oai-snapshot.json" \
    "WebShop products:$SHARED_DATA/webshop/items_shuffle.json" \
    "Pressbooks:$SHARED_DATA/pressbooks/pressbooks-0000.json.gz"; do
    label="${label_path%%:*}"
    fpath="${label_path#*:}"
    if [ -r "$fpath" ]; then
        size=$(du -sh "$fpath" 2>/dev/null | cut -f1)
        echo "  [OK] $label ($size)"
    else
        echo "  [MISSING] $label — $fpath"
        ALL_OK=false
    fi
done

if [ "$ALL_OK" = false ]; then
    echo ""
    echo "Some data files are missing or unreadable."
    echo "Ask u1653932 to fix permissions: chmod -R g+rX $SHARED_DATA/"
fi

# ── 3. Create arXiv symlink ──────────────────────────────────────────────────
echo ""
ARXIV_LINK="$REPO_ROOT/sites/academic-paper-db/data/291/arxiv-metadata-oai-snapshot.json"
ARXIV_TARGET="$SHARED_DATA/arxiv/arxiv-metadata-oai-snapshot.json"

if [ -L "$ARXIV_LINK" ]; then
    echo "[OK] arXiv symlink already exists."
elif [ -f "$ARXIV_LINK" ]; then
    echo "[SKIP] arXiv file exists as regular file (not symlink)."
else
    mkdir -p "$(dirname "$ARXIV_LINK")"
    ln -s "$ARXIV_TARGET" "$ARXIV_LINK"
    echo "[OK] Created arXiv symlink."
fi

# ── 4. Create conda environment ──────────────────────────────────────────────
echo ""
if $CONDA_BIN info --envs 2>/dev/null | grep -q miniweb-eval; then
    echo "[OK] Conda env 'miniweb-eval' already exists."
else
    echo "Creating conda env 'miniweb-eval' from environment.yml..."
    echo "(This may take a few minutes.)"
    $CONDA_BIN env create -f "$REPO_ROOT/environment.yml"
    echo "[OK] Conda env created."
fi

# ── 5. Create .env ───────────────────────────────────────────────────────────
echo ""
if [ -f "$REPO_ROOT/.env" ]; then
    echo "[OK] .env already exists."
else
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "[OK] Created .env from .env.example."
    echo "     Edit it to add your API keys: nano $REPO_ROOT/.env"
fi

# ── 6. Smoke test ────────────────────────────────────────────────────────────
echo ""
echo "Running smoke test..."
if $CONDA_BIN run -n miniweb-eval python -B -c \
    "from app import create_app; app = create_app(); print(f'  Flask app loaded: {len([r.rule for r in app.url_map.iter_rules()])} routes')" \
    2>&1; then
    echo "[OK] Smoke test passed."
else
    echo "[FAIL] Could not load Flask app. Check errors above."
fi

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (required for eval only)"
echo "  2. Activate the environment:"
echo "       conda activate miniweb-eval"
echo "  3. Start the server:"
echo "       python run.py"
echo "  4. Open in browser (SSH tunnel from your laptop):"
echo "       ssh -L 8080:localhost:8080 $(whoami)@<chpc-node>"
echo "       Then visit http://localhost:8080"
echo ""
