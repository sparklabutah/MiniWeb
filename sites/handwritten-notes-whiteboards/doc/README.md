# Handwritten notes / whiteboards

**Category**: Editing
**Reviewer**: Reaz
**Number of macros**: 22

## Data Source

JSON files in `data_sources/handwritten-notes-whiteboards/`:
- `notes.json` -- 20 notes with title, content, tags, notebook assignment, pinning, color
- `notebooks.json` -- 6 notebooks owned by different users
- `whiteboards.json` -- 8 whiteboards with positioned elements (text, shapes, sticky notes, drawings)
- `users.json` -- 5 users with credentials

### Data Format

**notes.json**: Array of note objects with fields: id, title, content, owner_id, created_at, updated_at, tags (array), notebook_id, is_pinned, color.

**notebooks.json**: Array of notebook objects: id, name, owner_id, color, notes_count.

**whiteboards.json**: Array of whiteboard objects: id, title, owner_id, created_at, updated_at, shared_with (array of user IDs), elements (array of positioned canvas objects with type/content/x/y/width/height/color).

**users.json**: Array of user objects: id, username, password, display_name, email, avatar.

### Sampling

All records loaded by default (num_data_points=-1). Data is small enough to load entirely.

## Real-World Model

**Notion / Miro / Apple Notes / Bear** -- note-taking and whiteboard collaboration platform. Key UI elements:
- Dashboard showing recent and pinned notes
- Notebook sidebar for organization
- Note editor with title, content, tags, color, pin toggle
- Whiteboard canvas with drag-and-drop elements (text, shapes, sticky notes, drawings)
- Search bar with keyword and semantic search
- Share/invite functionality for whiteboards
- Export in multiple formats (JSON, CSV, Markdown)
- Note type selector (text, checklist, sketch) via radio buttons
- Quick-create toggle between note and whiteboard

## Target Macros

navigate_by_route, navigate_by_pan_zoom, search_by_query, search_by_semantic, search_by_image, create_from_free_text, create_by_radio, create_by_toggle, create_by_drag, create_by_image, submit_by_query, edit_by_form, edit_by_ranking, edit_by_drag, edit_by_image, delete_from_table, upload_by_upload, save_by_toggle, export_by_dropdown, share_by_dropdown, invite_by_form, translate_by_image

## Temporal Dynamics

Not applicable -- notes and whiteboards are user-created content. No temporal simulation needed. Data is mutable state that changes via user actions.

## Domain-Specific Notes

- Semantic search: keyword-overlap scoring over note titles, content, and tags
- Image-based macros (search_by_image, create_by_image, edit_by_image, translate_by_image) are placeholder upload endpoints that accept files but do not perform real OCR/vision
- navigate_by_pan_zoom: whiteboard view endpoint accepts zoom/pan_x/pan_y query params
- create_by_drag: add element to whiteboard canvas with x,y position
- edit_by_drag: move whiteboard element to new x,y position
- edit_by_ranking: reorder notes by providing ordered list of note IDs
- save_by_toggle: pin/unpin note toggle
- share_by_dropdown: share whiteboard with user selected from dropdown
- invite_by_form: invite user to whiteboard by email address
