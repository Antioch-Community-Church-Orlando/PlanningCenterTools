"""Interactive CLI helpers for selecting input files and service types."""

import csv
import json
from pathlib import Path

# Resolve paths relative to the project root (parent of pco/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_INPUT_DIR = _PROJECT_ROOT / "input"

def grab_all_inputs() -> dict:
    """Load all .csv input files from the input/ directory.

    Returns:
        A dict mapping filename stems to lists of row dicts.

    Raises:
        SystemExit: If no CSV files are found.
    """
    files = {}
    for path in sorted(_INPUT_DIR.glob("*.csv")):
        with open(path, newline="") as f:
            files[path.stem] = list(csv.DictReader(f))

    if not files:
        print(
            "No input files found. Create a {name}.csv file in the input/ directory.\n"
            "See input/ExampleNames.csv.example for the expected format."
        )
        raise SystemExit(1)

    return files


def pick_input(choice: int | None = None) -> list[dict]:
    """Interactively prompt the user to select an input CSV file.

    Args:
        choice: Optional pre-selected 1-based index.

    Returns:
        A list of row dicts from the selected CSV.
    """
    inputs = grab_all_inputs()
    keys = list(inputs.keys())

    print("Choose an input file:")
    for i, name in enumerate(keys, 1):
        print(f"  {i}. {name}")

    if choice is None:
        choice = input("Enter the number of your choice: ")

    try:
        return inputs[keys[int(choice) - 1]]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return pick_input()


def get_blockout_info() -> dict:
    """Load blockout configuration from input/blockouts.json.

    Returns:
        A dict mapping trip names to blockout date ranges.
    """
    path = _INPUT_DIR / "blockouts.json"
    with open(path) as f:
        return json.load(f)
