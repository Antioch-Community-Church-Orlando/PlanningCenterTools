"""Application configuration loader from config.toml."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.toml"
_config_cache: AppConfig | None = None


@dataclass
class OrgConfig:
    timezone: str
    service_type_ids: list[str]


@dataclass
class ThresholdConfig:
    overuse_consecutive_weeks: int
    burnout_serves_per_month: float
    inactive_threshold_days: int
    new_volunteer_days: int
    schedule_horizon_weeks: int
    decline_rate_threshold: float
    pending_rate_threshold: float
    decline_lookback_days: int
    repeated_decline_count: int


@dataclass
class BurnoutWeights:
    serves_per_month_weight: float
    consecutive_weeks_weight: float
    decline_rate_weight: float
    multi_team_same_day_weight: float


@dataclass
class AppConfig:
    org: OrgConfig
    thresholds: ThresholdConfig
    burnout_weights: BurnoutWeights


def load_config() -> AppConfig:
    """Load and parse config.toml, applying env var overrides. Not cached."""
    with open(_CONFIG_PATH, "rb") as f:
        raw = tomllib.load(f)

    org_raw = raw.get("org", {})
    tz = os.environ.get("PCO_TIMEZONE", "").strip() or org_raw.get("timezone", "America/New_York")
    org = OrgConfig(
        timezone=tz,
        service_type_ids=[str(x) for x in org_raw.get("service_type_ids", [])],
    )

    t = raw.get("thresholds", {})
    thresholds = ThresholdConfig(
        overuse_consecutive_weeks=int(t.get("overuse_consecutive_weeks", 4)),
        burnout_serves_per_month=float(t.get("burnout_serves_per_month", 5.0)),
        inactive_threshold_days=int(t.get("inactive_threshold_days", 120)),
        new_volunteer_days=int(t.get("new_volunteer_days", 60)),
        schedule_horizon_weeks=int(t.get("schedule_horizon_weeks", 8)),
        decline_rate_threshold=float(t.get("decline_rate_threshold", 0.50)),
        pending_rate_threshold=float(t.get("pending_rate_threshold", 0.50)),
        decline_lookback_days=int(t.get("decline_lookback_days", 180)),
        repeated_decline_count=int(t.get("repeated_decline_count", 3)),
    )

    bw_raw = raw.get("burnout_weights", {})
    burnout_weights = BurnoutWeights(
        serves_per_month_weight=float(bw_raw.get("serves_per_month_weight", 0.40)),
        consecutive_weeks_weight=float(bw_raw.get("consecutive_weeks_weight", 0.30)),
        decline_rate_weight=float(bw_raw.get("decline_rate_weight", 0.20)),
        multi_team_same_day_weight=float(bw_raw.get("multi_team_same_day_weight", 0.10)),
    )

    return AppConfig(org=org, thresholds=thresholds, burnout_weights=burnout_weights)


def get_config() -> AppConfig:
    """Return the cached AppConfig, loading from disk on first call."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def _reset_config_cache() -> None:
    """Reset the config cache (for testing only)."""
    global _config_cache
    _config_cache = None
