"""Volunteer health & burnout report.

Serve counts come from **confirmed** assignments only (status C); declines are
tracked as a separate signal — a volunteer who declines everything must not
look like a frequent server.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pypco

from pco import report
from pco.client import get_plans_between, pick_service_types
from pco.config import get_config
from pco.models import Plan, PlanPerson
from services.reports.common import fetch_plan_people, progress


def _week_key(dt: datetime) -> tuple[int, int]:
    iso = dt.isocalendar()
    return (iso.year, iso.week)


def _max_consecutive_weeks(dates: list[datetime]) -> int:
    """Longest run of consecutive ISO weeks with at least one serve."""
    if not dates:
        return 0
    weeks = sorted({_week_key(d) for d in dates})
    # Convert (year, week) to an absolute week number for adjacency checks.
    absolute = [y * 53 + w for y, w in weeks]
    best = run = 1
    for prev, cur in zip(absolute, absolute[1:]):
        run = run + 1 if cur == prev + 1 else 1
        best = max(best, run)
    return best


def build_health_records(members: list[PlanPerson], window_days: int) -> list[dict]:
    """Compute per-person health metrics from PlanPerson records."""
    cfg = get_config()
    per_person: dict[str, dict] = {}
    serve_dates: dict[str, list[datetime]] = {}
    served_team_days: dict[str, set[tuple[str, str]]] = {}

    for m in members:
        if not m.person_id:
            continue
        rec = per_person.setdefault(
            m.person_id,
            {
                "person_id": m.person_id,
                "person_name": m.person_name,
                "serves": 0,
                "requests": 0,
                "declines": 0,
                "last_served": None,
            },
        )
        rec["requests"] += 1
        if m.is_declined:
            rec["declines"] += 1
        if m.is_confirmed and m.plan_date:
            rec["serves"] += 1
            serve_dates.setdefault(m.person_id, []).append(m.plan_date)
            day = m.plan_date.date().isoformat()
            served_team_days.setdefault(m.person_id, set()).add((day, m.team_id))
            if rec["last_served"] is None or m.plan_date > rec["last_served"]:
                rec["last_served"] = m.plan_date

    months = max(window_days / 30.44, 1e-9)
    w = cfg.burnout_weights
    t = cfg.thresholds
    records = []
    for pid, rec in per_person.items():
        dates = serve_dates.get(pid, [])
        rec["serves_per_month"] = round(rec["serves"] / months, 2)
        rec["consecutive_weeks"] = _max_consecutive_weeks(dates)
        rec["decline_rate"] = round(rec["declines"] / rec["requests"], 2) if rec["requests"] else 0.0
        day_counts: dict[str, int] = {}
        for day, _team in served_team_days.get(pid, set()):
            day_counts[day] = day_counts.get(day, 0) + 1
        rec["multi_team_days"] = sum(1 for c in day_counts.values() if c > 1)

        score = (
            w.serves_per_month_weight * min(rec["serves_per_month"] / t.burnout_serves_per_month, 1.0)
            + w.consecutive_weeks_weight * min(rec["consecutive_weeks"] / t.overuse_consecutive_weeks, 1.0)
            + w.decline_rate_weight * rec["decline_rate"]
            + w.multi_team_same_day_weight * min(rec["multi_team_days"] / 3, 1.0)
        )
        rec["burnout_score"] = round(score, 3)
        records.append(rec)

    return sorted(records, key=lambda r: -r["burnout_score"])


def volunteer_health_report(pco: pypco.PCO) -> None:
    """Interactive volunteer health + burnout scan over a lookback window."""
    cfg = get_config()
    service_types = pick_service_types(pco)

    default_days = cfg.thresholds.decline_lookback_days
    raw_days = input(f"Lookback window in days [{default_days}]: ").strip()
    window_days = int(raw_days) if raw_days.isdigit() else default_days

    now = datetime.now(UTC)
    after = (now - timedelta(days=window_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    plans: list[Plan] = []
    for i, st in enumerate(service_types, 1):
        progress(i, len(service_types), "plans")
        for raw in get_plans_between(pco, st["id"], after, before):
            plans.append(Plan.from_api(raw, st["id"], st["attributes"]["name"]))

    members = fetch_plan_people(pco, plans, filter="not_archived", label="assignments")
    records = build_health_records(members, window_days)

    at_risk = [
        r
        for r in records
        if r["serves_per_month"] >= cfg.thresholds.burnout_serves_per_month
        or r["consecutive_weeks"] >= cfg.thresholds.overuse_consecutive_weeks
    ]

    print(f"\nAnalyzed {len(records)} volunteers across {len(plans)} plans.")
    if not at_risk:
        print("✓ Nobody over the burnout thresholds.")
    for r in at_risk[:20]:
        print(
            f"  ⚠  {r['person_name']}: {r['serves']} serves"
            f" ({r['serves_per_month']}/month), {r['consecutive_weeks']} consecutive weeks,"
            f" burnout score {r['burnout_score']}"
        )

    summary = [
        f"Volunteers analyzed: {len(records)}",
        f"At risk (≥ {cfg.thresholds.burnout_serves_per_month} serves/month or"
        f" ≥ {cfg.thresholds.overuse_consecutive_weeks} consecutive weeks): {len(at_risk)}",
        "",
    ] + [
        f"- {r['person_name']}: score {r['burnout_score']}, {r['serves_per_month']} serves/month"
        for r in at_risk
    ]
    out = report.write(
        "volunteer_health",
        records,
        fields=[
            "person_name",
            "serves",
            "serves_per_month",
            "consecutive_weeks",
            "requests",
            "declines",
            "decline_rate",
            "multi_team_days",
            "burnout_score",
            "last_served",
        ],
        summary_lines=summary,
        scope=", ".join(st["attributes"]["name"] for st in service_types),
        date_range=(after[:10], before[:10]),
    )
    print(f"✓ Report written to {out}/volunteer_health.*")
