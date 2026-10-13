import math
from pathlib import Path
import pytest

from batch_audio_leveler.config import AppConfig
from batch_audio_leveler.models import NormalizationMode


def test_app_config_auto_negates_positive_lufs_and_peak():
    # If user specifies positive numbers on instantiation
    config = AppConfig(fixed_target_lufs=15.0, true_peak_ceiling_dbtp=2.0)
    assert config.fixed_target_lufs == -15.0
    assert config.true_peak_ceiling_dbtp == -2.0

    # If user assigns positive numbers later (e.g. from UI input)
    config.fixed_target_lufs = 16.0
    assert config.fixed_target_lufs == -16.0

    config.true_peak_ceiling_dbtp = 1.5
    assert config.true_peak_ceiling_dbtp == -1.5


def test_app_config_validation():
    # Valid config
    config = AppConfig(fixed_target_lufs=-16.0, true_peak_ceiling_dbtp=-2.0)
    assert config.validate() == []

    # Out of range LUFS (e.g. -80.0, or 80.0 which becomes -80.0)
    config = AppConfig(fixed_target_lufs=-80.0)
    errors = config.validate()
    assert any("Fixed target LUFS" in e for e in errors)

    # Out of range ceiling
    config = AppConfig(true_peak_ceiling_dbtp=-25.0)
    errors = config.validate()
    assert any("True peak ceiling dBTP" in e for e in errors)
