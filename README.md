# PlanningCenterTools

Python CLI tools to automate [Planning Center](https://www.planningcenteronline.com/) processes via the PCO API.

## Features

| Tool | Description |
|---|---|
| **Add blockout dates** | Bulk-add volunteer blockouts from a CSV (with dry-run preview) |
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

2. **Store API credentials in the system keyring** — on first run you will be prompted
   automatically. Or run the tool and enter your credentials from
   [api.planningcenteronline.com](https://api.planningcenteronline.com/personal_access_tokens) when asked.
   Credentials are stored securely in your OS keychain (macOS Keychain,
   Windows Credential Manager, or a Secret Service on Linux).

3. **Prepare input files** (for blockouts):
   - `input/{name}.csv` — one row per person with `Last Name`, `First Name`, `Reason`, `Start Date`, `End Date` columns.
   - See `input/ExampleBlockouts.csv.example` for the expected format.
   - Dates can be in most common formats (MM/DD/YYYY, YYYY-MM-DD, etc.).
   - Rows with non-date values like "Pending" or "TBD" are skipped with a warning.

## Usage

```bash
uv run python main.py
```

You'll be prompted to enter your PCO API credentials on first run (stored securely in the system keyring). Subsequent runs will use the saved credentials automatically.

## Project Structure

```
PlanningCenterTools/
├── main.py              # CLI entry point
├── .env.example         # Template for non-sensitive config
├── pco/                 # Shared API client & CLI helpers
│   ├── client.py        # pypco wrapper, keyring credential management
│   └── cli.py           # Interactive input/service-type pickers
├── services/            # Planning Center Services tools
│   ├── blockouts.py     # Bulk blockout date creation
│   ├── volunteers.py    # Duplicate detection & usage reports
│   └── templates.py     # Template export
├── people/              # Planning Center People tools
│   └── extract.py       # Full people export (JSON + CSV)
├── input/               # Input CSVs and blockout JSON
├── output/              # Generated reports (gitignored)
└── pyproject.toml
```

## License

MIT 
