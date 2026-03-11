# PlanningCenterTools

Python CLI tools to automate [Planning Center](https://www.planningcenteronline.com/) processes via the PCO API.

## Features

| Tool | Description |
|---|---|
| **Add blockout dates** | Bulk-add volunteer blockouts from a CSV + JSON config |
| **Duplicate volunteer check** | Scan upcoming plans for people scheduled more than once |
| **Volunteer usage report** | Count how often each volunteer served in a date range |
| **Export plan templates** | Export templates and their team members to JSON/CSV |
| **Extract all people** | Dump every person from People to JSON + CSV |

## Setup

1. **Install dependencies** (requires Python ≥ 3.10):
   ```bash
   # with uv (recommended)
   uv sync

   # or with pip
   pip install .
   ```

2. **Create an API context** — copy the example and fill in your credentials from
   [developer.planning.center](https://developer.planning.center/):
   ```bash
   cp context/context.cxt.example context/myorg.cxt
   # edit context/myorg.cxt with your application_id and secret
   ```

3. **Prepare input files** (for blockouts):
   - `input/names.csv` — one row per person with `Full Name` and `Trip` columns
   - `input/blockouts.json` — maps trip names to `starts_at`, `ends_at`, and `reason`

## Usage

```bash
uv run python main.py
```

You'll be prompted to choose a context, then pick an action from the menu.

## Project Structure

```
PlanningCenterTools/
├── main.py              # CLI entry point
├── pco/                 # Shared API client & CLI helpers
│   ├── client.py        # pypco wrapper, pagination, service-type helpers
│   └── cli.py           # Interactive context/input pickers
├── services/            # Planning Center Services tools
│   ├── blockouts.py     # Bulk blockout date creation
│   ├── volunteers.py    # Duplicate detection & usage reports
│   └── templates.py     # Template export
├── people/              # Planning Center People tools
│   └── extract.py       # Full people export (JSON + CSV)
├── context/             # API credential files (.cxt)
├── input/               # Input CSVs and blockout JSON
├── output/              # Generated reports (gitignored)
└── pyproject.toml
```

## License

MIT 
