# What Is a Macro?

A **macro** is the smallest unit of web interaction that carries a distinct, recurring **intent**. It is written site-agnostically and sits right between a mechanical action and a full task.

| Level | Example | Description |
| --- | --- | --- |
| **Atomic Action** | Click "Submit" | Too small; just UI mechanics. |
| **MACRO** | Log in | The sweet spot; one clear intent. |
| **Task** | Log in, then buy an item | Too big; a chain of multiple macros. |

---

## Naming & Structure

Name every macro using the format **`verb_modifier`** (in snake_case). The website and specific data values are just fill-in-the-blank **slots**.

* **Verb:** The primary goal (e.g., navigate, extract, search).
* **Modifier:** How the target is defined or structured (e.g., `by_semantic_match`, `from_free_text`).

**The Registry Rule:**
You must build macros by pairing a verb and a modifier from the approved registries (`macros/verbs_modalities.csv` and `macros/all_macros.csv`). If a standard pair doesn't fit, explicitly propose a new verb or modifier in the CSV (`status=proposed`). **Never invent new ones silently.**

---

## The 3 Tests (Must Pass All)

A candidate is only a macro if it meets all three criteria:

1. **Single Intent:** It names exactly one goal, phrased as `verb + target + modifier`.
2. **One Terminal State:** It has a single, verifiable outcome checkable by one evaluator.
3. **Indivisible Intent:** Splitting it apart yields only bare atomic actions (clicks, keystrokes). If a split piece has its own intent and outcome, you are looking at a task.

---

## What is NOT a Macro

* **Too Small (UI Mechanics):** `locate_search_bar`, `type_query`, `click_submit`. These always happen in a fixed sequence and have no independent outcome. **Fix:** Collapse them into their parent intent (e.g., `search_by_keyword`).
* **Too Big (Tasks):** "Find the FAQ and tell me the CEO." This has two outcomes (arriving at the page, extracting the name). **Fix:** Split it into two macros.

---

## Composition Policy

Surface **every** distinct intent step. A task rarely consists of just two macros. Do not skip intermediate actions that narrow down or locate a target.

Err toward capturing more **intents**, never more UI mechanics. (See `docs/labeling_policy.md` for full reviewer rules).

**Common sequence steps to include:**

* `search` (retrieve a set)
* `filter` (narrow down)
* `sort` (order the list)
* `Maps` (open the chosen item)
* `extract` (read the info)

---

## Examples

**Task:** *"Go to the dogs Wikipedia article and tell me their average lifespan."*

> `Maps_by_semantic_match`, `extract_from_free_text`

**Task:** *"Buy the cheapest in-stock {{product}}."*

> `Maps_by_semantic_match`, `search_by_keyword`, `filter_by_attribute`, `sort_list`, `Maps_by_semantic_match`, `add_to_cart`, `place_order`