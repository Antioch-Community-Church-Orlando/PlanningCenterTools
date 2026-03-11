"""Interactive CLI helpers for selecting contexts, input files, and service types."""

import csv
import json
from glob import glob
from pathlib import Path

# Resolve paths relative to the project root (parent of pco/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONTEXT_DIR = _PROJECT_ROOT / "context"
_INPUT_DIR = _PROJECT_ROOT / "input"


def grab_all_contexts() -> dict:
    """Load all .cxt context files from the context/ directory.

    Returns:
        A dict mapping filename stems to their parsed JSON contents.

    Raises:
        SystemExit: If no context files are found.
    """
    contexts = {}
    for path in sorted(_CONTEXT_DIR.glob("*.cxt")):
        with open(path) as f:
            contexts[path.stem] = json.load(f)

    if not contexts:
        print(
            "No contexts found. Create a {name}.cxt file in the context/ directory.\n"
            "Use the values from https://developer.planning.center/ — see context.cxt.example."
        )
        raise SystemExit(1)

    return contexts


def pick_context(choice: int | None = None) -> dict:
    """Interactively prompt the user to select an API context.

    Args:
        choice: Optional pre-selected 1-based index.

    Returns:
        The parsed context dict for the selected .cxt file.
    """
    contexts = grab_all_contexts()
    keys = list(contexts.keys())

    print("Choose a context:")
    for i, name in enumerate(keys, 1):
        print(f"  {i}. {name}")

    if choice is None:
        choice = input("Enter the number of your choice: ")

    try:
        return contexts[keys[int(choice) - 1]]
    except (IndexError, ValueError):
        print("Invalid choice. Please enter a number from the list.")
        return pick_context()


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
