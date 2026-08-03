"""Shared helpers for write operations: previews and confirmation prompts."""
from __future__ import annotations


def confirm_apply(preview_lines: list[str], noun: str, destructive: bool = False) -> bool:
    """Show a dry-run preview and ask for explicit confirmation.

    Every write operation goes through this: the user always sees exactly
    what will change before anything is sent to the API.

    Args:
        preview_lines: Human-readable lines describing each pending change.
        noun: What is being changed, e.g. "blockouts", "assignments".
        destructive: If True, requires typing "yes" in full.

    Returns:
        True if the user confirmed.
    """
    print(f"\n── DRY RUN — {len(preview_lines)} {noun} would be changed ──")
    for line in preview_lines:
        print(f"  {line}")

    if not preview_lines:
        print("Nothing to do.")
        return False

    if destructive:
        answer = input('\nThis includes destructive changes. Type "yes" to apply: ').strip()
        return answer == "yes"
    answer = input("\nApply these changes? [y/N]: ").strip().lower()
    return answer in ("y", "yes")
