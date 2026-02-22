"""Rich demo data for --demo mode.

Provides:
- get_demo_dir()          → Path to bundled demo project folder
- refresh_demo_dates()    → Shift dates in demo.wbs.md so today is active
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

_ANCHOR_RE = re.compile(r"<!--\s*demo-anchor:\s*(\d{4}-\d{2}-\d{2})\s*-->")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def get_demo_dir() -> Path:
    """Return path to the bundled demo project folder."""
    return Path(__file__).parent / "demo"


def _extract_anchor(content: str) -> date | None:
    """Extract the anchor date from demo content."""
    m = _ANCHOR_RE.search(content)
    if m:
        return date.fromisoformat(m.group(1))
    return None


def _shift_dates_in_content(content: str, delta: timedelta) -> str:
    """Shift all YYYY-MM-DD dates in content by delta days.

    Also updates the demo-anchor comment.
    """
    if delta.days == 0:
        return content

    def _replace_date(m: re.Match) -> str:
        d = date.fromisoformat(m.group(0))
        return (d + delta).isoformat()

    return _DATE_RE.sub(_replace_date, content)


def refresh_demo_dates(target_date: date | None = None) -> None:
    """Shift dates in demo.wbs.md so today falls within the active phase.

    Reads the anchor date, computes delta to *target_date* (default: today),
    and rewrites the file with all dates shifted.
    """
    target = target_date or date.today()
    demo_file = get_demo_dir() / "demo.wbs.md"
    content = demo_file.read_text(encoding="utf-8")

    anchor = _extract_anchor(content)
    if anchor is None:
        msg = "demo.wbs.md missing <!-- demo-anchor: YYYY-MM-DD --> comment"
        raise ValueError(msg)

    delta = target - anchor
    if delta.days == 0:
        return

    new_content = _shift_dates_in_content(content, delta)
    demo_file.write_text(new_content, encoding="utf-8")
