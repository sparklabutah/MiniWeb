#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_DIR="$PROJECT_ROOT/sites/_template"
SITES_DIR="$PROJECT_ROOT/sites"

usage() {
    echo "Usage: $0 <site-id> [\"Site Name\"] [\"Description\"]"
    echo
    echo "Example:"
    echo "  $0 todo-app \"Todo App\" \"A simple to-do list application\""
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

SITE_ID="$1"
SITE_NAME="${2:-$SITE_ID}"
SITE_DESC="${3:-A new MiniWeb site}"
SITE_DIR="$SITES_DIR/$SITE_ID"

if [ -d "$SITE_DIR" ]; then
    echo "Error: Site directory already exists: $SITE_DIR"
    exit 1
fi

echo "Creating site: $SITE_ID"

cp -r "$TEMPLATE_DIR" "$SITE_DIR"

# Rename template subdirectory in templates/
mv "$SITE_DIR/templates/_template" "$SITE_DIR/templates/$SITE_ID"

# Update site.json
cat > "$SITE_DIR/site.json" <<EOF
{
    "id": "$SITE_ID",
    "name": "$SITE_NAME",
    "description": "$SITE_DESC",
    "tags": ["example"]
}
EOF

# Update blueprint name and template references in routes.py
sed -i.bak "s/_template/$SITE_ID/g" "$SITE_DIR/routes.py"
rm -f "$SITE_DIR/routes.py.bak"

# Create __init__.py for the module
touch "$SITE_DIR/__init__.py"

echo
echo "Site created at: $SITE_DIR"
echo
echo "Next steps:"
echo "  1. Edit $SITE_DIR/site.json to update tags"
echo "  2. Build your pages in $SITE_DIR/templates/$SITE_ID/"
echo "  3. Add data files to $SITE_DIR/data/"
echo "  4. Edit $SITE_DIR/routes.py to add your routes"
echo "  5. Restart: python run.py"