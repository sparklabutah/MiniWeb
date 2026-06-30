# FormFlow - Forms & Surveys Platform

## Domain
Productivity tool for creating, distributing, and analyzing forms and surveys. Inspired by Google Forms and SurveyMonkey.

## Purpose
Users create forms with various field types (text, rating, radio, checkbox, dropdown, slider, ranking, file upload), distribute them to respondents, collect responses, view analytics/statistics, and export results.

## Data Files
- `users.json` - 5 users at a company (Meridian Systems)
- `forms.json` - 12 forms/surveys covering retrospectives, feedback, prioritization, satisfaction
- `responses.json` - 45 responses across the forms
- `templates_forms.json` - 6 reusable form templates (CSAT, NPS, etc.)

## Real-World Model
Google Forms / SurveyMonkey-style form builder with dashboard, form creation, response collection, and analytics.

## Temporal Dynamics
No continuous time simulation. Forms have status (draft/active/closed) that changes via user actions.

## Key Features
- Form builder with 8 field types: text, textarea, rating, radio, checkbox, dropdown, slider, ranking
- Response collection with validation
- Results analytics with per-field statistics
- CSV/JSON export of responses
- File attachments on forms
- Form sharing via email or link
- Form templates gallery
- Search/filter forms by status, keyword
