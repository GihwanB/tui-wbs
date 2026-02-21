"""YAML-based centralized color system for TUI WBS.

Loads colors from default_theme.yaml and optionally merges
project-level overrides from {project_dir}/.tui-wbs/theme.yaml.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import NamedTuple

import yaml

from tui_wbs.models import Priority, Status


class ColorPair(NamedTuple):
    """A pair of colors for dark and light themes."""

    dark: str
    light: str

    def resolve(self, is_dark: bool) -> str:
        return self.dark if is_dark else self.light


# ── Module-level variables (populated by _apply) ──────────────────

STATUS_TODO: ColorPair
STATUS_IN_PROGRESS: ColorPair
STATUS_DONE: ColorPair
STATUS_COLORS: dict[Status, ColorPair]

PRIORITY_HIGH: ColorPair
PRIORITY_MEDIUM: ColorPair
PRIORITY_LOW: ColorPair
PRIORITY_COLORS: dict[Priority, ColorPair]

GANTT_HEADER: ColorPair
GANTT_TODAY_MARKER: ColorPair
GANTT_DEPENDENCY_ARROW: ColorPair
GANTT_MILESTONE: ColorPair
GANTT_BAR_DONE: ColorPair
GANTT_BAR_IN_PROGRESS: ColorPair
GANTT_BAR_TODO: ColorPair
GANTT_BAND_BG: ColorPair
GANTT_BASE_BG: ColorPair
GANTT_HIGHLIGHT_BG: ColorPair
GANTT_WEEKEND_BG: ColorPair
GANTT_HOLIDAY_BG: ColorPair

PROGRESS_THRESHOLDS: list[tuple[int, ColorPair]]

OVERDUE_TITLE: ColorPair
MILESTONE: ColorPair
STATUSBAR_DEMO: ColorPair
STATUSBAR_WARNING: ColorPair
WARNING_ICON: ColorPair


# ── Internal helpers ──────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return a dict (empty dict on error)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (returns a new dict)."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        elif key in result and isinstance(result[key], list) and isinstance(val, list):
            result[key] = val  # lists are replaced, not appended
        else:
            result[key] = val
    return result


def _pair(d: dict) -> ColorPair:
    """Convert a {dark: ..., light: ...} dict to a ColorPair."""
    return ColorPair(str(d.get("dark", "white")), str(d.get("light", "white")))


def _apply(data: dict) -> None:
    """Map parsed YAML data onto module-level constants."""
    mod = sys.modules[__name__]

    # ── Status ──
    status = data.get("status", {})
    s_todo = _pair(status.get("todo", {}))
    s_ip = _pair(status.get("in_progress", {}))
    s_done = _pair(status.get("done", {}))

    mod.STATUS_TODO = s_todo
    mod.STATUS_IN_PROGRESS = s_ip
    mod.STATUS_DONE = s_done
    mod.STATUS_COLORS = {
        Status.TODO: s_todo,
        Status.IN_PROGRESS: s_ip,
        Status.DONE: s_done,
    }

    # ── Priority ──
    priority = data.get("priority", {})
    p_high = _pair(priority.get("high", {}))
    p_med = _pair(priority.get("medium", {}))
    p_low = _pair(priority.get("low", {}))

    mod.PRIORITY_HIGH = p_high
    mod.PRIORITY_MEDIUM = p_med
    mod.PRIORITY_LOW = p_low
    mod.PRIORITY_COLORS = {
        Priority.HIGH: p_high,
        Priority.MEDIUM: p_med,
        Priority.LOW: p_low,
    }

    # ── Gantt ──
    gantt = data.get("gantt", {})
    mod.GANTT_HEADER = _pair(gantt.get("header", {}))
    mod.GANTT_TODAY_MARKER = _pair(gantt.get("today_marker", {}))
    mod.GANTT_DEPENDENCY_ARROW = _pair(gantt.get("dependency_arrow", {}))
    mod.GANTT_MILESTONE = _pair(gantt.get("milestone", {}))
    mod.GANTT_BAR_DONE = _pair(gantt.get("bar_done", {}))
    mod.GANTT_BAR_IN_PROGRESS = _pair(gantt.get("bar_in_progress", {}))
    mod.GANTT_BAR_TODO = _pair(gantt.get("bar_todo", {}))
    mod.GANTT_BAND_BG = _pair(gantt.get("band_bg", {}))
    mod.GANTT_BASE_BG = _pair(gantt.get("base_bg", {}))
    mod.GANTT_HIGHLIGHT_BG = _pair(gantt.get("highlight_bg", {}))
    mod.GANTT_WEEKEND_BG = _pair(gantt.get("weekend_bg", {"dark": "#2a1a1a", "light": "#e8d8d8"}))
    mod.GANTT_HOLIDAY_BG = _pair(gantt.get("holiday_bg", {"dark": "#3a2a1a", "light": "#f0e0c8"}))

    # ── Progress ──
    progress_list = data.get("progress", [])
    thresholds: list[tuple[int, ColorPair]] = []
    for entry in progress_list:
        if isinstance(entry, dict):
            thresholds.append((int(entry.get("min", 0)), _pair(entry)))
    mod.PROGRESS_THRESHOLDS = thresholds

    # ── UI ──
    ui = data.get("ui", {})
    mod.OVERDUE_TITLE = _pair(ui.get("overdue_title", {}))
    mod.MILESTONE = _pair(ui.get("milestone", {}))
    mod.STATUSBAR_DEMO = _pair(ui.get("statusbar_demo", {}))
    mod.STATUSBAR_WARNING = _pair(ui.get("statusbar_warning", {}))
    mod.WARNING_ICON = _pair(ui.get("warning_icon", {}))


# ── Public API ────────────────────────────────────────────────────

def init_theme(project_dir: Path) -> Path:
    """Copy default_theme.yaml → {project_dir}/.tui-wbs/theme.yaml.

    Raises FileExistsError if the destination already exists.
    """
    dest = project_dir / ".tui-wbs" / "theme.yaml"
    if dest.exists():
        raise FileExistsError(str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = Path(__file__).parent / "default_theme.yaml"
    shutil.copy2(src, dest)
    return dest


def load_theme(project_dir: Path | None = None) -> None:
    """Load the default theme and optionally merge project overrides.

    1. Load ``default_theme.yaml`` bundled with the package.
    2. If *project_dir* is given and ``{project_dir}/.tui-wbs/theme.yaml``
       exists, deep-merge it on top of the defaults.
    3. Apply the merged data to module-level constants.
    """
    default_path = Path(__file__).parent / "default_theme.yaml"
    data = _load_yaml(default_path)

    if project_dir is not None:
        override_path = project_dir / ".tui-wbs" / "theme.yaml"
        if override_path.is_file():
            override = _load_yaml(override_path)
            if override:
                data = _deep_merge(data, override)

    _apply(data)


# Apply default theme on module import
load_theme()
