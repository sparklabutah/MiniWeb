"""Macro difficulty categorization for sampling weights.

Categories determine how heavily each macro is sampled during annotation.
Higher-difficulty macros get more tasks to ensure adequate coverage of skills
that agents struggle with.

The per-macro category and the per-category weights are now defined in the
canonical registry (data/macros.yaml) and loaded via annotation/macros.py; this
module is a thin compatibility shim over that single source of truth. Edit the
registry, not this file.

Target distribution at 2500 tasks:
  spatial_control:  600 tasks (~22 per macro)
  reasoning:        400 tasks (~50 per macro)
  state_change:     500 tasks (~33 per macro)
  media:            200 tasks (~29 per macro)
  text_input:       400 tasks (~8 per macro)
  simple_select:    250 tasks (~5 per macro)
  trivial:          150 tasks (~12 per macro)
"""
from annotation import macros as _registry

# Canonical {macro: category} and {category: weight}, derived from the registry.
MACRO_CATEGORIES = _registry.macro_categories()
CATEGORY_WEIGHTS = _registry.category_weights()


def get_macro_category(macro_name):
    """Return the difficulty category for a macro (alias-resolved)."""
    return _registry.category(macro_name) or "simple_select"


def get_macro_weight(macro_name):
    """Return sampling weight for a macro based on its difficulty category."""
    return CATEGORY_WEIGHTS.get(get_macro_category(macro_name), 1.0)
