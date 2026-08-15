# Forms & surveys

**Category**: Productivity
**Reviewer**: Reaz
**Number of macros**: 18

## Data Source

Pew Research Surveys

## Target Macros

navigate_by_semantic, navigate_by_route, extract_by_query, extract_by_semantic, extract_by_dropdown, extract_by_route, create_from_free_text, submit_by_query, submit_by_dropdown, submit_by_route, submit_by_ranking, submit_by_slider, edit_by_query, delete_from_table, select_by_dropdown, export_by_dropdown, upload_by_upload, share_by_dropdown

## Site Description

FormFlow is a Google Forms / SurveyMonkey-inspired form builder and survey platform. Users create forms with various field types, distribute them, collect responses, view analytics, and export data.

### Data Files
- `users.json` -- 5 users at Meridian Systems company
- `forms.json` -- 12 forms/surveys (retrospectives, feedback, prioritization, satisfaction)
- `responses.json` -- 45 responses across the forms
- `templates_forms.json` -- 6 reusable form templates (CSAT, NPS, etc.)

### Key Features
- Form builder with 8 field types: text, textarea, rating, radio, checkbox, dropdown, slider, ranking
- Response collection with required-field validation
- Results analytics with per-field statistics (averages, distributions, rankings)
- CSV and JSON export of responses
- File attachments on forms
- Form sharing via email or link
- Form templates gallery for quick creation
- Search/filter forms by status and keyword
- Semantic search across form titles, descriptions, and field labels

### Real-World Model
Modeled after Google Forms with additional features from SurveyMonkey (templates, analytics, sharing).

### No Temporal Dynamics
Forms have status (draft/active/closed) that changes via user actions. No continuous time simulation needed.
