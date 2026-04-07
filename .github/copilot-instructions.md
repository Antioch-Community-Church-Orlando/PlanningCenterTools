# Copilot Instructions

## Project Overview

CLI tool for automating Planning Center Online (PCO) workflows — bulk blockout creation, volunteer duplicate detection, usage analytics, and data exports. All interaction is through interactive numbered menus in the terminal.

## Running the App

```bash
uv sync              # Install dependencies
uv run python main.py  # Run the CLI
```

## Architecture

```
main.py              → Entry point: loads .env, authenticates, dispatches menu choice
pco/                 → PCO API abstraction layer
  client.py          → Wraps pypco: credential management (keyring), pagination, API helpers
  cli.py             → Interactive pickers for input files and service types
services/            → Planning Center Services features
  blockouts.py       → Bulk blockout creation from CSV + JSON config
  volunteers.py      → Duplicate detection and usage frequency reports
  templates.py       → Plan template and team member export
people/
  extract.py         → Full people dump to JSON + CSV
input/               → User-provided CSVs and blockouts.json (gitignored data)
output/              → Generated files (gitignored)
```

**Data flow:** `input/` CSV/JSON files + PCO API → domain function in `services/` or `people/` → printed results and/or `output/` files.

**Credentials** are stored in the OS keyring (macOS Keychain, etc.), never in `.env` or source. The `.env` file is reserved for non-sensitive config only.

## Key Conventions

**Interactive menu pattern** — all `pick_*` functions prompt the user with a numbered list and re-prompt recursively on invalid input:
```python
def pick_service_type(pco, choice: int | None = None) -> dict:
```

**Dict dispatch for menus** — `main.py` routes selections via `actions = {"1": lambda: ..., "2": lambda: ...}` rather than if/elif chains.

**Private vs public functions** — `_leading_underscore` for module-internal helpers (e.g., `_match_person`, `_post_blockout`, `_iterate_to_list`); plain names for exported functions.

**Path resolution** — always relative to project root via `Path(__file__).resolve().parent.parent`, not CWD-dependent.

**Pagination** — all PCO list endpoints go through `_iterate_to_list()` which unwraps `item["data"]` from `pco.iterate()`.

**Fuzzy name matching** in `blockouts.py` handles middle names: tries full name, then first+last, then first token + last token.

**Type hints** use modern `|` union syntax (Python 3.10+) throughout; all public functions are annotated.

**Output format** — most features print human-readable results to stdout with ✓/✗ emoji; data exports write both `.json` (full API response) and `.csv` (selected fields) to `output/`.

## Input File Formats

- `input/*.csv` — must have `Full Name` and `Trip` columns (see `ExampleNames.csv.example`)
- `input/blockouts.json` — maps trip names to `{ "starts_at": ..., "ends_at": ... }` ISO 8601 timestamps (see `blockouts.json.example`)

## Dependencies

| Package | Role |
|---|---|
| `pypco` | Official PCO API client with pagination support |
| `keyring` | OS-level secure credential storage |
| `python-dotenv` | Load `.env` for non-sensitive config |
