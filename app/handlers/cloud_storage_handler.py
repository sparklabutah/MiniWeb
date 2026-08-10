"""Cloud storage handler — syncs files created on other sites."""

from datetime import datetime

from app import db
from app.events import on

_TYPE_MAP = {
    "document": ("document", "application/vnd.docedit", ".doc"),
    "spreadsheet": ("spreadsheet", "application/vnd.sheetdeck", ".xlsx"),
    "presentation": ("presentation", "application/vnd.sheetdeck.slides", ".pptx"),
    "note": ("document", "text/plain", ".txt"),
    "whiteboard": ("image", "image/svg+xml", ".svg"),
    "code": ("code", "text/x-python", ".py"),
}

# Maps source_site to the URL pattern for opening files


@on("file_created")
def sync_to_cloud(user_id, filename, file_type, size_bytes=0,
                  source_site="", source_id="", **kwargs):
    type_info = _TYPE_MAP.get(file_type, ("document", "application/octet-stream", ""))

    max_id = db.execute(
        "SELECT MAX(id) FROM cloud_storage_file_transfer_files", fetch="val") or 0
    new_id = max(max_id + 1, 90001)

    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    site_label = (source_site or "apps").replace("-", " ").title()

    # Add extension to filename if not present
    ext = type_info[2]
    if ext and not filename.endswith(ext):
        display_name = filename + ext
    else:
        display_name = filename

    db.save_item("cloud-storage-file-transfer", "files", new_id, {
        "id": new_id,
        "name": display_name,
        "path": f"/MiniWeb Apps/{site_label}/{display_name}",
        "size_bytes": size_bytes or 1024,
        "type": type_info[0],
        "mime_type": type_info[1],
        "owner_id": user_id,
        "created_at": now,
        "modified_at": now,
        "shared_with": [],
        "folder_id": 0,
        "starred": 0,
        "is_trashed": 0,
        "source_site": source_site,
        "source_id": str(source_id),
    })
