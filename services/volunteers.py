"""Volunteer analysis tools: duplicate detection and usage frequency."""

from datetime import datetime

import pypco

from pco.client import get_plans, get_team_members, pick_service_type


def check_for_duplicates(pco: pypco.PCO):
    """Find volunteers scheduled more than once in any upcoming plan.

    Prompts the user to select a service type, then scans all future plans
    and reports any person listed multiple times within the same plan.
    """
    service_type = pick_service_type(pco)
    service_type_id = service_type["id"]
    plans = get_plans(pco, service_type_id)
    today = datetime.now()

    found_any = False
    for plan in plans:
        plan_date = datetime.strptime(plan["attributes"]["sort_date"], "%Y-%m-%dT%H:%M:%SZ")
        if plan_date < today:
            break

        team_members = get_team_members(pco, service_type_id, plan["id"])
        seen: dict[str, int] = {}
        for member in team_members:
            name = member["attributes"]["name"]
            seen[name] = seen.get(name, 0) + 1

        duplicates = {name: count for name, count in seen.items() if count > 1}
        if duplicates:
            found_any = True
            print(f"\nPlan {plan['attributes']['sort_date']}:")
            for name, count in duplicates.items():
                print(f"  ⚠  {name} appears {count} times")

    if not found_any:
        print("No duplicate volunteers found in upcoming plans.")


def check_average_volunteer_usage(pco: pypco.PCO):
    """Show how many times each volunteer served within a date range.

    Prompts for a service type and date range, then counts appearances
    across all plans in that window.
    """
    service_type = pick_service_type(pco)
    service_type_id = service_type["id"]
    plans = get_plans(pco, service_type_id)

    start_input = input("Start date (YYYY-MM-DD): ")
    end_input = input("End date (YYYY-MM-DD): ")
    start_date = datetime.strptime(start_input, "%Y-%m-%d")
    end_date = datetime.strptime(end_input, "%Y-%m-%d")

    volunteer_count: dict[str, int] = {}
    plan_count = 0

    for plan in plans:
        plan_date = datetime.strptime(plan["attributes"]["sort_date"], "%Y-%m-%dT%H:%M:%SZ")
        if plan_date < start_date or plan_date > end_date:
            continue

        plan_count += 1
        team_members = get_team_members(pco, service_type_id, plan["id"])
        for member in team_members:
            name = member["attributes"]["name"]
            volunteer_count[name] = volunteer_count.get(name, 0) + 1

    print(f"\nVolunteer usage across {plan_count} plans ({start_input} to {end_input}):")
    for name, count in sorted(volunteer_count.items(), key=lambda x: x[1], reverse=True):
        print(f"  {name}: {count} time{'s' if count != 1 else ''}")
