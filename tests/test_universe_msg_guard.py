"""P13-A #4: load_universe's not-found error must guide the user."""
from __future__ import annotations

import pytest

from niveshdristi.config_loader import ConfigurationError, load_universe


class TestUniverseErrorMessage:
    def test_missing_universe_error_names_fix(self, tmp_path):
        with pytest.raises(ConfigurationError, match="Available universes"):
            load_universe("nope50", universes_dir=tmp_path)
