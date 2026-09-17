"""Shared path constants for WiFi state flags written by the API and read by the boot service.

The single definition of ``WIFI_FLAG`` and ``FORCE_PORTAL`` lives in
``wifi_setup/wifi_state.py`` (the shared configured-verdict resolver). This module simply
re-exports them so existing API importers (``main.py`` auto-start, ``helpers/buttons.py``)
keep working unchanged.

Import-path note: the API process runs with its working directory set to ``api/`` (see the
``nuggies-api.service`` unit and ``run_api.sh``), so its imports use the bare ``helpers.``
prefix and the project root is *not* on ``sys.path``. The ``wifi_setup`` package lives at
the project root, so we add the project root to ``sys.path`` before importing it. The
project root is resolved from the shared ``_PROJECT_ROOT`` already computed in
``helpers.process`` (``parents[2]`` of ``api/helpers/process.py``).
"""

import sys

from helpers.process import _PROJECT_ROOT

# Make the project-root `wifi_setup` package importable from the api-rooted sys.path.
_project_root_str = str(_PROJECT_ROOT)
if _project_root_str not in sys.path:
    sys.path.insert(0, _project_root_str)

# Re-export the single-definition constants from the shared resolver. These are the exact
# same Path objects as `wifi_setup.wifi_state.WIFI_FLAG` / `.FORCE_PORTAL`, so there is no
# duplicate literal definition.
from wifi_setup.wifi_state import FORCE_PORTAL, WIFI_FLAG  # noqa: E402

__all__ = ["WIFI_FLAG", "FORCE_PORTAL"]
