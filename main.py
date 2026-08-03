"""PlanningCenterTools — CLI entry point.

Run with:  uv run python main.py   (or the `pct` script)
"""

from dotenv import load_dotenv
from pypco.exceptions import PCORequestException

from checkins.first_timers import first_time_visitors
from checkins.lapsed import lapsed_attenders
from checkins.trends import attendance_trends
from pco.client import create_client
from people.background_checks import background_check_report
from people.bulk_fields import bulk_update_fields
from people.duplicates import find_duplicate_people
from people.extract import extract_people
from people.forms_export import export_form_submissions
from people.workflows import bulk_enroll_workflow, overdue_cards_report
from reconcile_names import reconcile
from services.blockouts import add_blockouts
from services.reports.blockout_conflicts import scan_blockout_conflicts
from services.reports.coverage import coverage_report
from services.reports.cross_duplicates import scan_cross_duplicates
from services.reports.decline_detector import scan_decline_rates
from services.reports.notifications import notification_audit
from services.reports.roster import onboarding_report, roster_drift_report
from services.reports.volunteer_health import volunteer_health_report
from services.templates import export_templates
from services.volunteers import check_average_volunteer_usage, check_for_duplicates
from services.write.auto_blockout import auto_blockout_from_declines
from services.write.bulk_schedule import bulk_schedule
from services.write.roster_sync import roster_sync
from services.write.template_copy import template_copy

MENU = """
Planning Center Tools
=====================
── Scheduling ──
 1. Add blockout dates from CSV
 2. Duplicate volunteers within a plan
 3. Double-booked across services (same day)
 4. Blockout vs schedule conflicts
 5. Decline / no-response report
 6. Scheduling-notification audit

── Volunteer Analytics ──
 7. Volunteer health & burnout report
 8. Average volunteer usage
 9. Open positions / coverage report
10. Team roster drift report
11. New-volunteer onboarding report

── People ──
12. Find duplicate people profiles
13. Background-check compliance report
14. Overdue workflow cards report
15. Bulk-enroll people into a workflow
16. Bulk update custom fields from CSV
17. Export form submissions

── Check-Ins ──
18. Attendance trends
19. First-time visitors
20. Lapsed attender follow-up list

── Bulk Writes (dry-run + confirm) ──
21. Bulk schedule volunteers from CSV
22. Sync a team roster from CSV
23. Copy template people into plans
24. Auto-blockout repeated decliners

── Data ──
25. Export plan templates
26. Extract all people
27. Reconcile names in an input file

 0. Exit
"""


def _run(action) -> None:
    """Run a menu action with friendly error reporting."""
    try:
        action()
    except KeyboardInterrupt:
        print("\nCancelled.")
    except PCORequestException as e:
        status = getattr(e, "status_code", None)
        if status in (401, 403):
            print(
                f"✗ Planning Center rejected the request ({status}).\n"
                "  Check that your Personal Access Token is valid and that your\n"
                "  PCO account has access to this product (Services/People/Check-Ins)."
            )
        elif status == 404:
            print(
                "✗ Planning Center returned 404 — the resource wasn't found.\n"
                "  The item may have been deleted, or your plan may not include this feature."
            )
        else:
            print(f"✗ Planning Center API error: {e}")


def main():
    load_dotenv()
    pco = None

    while True:
        print(MENU)
        try:
            choice = input("Enter your choice: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            return
        if choice in ("0", "q", "exit", ""):
            return

        if pco is None:
            pco = create_client()

        actions = {
            "1": lambda: add_blockouts(pco),
            "2": lambda: check_for_duplicates(pco),
            "3": lambda: scan_cross_duplicates(pco),
            "4": lambda: scan_blockout_conflicts(pco),
            "5": lambda: scan_decline_rates(pco),
            "6": lambda: notification_audit(pco),
            "7": lambda: volunteer_health_report(pco),
            "8": lambda: check_average_volunteer_usage(pco),
            "9": lambda: coverage_report(pco),
            "10": lambda: roster_drift_report(pco),
            "11": lambda: onboarding_report(pco),
            "12": lambda: find_duplicate_people(pco),
            "13": lambda: background_check_report(pco),
            "14": lambda: overdue_cards_report(pco),
            "15": lambda: bulk_enroll_workflow(pco),
            "16": lambda: bulk_update_fields(pco),
            "17": lambda: export_form_submissions(pco),
            "18": lambda: attendance_trends(pco),
            "19": lambda: first_time_visitors(pco),
            "20": lambda: lapsed_attenders(pco),
            "21": lambda: bulk_schedule(pco),
            "22": lambda: roster_sync(pco),
            "23": lambda: template_copy(pco),
            "24": lambda: auto_blockout_from_declines(pco),
            "25": lambda: export_templates(pco),
            "26": lambda: extract_people(pco),
            "27": reconcile,
        }

        action = actions.get(choice)
        if action:
            _run(action)
            input("\nPress Enter to return to the menu…")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
