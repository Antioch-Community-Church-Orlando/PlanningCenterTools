"""Tests for pco/config.py load_config and get_config."""
import os
from unittest.mock import patch

from pco.config import (
    AppConfig,
    BurnoutWeights,
    OrgConfig,
    ThresholdConfig,
    _reset_config_cache,
    get_config,
    load_config,
)


def test_load_config_returns_app_config():
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert isinstance(cfg.org, OrgConfig)
    assert isinstance(cfg.thresholds, ThresholdConfig)
    assert isinstance(cfg.burnout_weights, BurnoutWeights)


def test_org_timezone_default():
    cfg = load_config()
    # Without PCO_TIMEZONE env var, should use config.toml value
    assert cfg.org.timezone == "America/New_York"


def test_thresholds_values():
    cfg = load_config()
    assert cfg.thresholds.overuse_consecutive_weeks == 4
    assert cfg.thresholds.burnout_serves_per_month == 5.0
    assert cfg.thresholds.inactive_threshold_days == 120
    assert cfg.thresholds.new_volunteer_days == 60
    assert cfg.thresholds.schedule_horizon_weeks == 8
    assert cfg.thresholds.decline_rate_threshold == 0.50
    assert cfg.thresholds.pending_rate_threshold == 0.50


def test_burnout_weights_sum():
    cfg = load_config()
    bw = cfg.burnout_weights
    total = (
        bw.serves_per_month_weight
        + bw.consecutive_weeks_weight
        + bw.decline_rate_weight
        + bw.multi_team_same_day_weight
    )
    assert abs(total - 1.0) < 1e-9


def test_pco_timezone_env_override():
    # Ensure PCO_TIMEZONE env var overrides config.toml
    env = {k: v for k, v in os.environ.items() if k != "PCO_TIMEZONE"}
    env["PCO_TIMEZONE"] = "America/Los_Angeles"
    with patch.dict(os.environ, env, clear=True):
        cfg = load_config()
        assert cfg.org.timezone == "America/Los_Angeles"


def test_get_config_caches():
    _reset_config_cache()
    cfg1 = get_config()
    cfg2 = get_config()
    assert cfg1 is cfg2


def test_service_type_ids_empty_by_default():
    cfg = load_config()
    assert cfg.org.service_type_ids == []
