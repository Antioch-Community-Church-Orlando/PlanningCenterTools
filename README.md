# PlanningCenterTools

Python CLI tools to automate [Planning Center](https://www.planningcenteronline.com/) processes via the PCO API — the things the web UI can't do in bulk.

Everything runs from a simple numbered menu. Reports are written to `output/` as JSON + CSV + Markdown. **Every operation that changes data shows a dry-run preview and asks for confirmation first.**

## Features

### Scheduling (Services)
| Tool | Description |
|---|---|
| **Add blockout dates** | Bulk-add volunteer blockouts from a CSV (dry-run preview, duplicate detection) |
| **Duplicate volunteer check** | Scan upcoming plans for people scheduled more than once in a plan |
| **Cross-service double-booking scan** | Find people confirmed on two plans on the same day |
| **Blockout conflict scan** | Find people scheduled during their own blockouts |
| **Decline / no-response report** | Who declines or ignores scheduling requests, with reasons |
| **Notification audit** | Pending volunteers whose scheduling notification was never sent or read |

### Volunteer Analytics (Services)
| Tool | Description |
|---|---|
| **Volunteer health & burnout** | Serves/month, consecutive-week streaks, weighted burnout scores (confirmed serves only) |
| **Volunteer usage report** | Count how often each volunteer served in a date range |
| **Coverage report** | Open (needed) positions across upcoming plans |
| **Roster drift report** | Roster members who never serve; people serving off-roster; scheduling preferences |
| **Onboarding report** | New volunteers by first confirmed serve date |

### People
| Tool | Description |
|---|---|
| **Duplicate people finder** | Fuzzy-match the whole database for probable duplicate profiles (merge is UI-only) |
| **Background-check compliance** | Volunteers serving without a passed background check |
| **Workflow tools** | Cross-workflow overdue-card report; bulk-enroll people into a workflow from CSV |
| **Bulk custom fields** | Set custom field values for many people from a CSV |
| **Forms export** | Aggregate all form submissions to one export |
| **Extract all people** | Dump every person from People to JSON + CSV |

### Check-Ins
| Tool | Description |
|---|---|
| **Attendance trends** | Per-gathering counts with rolling averages and volunteer share |
| **First-time visitors** | First-time check-ins over a recent window |
| **Lapsed attenders** | Regulars who stopped showing up — a follow-up list |

### Bulk Writes (Services)
| Tool | Description |
|---|---|
| **Bulk schedule** | Schedule volunteers onto plans from a CSV (optionally send notifications) |
| **Roster sync** | Sync a team position's roster to a CSV (adds + removals, typed confirmation) |
| **Template copy** | Copy a template's people into one or many upcoming plans |
| **Auto-blockout** | Offer blockouts to volunteers who keep declining |

## Setup

1. **Install dependencies** (requires Python ≥ 3.12):
   ```bash
   # with uv (recommended)
   uv sync

   # or with pip
   pip install .
   ```

2. **Store API credentials in the system keyring** — on first run you will be prompted
   automatically. Get a Personal Access Token from
   [api.planningcenteronline.com](https://api.planningcenteronline.com/personal_access_tokens).
   Credentials are stored securely in your OS keychain (macOS Keychain,
   Windows Credential Manager, or a Secret Service on Linux) — never in files.
   For scripting/CI, `PCO_APP_ID` and `PCO_SECRET` environment variables are also honored.

3. **Configure** (optional):
   - `.env` — set `PCO_TIMEZONE` (required for blockout dates); see `.env.example`.
   - `config.toml` — report thresholds (burnout weights, lookback windows, horizons).

4. **Prepare input files** — drop CSVs into `input/`. See the `input/*.csv.example` files:
   - `ExampleBlockouts` — `Last Name, First Name, Reason, Start Date, End Date`
   - `ExampleBulkSchedule` — `Full Name, Date, Team, Position`
   - `ExampleRosterSync` — `Full Name`
   - `ExampleFieldUpdates` — `Full Name` plus one column per custom field

## Usage

```bash
uv run python main.py
```

Pick a number from the menu. Long scans show progress; the PCO rate limit
(100 requests / 20 s) is handled automatically with retries.

## Project Structure

```
PlanningCenterTools/
├── main.py                  # CLI entry point (menu)
├── config.toml              # Report thresholds & org settings
├── .env.example             # Template for non-sensitive config
├── pco/                     # Shared API layer
│   ├── client.py            # pypco wrapper: Services endpoints, caching, keyring
│   ├── people_api.py        # People API endpoints
│   ├── checkins_api.py      # Check-Ins API endpoints
│   ├── models.py            # Typed dataclasses mirroring API resources
│   ├── config.py            # config.toml loader
│   ├── report.py            # JSON/CSV/Markdown report writer
│   ├── names.py             # Fuzzy person-name matching
│   └── cli.py               # Interactive input pickers
├── services/                # Planning Center Services tools
│   ├── blockouts.py         # Bulk blockout creation
│   ├── volunteers.py        # In-plan duplicates & usage reports
│   ├── templates.py         # Template export
│   ├── reports/             # Read-only reports (declines, health, coverage, …)
│   └── write/               # Bulk writes (schedule, roster sync, template copy, …)
├── people/                  # People tools (duplicates, workflows, fields, forms)
├── checkins/                # Check-Ins reports (trends, first-timers, lapsed)
├── tests/                   # Unit tests (fixtures mirror real API shapes)
├── input/                   # Input CSVs (gitignored)
└── output/                  # Generated reports (gitignored)
```

## Development

```bash
uv sync --extra dev
uv run pytest          # tests
uv run ruff check .    # lint
```

Every API endpoint used in code carries a comment linking to its
documentation page at [developer.planning.center](https://developer.planning.center/docs/) —
keep that convention when adding endpoints, and keep test fixtures faithful
to the documented response shapes.

## License

MIT
