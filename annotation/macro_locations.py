"""Per-site macro -> verified UI location(s).

The data now lives in ``data/macro_locations.yaml`` (keyed by canonical base
macro from ``data/macros.yaml``). This module just loads it so existing
imports keep working:

    from annotation.macro_locations import MACRO_LOCATIONS

Edit the YAML, not this file.
"""
import pathlib

import yaml

_YAML_PATH = pathlib.Path(__file__).resolve().parent.parent / "data" / "macro_locations.yaml"

MACRO_LOCATIONS: dict[str, dict[str, list[str]]] = yaml.safe_load(_YAML_PATH.read_text()) or {}
