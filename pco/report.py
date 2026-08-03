"""Standard report writer: emits output/{name}.json, .csv, and .md."""
from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def write(
    name: str,
    records: list[dict],
    fields: list[str],
    summary_lines: list[str],
    scope: str = "",
    date_range: tuple[str, str] | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Write report artifacts to output directory.

    Creates:
      output/{name}.json   – full records list
      output/{name}.csv    – flat CSV with given fields
      output/{name}.md     – Markdown summary with header

    Returns the output directory path.
    """
    out = output_dir if output_dir is not None else _OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)

    # JSON
    with open(out / f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)

    # CSV
    with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)

    # Markdown
    now_utc = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        f"# Report: {name}",
        f"Generated: {now_utc}",
        f"Scope: {scope}",
    ]
    if date_range:
        lines.append(f"Date range: {date_range[0]} to {date_range[1]}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.extend(summary_lines)

    with open(out / f"{name}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return out
