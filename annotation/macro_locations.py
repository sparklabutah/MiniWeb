"""Per-site macro -> verified UI location(s).

The data now lives in ``macro_locations.yaml`` (keyed by canonical base macro
from ``macros.yaml``). This module just loads it so existing imports keep
working:

    from annotation.macro_locations import MACRO_LOCATIONS

Path resolution mirrors the registry: set ``MINIWEB_MACRO_DIR`` to a persistent
volume (or ``MINIWEB_MACRO_LOCATIONS`` for the exact file); defaults to the
repo's ``data/`` dir and self-seeds a fresh volume. Edit the YAML, not this file.
"""
import yaml

from annotation.macros import macro_data_path

_YAML_PATH = macro_data_path("macro_locations.yaml", "MINIWEB_MACRO_LOCATIONS")

with open(_YAML_PATH) as _f:
    MACRO_LOCATIONS: dict[str, dict[str, list[str]]] = yaml.safe_load(_f) or {}
