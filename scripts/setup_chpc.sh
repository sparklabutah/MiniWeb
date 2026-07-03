#!/usr/bin/env bash
# =============================================================================
# MiniWeb — CHPC contributor setup
#
# Run once after cloning the repo:
#   bash scripts/setup_chpc.sh
#
# Creates the conda environment, checks shared data, and prepares .env.
# =============================================================================
set -euo pipefail

SHARED_DATA="/scratch/general/vast/u1653932/data_sources"
SHARED_DB="$SHARED_DATA/miniweb.db"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Use module system for conda (works for all CHPC users)
if ! command -v conda &>/dev/null; then
    module load miniforge3 2>/dev/null || true
fi
CONDA_BIN="$(command -v conda 2>/dev/null || echo "")"
if [ -z "$CONDA_BIN" ]; then
    echo "[ERROR] conda not found. Run: module load miniforge3"
    exit 1
fi

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

# ── 2. Symlink shared database ────────────────────────────────────────────────
echo ""
echo "Setting up database symlink..."
if [ -f "$SHARED_DB" ] && [ -r "$SHARED_DB" ]; then
    size=$(du -sh "$SHARED_DB" 2>/dev/null | cut -f1)
    echo "  [OK] Shared DB exists ($size)"
    if [ -L "$REPO_ROOT/miniweb.db" ]; then
        echo "  [OK] Symlink already exists: $(readlink "$REPO_ROOT/miniweb.db")"
    elif [ -f "$REPO_ROOT/miniweb.db" ]; then
        echo "  [SKIP] $REPO_ROOT/miniweb.db is a regular file (not a symlink)."
        echo "         Remove it and re-run if you want to use the shared DB."
    else
        ln -s "$SHARED_DB" "$REPO_ROOT/miniweb.db"
        echo "  [OK] Created symlink: miniweb.db -> $SHARED_DB"
    fi
else
    echo "  [WARN] Shared DB not found or not readable: $SHARED_DB"
    echo "         Ask u1653932 to fix permissions: chmod o+r $SHARED_DB"
fi

# ── 3. Check shared data access ──────────────────────────────────────────────
echo ""
echo "Checking shared data sources..."
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
    echo "Ask u1653932 to fix permissions: chmod -R o+rX $SHARED_DATA/"
fi

# ── 4. Create conda environment ──────────────────────────────────────────────
echo ""
if $CONDA_BIN info --envs 2>/dev/null | grep -q miniweb-eval; then
    echo "[OK] Conda env 'miniweb-eval' already exists."
else
    echo "Creating conda env 'miniweb-eval' (Python 3.11 + requirements.txt)..."
    echo "(This may take a few minutes.)"
    $CONDA_BIN create -n miniweb-eval python=3.11 -y
    $CONDA_BIN run -n miniweb-eval pip install -r "$REPO_ROOT/requirements.txt"
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
