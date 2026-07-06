"""Macro difficulty categorization for sampling weights.

Categories determine how heavily each macro is sampled during annotation.
Higher-difficulty macros get more tasks to ensure adequate coverage of
skills that agents struggle with.

Target distribution at 2500 tasks:
  spatial_control:  600 tasks (~22 per macro)
  reasoning:        400 tasks (~50 per macro)
  state_change:     500 tasks (~33 per macro)
  media:            200 tasks (~29 per macro)
  text_input:       400 tasks (~8 per macro)
  simple_select:    250 tasks (~5 per macro)
  trivial:          150 tasks (~12 per macro)
"""

# Maps each macro to a difficulty category.
# Categories with higher sampling weights get more tasks.
MACRO_CATEGORIES = {
    # --- SPATIAL CONTROL: sliders, date pickers, drag, pan/zoom ---
    # Hardest for agents — precision, spatial reasoning, non-standard inputs
    "filter_by_slider": "spatial_control",
    "filter_by_date_range": "spatial_control",
    "compute_by_slider": "spatial_control",
    "configure_by_slider": "spatial_control",
    "rate_by_slider": "spatial_control",
    "verify_by_slider": "spatial_control",
    "extract_by_slider": "spatial_control",
    "extract_by_date_range": "spatial_control",
    "select_by_slider": "spatial_control",
    "select_by_date_range": "spatial_control",
    "compare_by_slider": "spatial_control",
    "compare_by_date_range": "spatial_control",
    "sort_by_slider": "spatial_control",
    "sort_by_date_range": "spatial_control",
    "book_by_date_range": "spatial_control",
    "play_by_date_range": "spatial_control",
    "play_by_slider": "spatial_control",
    "configure_by_date_range": "spatial_control",
    "create_by_drag": "spatial_control",
    "edit_by_drag": "spatial_control",
    "edit_by_date_range": "spatial_control",
    "react_by_gesture": "spatial_control",
    "navigate_by_pan_zoom": "spatial_control",
    "search_by_pan_zoom": "spatial_control",
    "search_by_date_range": "spatial_control",
    "submit_by_slider": "spatial_control",
    "submit_by_date_range": "spatial_control",
    "translate_by_slider": "spatial_control",

    # --- REASONING: extract, compute, compare, verify ---
    # Requires reading page content and producing an answer
    "extract_by_route": "reasoning",
    "extract_by_extremum": "reasoning",
    "extract_by_ranking": "reasoning",
    "extract_by_image": "reasoning",
    "compute_by_extremum": "reasoning",
    "compute_by_route": "reasoning",
    "compare_by_route": "reasoning",
    "verify_identity_by_code": "reasoning",

    # --- STATE CHANGE: create, edit, delete, submit, pay, book ---
    # Multi-field forms, data mutation, needs verification
    "submit_by_form": "state_change",
    "create_by_form": "state_change",
    "edit_by_form": "state_change",
    "delete_from_table": "state_change",
    "add_by_button": "state_change",
    "submit_by_route": "state_change",
    "submit_by_ranking": "state_change",
    "book_by_form": "state_change",
    "cancel_by_form": "state_change",
    "checkout_by_form": "state_change",
    "pay_by_form": "state_change",
    "apply_by_form": "state_change",
    "configure_by_route": "state_change",
    "create_by_timestamp": "state_change",
    "edit_by_image": "state_change",
    "edit_by_ranking": "state_change",

    # --- MEDIA: upload, playback ---
    # Interaction with media controls, file pickers
    "upload_by_upload": "media",
    "play_by_playback": "media",
    "export_by_route": "media",
    "play_by_route": "media",
    "play_by_timestamp": "media",
    "upload_by_image": "media",
    "upload_by_route": "media",

    # --- TEXT INPUT: search, type, query-based interactions ---
    # Typing into fields — easy mechanically but reasoning about WHAT to type varies
    "search_by_query": "text_input",
    "search_by_semantic": "text_input",
    "extract_by_query": "text_input",
    "extract_by_semantic": "text_input",
    "sort_by_ranking": "text_input",
    "post_from_free_text": "text_input",
    "edit_by_query": "text_input",
    "filter_by_query": "text_input",
    "filter_by_checkbox": "text_input",
    "message_from_free_text": "text_input",
    "redeem_by_code": "text_input",
    "search_by_proximity": "text_input",
    "select_by_extremum": "text_input",
    "select_by_ranking": "text_input",
    "filter_by_semantic": "text_input",
    "pay_by_query": "text_input",
    "search_by_checkbox": "text_input",
    "search_by_route": "text_input",
    "translate_by_query": "text_input",
    "compute_by_query": "text_input",
    "create_by_query": "text_input",
    "post_by_route": "text_input",
    "save_by_query": "text_input",
    "share_by_query": "text_input",
    "sign_by_signature": "text_input",
    "verify_from_free_text": "text_input",
    "apply_by_query": "text_input",
    "authenticate_by_code": "text_input",
    "compare_by_query": "text_input",
    "configure_by_query": "text_input",
    "copy_by_route": "text_input",
    "create_by_checkbox": "text_input",
    "create_by_code": "text_input",
    "extract_by_checkbox": "text_input",
    "extract_by_code": "text_input",
    "extract_from_free_text": "text_input",
    "filter_by_proximity": "text_input",
    "filter_by_route": "text_input",
    "invite_by_query": "text_input",
    "join_by_code": "text_input",
    "post_by_query": "text_input",
    "register_by_query": "text_input",
    "route_by_query": "text_input",
    "route_by_route": "text_input",
    "search_by_code": "text_input",
    "select_by_query": "text_input",
    "sign_by_query": "text_input",
    "sort_by_extremum": "text_input",
    "sort_by_proximity": "text_input",
    "upload_by_query": "text_input",

    # --- SIMPLE SELECT: dropdowns, toggles, radio, chips ---
    # Easy for agents — locate element, pick option
    "filter_by_dropdown": "simple_select",
    "extract_from_table": "simple_select",
    "save_by_toggle": "simple_select",
    "export_by_dropdown": "simple_select",
    "extract_by_dropdown": "simple_select",
    "follow_by_toggle": "simple_select",
    "select_by_dropdown": "simple_select",
    "subscribe_by_toggle": "simple_select",
    "share_by_toggle": "simple_select",
    "react_by_toggle": "simple_select",
    "configure_by_dropdown": "simple_select",
    "follow_by_dropdown": "simple_select",
    "share_by_dropdown": "simple_select",
    "compare_by_dropdown": "simple_select",
    "compute_by_dropdown": "simple_select",
    "compare_from_table": "simple_select",
    "filter_by_radio": "simple_select",
    "select_from_table": "simple_select",
    "sort_by_dropdown": "simple_select",
    "block_by_toggle": "simple_select",
    "filter_by_toggle": "simple_select",
    "compute_from_table": "simple_select",
    "configure_by_toggle": "simple_select",
    "join_by_toggle": "simple_select",
    "play_by_dropdown": "simple_select",
    "search_by_dropdown": "simple_select",
    "create_by_dropdown": "simple_select",
    "edit_by_dropdown": "simple_select",
    "verify_by_dropdown": "simple_select",
    "verify_by_toggle": "simple_select",
    "configure_by_radio": "simple_select",
    "create_from_table": "simple_select",
    "extract_by_toggle": "simple_select",
    "filter_by_chip": "simple_select",
    "select_by_radio": "simple_select",
    "add_by_dropdown": "simple_select",
    "block_by_dropdown": "simple_select",
    "configure_by_chip": "simple_select",
    "create_by_radio": "simple_select",
    "create_by_toggle": "simple_select",
    "edit_by_toggle": "simple_select",
    "pay_by_dropdown": "simple_select",
    "redeem_by_dropdown": "simple_select",
    "route_by_radio": "simple_select",
    "select_by_chip": "simple_select",
    "sort_by_toggle": "simple_select",
    "submit_by_dropdown": "simple_select",
    "translate_by_dropdown": "simple_select",

    # --- TRIVIAL: navigation, auth, social ---
    # Agents handle these easily
    "navigate_by_route": "trivial",
    "navigate_by_semantic": "trivial",
    "navigate_by_query": "trivial",
    "navigate_from_table": "trivial",
    "navigate_by_date_range": "trivial",
    "authenticate_by_form": "trivial",
    "register_by_form": "trivial",
    "report_by_form": "trivial",
    "invite_by_form": "trivial",
    "follow_by_route": "trivial",
    "join_by_route": "trivial",
    "share_by_route": "trivial",
}

# Sampling weight multiplier per category.
# Higher = more tasks sampled for that category.
CATEGORY_WEIGHTS = {
    "spatial_control": 5.0,
    "reasoning": 8.0,
    "state_change": 4.0,
    "media": 4.0,
    "text_input": 1.5,
    "simple_select": 1.0,
    "trivial": 0.5,
}


def get_macro_weight(macro_name):
    """Return sampling weight for a macro based on its difficulty category."""
    cat = MACRO_CATEGORIES.get(macro_name, "simple_select")
    return CATEGORY_WEIGHTS.get(cat, 1.0)


def get_macro_category(macro_name):
    """Return the difficulty category for a macro."""
    return MACRO_CATEGORIES.get(macro_name, "simple_select")
