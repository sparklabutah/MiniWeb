# AI Chatbots Hub (`ai-chatbots`)

A ChatGPT-style chat app with three bot personas (Assistant, Creative, Analyst),
a searchable knowledge base, an FAQ and a prompts library. Replies come from a
local, deterministic rule engine (intent matching plus retrieval over the
knowledge base and FAQ); no external LLM is ever called.

- URL: `/sites/ai-chatbots/` (simulated domain `chatbotshub.ai`)
- Data split: training site

## Pages

| Route | Page |
|---|---|
| `/` | Home with recent conversations |
| `/chat`, `/chat/<conv_id>` | Chat view: conversation sidebar, messages, title edit, share, regenerate, system prompt |
| `/prompts` | Prompts library with search and per-prompt Save |
| `/knowledge` | Knowledge base table with search and category filter |
| `/faq` | FAQ with search |
| `/settings` | Preferences (default bot, theme, font size), subscription plan, export, knowledge-base upload |
| `/login`, `/register` | Sign-in and sign-up forms |

Forms post to `/form/*`; JSON endpoints live under `/api/` (chat, conversations,
knowledge, faq, prompts, export, upload).

## Interactions and macros

- Start a chat or send a message, register an account: `create_by_form`
- Rename a conversation: `edit_by_form`
- Delete a conversation (or all of them): `delete_from_table`
- Share a conversation: `share_by_form`
- Search the knowledge base, FAQ or prompts: `search`
- Save a prompt, switch subscription plan: `toggle_relationship`
- Change default bot, theme and font size: `configure_by_form`
- Export conversations or the knowledge base: `export`
- Upload a text file to the knowledge base: `upload_file`
- Read conversations and knowledge-base entries: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `ai-chatbots`.

## Data

- Tables: `ai_chatbots_conversations`, `ai_chatbots_knowledge_base`,
  `ai_chatbots_faq`, `ai_chatbots_prompts_library`, `ai_chatbots_users`.
- Login uses `session["user_id"]`, so the global auto-login signs in user 1.
- Site settings (bot list, default bot) come from `sites/ai-chatbots/config/config.json`.
- Registering emits a `signup` event: the password manager gets a vault entry
  and WebMail gets a welcome email.
- The same message always gets the same reply (hash-seeded response bank per persona).
