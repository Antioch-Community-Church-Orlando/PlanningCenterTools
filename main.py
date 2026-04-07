"""PlanningCenterTools — CLI entry point.

Run with:  python -m main
"""

from dotenv import load_dotenv

from pco.client import create_client
from services.blockouts import add_blockouts
from services.volunteers import check_for_duplicates, check_average_volunteer_usage
from services.templates import export_templates
from people.extract import extract_people

MENU = """
Planning Center Tools
=====================
1. Add blockout dates
2. Check for duplicate volunteers
3. Check average volunteer usage
4. Export plan templates
5. Extract all people
"""


def main():
    load_dotenv()
    print(MENU)
    choice = input("Enter your choice: ").strip()

    pco = create_client()

    actions = {
        "1": lambda: add_blockouts(pco),
        "2": lambda: check_for_duplicates(pco),
        "3": lambda: check_average_volunteer_usage(pco),
        "4": lambda: export_templates(pco),
        "5": lambda: extract_people(pco),
    }

    action = actions.get(choice)
    if action:
        action()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main()
