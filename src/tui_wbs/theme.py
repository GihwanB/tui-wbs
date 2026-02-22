"""YAML-based centralized color system for TUI WBS.

Each theme file defines a single color set (dark or light) with a ``dark`` flag.
Loads from ``themes/{name}.yaml`` and optionally merges
project-level overrides from ``{project_dir}/.tui-wbs/theme.yaml``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

from tui_wbs.models import Priority, Status

PRESET_DIR = Path(__file__).parent / "themes"


# ── Module-level variables (populated by _apply) ──────────────────

THEME_NAME: str = "default_dark"
THEME_IS_DARK: bool = True

STATUS_TODO: str
STATUS_IN_PROGRESS: str
STATUS_DONE: str
STATUS_COLORS: dict[Status, str]

PRIORITY_HIGH: str
PRIORITY_MEDIUM: str
PRIORITY_LOW: str
PRIORITY_COLORS: dict[Priority, str]

GANTT_HEADER: str
GANTT_TODAY_MARKER: str
GANTT_DEPENDENCY_ARROW: str
GANTT_MILESTONE: str
GANTT_BAR_DONE: str
GANTT_BAR_IN_PROGRESS: str
GANTT_BAR_TODO: str
GANTT_BAND_BG: str
GANTT_HIGHLIGHT_BG: str
GANTT_HIGHLIGHT_BORDER_COLOR: str
GANTT_HIGHLIGHT_BORDER_THICKNESS: int
GANTT_WEEKEND_BG: str
GANTT_HOLIDAY_BG: str

PROGRESS_THRESHOLDS: list[tuple[int, str]]

APP_BASE_BG: str

OVERDUE_TITLE: str
MILESTONE: str
STATUSBAR_DEMO: str
STATUSBAR_WARNING: str
WARNING_ICON: str


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


def _color(val, default: str = "white") -> str:
    """Resolve a value to a single color string.

    - str: return directly (new single-color format)
    - dict: pick ``dark`` or ``light`` key based on ``THEME_IS_DARK`` (backwards compat)
    """
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        mod = sys.modules[__name__]
        is_dark = getattr(mod, "THEME_IS_DARK", True)
        return str(val.get("dark" if is_dark else "light", default))
    return default


def _apply(data: dict) -> None:
    """Map parsed YAML data onto module-level constants."""
    mod = sys.modules[__name__]

    # ── Metadata ──
    mod.THEME_NAME = str(data.get("name", "default_dark"))
    mod.THEME_IS_DARK = bool(data.get("dark", True))

    # ── App (global) ──
    app = data.get("app", {})
    mod.APP_BASE_BG = _color(app.get("base_bg", "#1c1c1c"))

    # ── Status ──
    status = data.get("status", {})
    s_todo = _color(status.get("todo", "white"))
    s_ip = _color(status.get("in_progress", "white"))
    s_done = _color(status.get("done", "white"))

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
    p_high = _color(priority.get("high", "white"))
    p_med = _color(priority.get("medium", "white"))
    p_low = _color(priority.get("low", "white"))

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
    mod.GANTT_HEADER = _color(gantt.get("header", "white"))
    mod.GANTT_TODAY_MARKER = _color(gantt.get("today_marker", "white"))
    mod.GANTT_DEPENDENCY_ARROW = _color(gantt.get("dependency_arrow", "white"))
    mod.GANTT_MILESTONE = _color(gantt.get("milestone", "white"))
    mod.GANTT_BAR_DONE = _color(gantt.get("bar_done", "white"))
    mod.GANTT_BAR_IN_PROGRESS = _color(gantt.get("bar_in_progress", "white"))
    mod.GANTT_BAR_TODO = _color(gantt.get("bar_todo", "white"))
    mod.GANTT_BAND_BG = _color(gantt.get("band_bg", "#1c1c1c"))
    mod.GANTT_HIGHLIGHT_BG = _color(gantt.get("highlight_bg", "#333333"))
    mod.GANTT_HIGHLIGHT_BORDER_COLOR = _color(
        gantt.get("highlight_border_color", gantt.get("highlight_bg", "#333333"))
    )
    mod.GANTT_HIGHLIGHT_BORDER_THICKNESS = int(
        gantt.get("highlight_border_thickness", 1)
    )
    mod.GANTT_WEEKEND_BG = _color(gantt.get("weekend_bg", "#2a1a1a"))
    mod.GANTT_HOLIDAY_BG = _color(gantt.get("holiday_bg", "#3a2a1a"))

    # ── Progress ──
    progress_list = data.get("progress", [])
    thresholds: list[tuple[int, str]] = []
    for entry in progress_list:
        if isinstance(entry, dict):
            # New format: {min: N, color: "#hex"}
            # Backwards compat: {min: N, dark: "#hex", light: "#hex"}
            color_val = entry.get("color")
            if color_val is not None:
                thresholds.append((int(entry.get("min", 0)), str(color_val)))
            else:
                thresholds.append((int(entry.get("min", 0)), _color(entry)))
    mod.PROGRESS_THRESHOLDS = thresholds

    # ── UI ──
    ui = data.get("ui", {})
    mod.OVERDUE_TITLE = _color(ui.get("overdue_title", "white"))
    mod.MILESTONE = _color(ui.get("milestone", "white"))
    mod.STATUSBAR_DEMO = _color(ui.get("statusbar_demo", "white"))
    mod.STATUSBAR_WARNING = _color(ui.get("statusbar_warning", "white"))
    mod.WARNING_ICON = _color(ui.get("warning_icon", "white"))


# ── Public API ────────────────────────────────────────────────────

def build_textual_theme():
    """Build a single Textual Theme from the current loaded theme."""
    from textual.color import Color
    from textual.theme import Theme

    bg = APP_BASE_BG
    is_dark = THEME_IS_DARK

    if is_dark:
        return Theme(
            name="wbs-theme",
            primary="#0178D4",
            background=bg,
            surface=Color.parse(bg).lighten(0.04).hex,
            panel=Color.parse(bg).lighten(0.08).hex,
            dark=True,
        )
    else:
        return Theme(
            name="wbs-theme",
            primary="#004578",
            background=bg,
            surface=Color.parse(bg).darken(0.03).hex,
            panel=Color.parse(bg).darken(0.06).hex,
            dark=False,
        )


def list_presets() -> list[str]:
    """Return available preset theme names (without .yaml extension)."""
    return sorted(p.stem for p in PRESET_DIR.glob("*.yaml"))


def init_theme(project_dir: Path, preset: str | None = None) -> Path:
    """Copy a theme YAML → {project_dir}/.tui-wbs/theme.yaml.

    If *preset* is given, copies from ``themes/{preset}.yaml``;
    otherwise copies the bundled ``default_theme.yaml``.

    Raises FileExistsError if the destination already exists.
    Raises FileNotFoundError if the preset name is invalid.
    """
    dest = project_dir / ".tui-wbs" / "theme.yaml"
    if dest.exists():
        raise FileExistsError(str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)

    if preset is not None:
        src = PRESET_DIR / f"{preset}.yaml"
        if not src.is_file():
            raise FileNotFoundError(
                f"Unknown preset '{preset}'. "
                f"Available: {', '.join(list_presets())}"
            )
    else:
        src = Path(__file__).parent / "default_theme.yaml"

    shutil.copy2(src, dest)
    return dest


def load_theme(project_dir: Path | None = None, theme_name: str = "default_dark") -> None:
    """Load a named theme and optionally merge project overrides.

    1. Load ``themes/{theme_name}.yaml`` bundled with the package.
       Falls back to ``default_theme.yaml`` if not found.
    2. If *project_dir* is given and ``{project_dir}/.tui-wbs/theme.yaml``
       exists, deep-merge it on top of the theme data.
    3. Apply the merged data to module-level constants.
    """
    # Try named theme file first
    theme_path = PRESET_DIR / f"{theme_name}.yaml"
    if theme_path.is_file():
        data = _load_yaml(theme_path)
    else:
        # Fallback to default_theme.yaml (old format, backwards compat)
        default_path = Path(__file__).parent / "default_theme.yaml"
        data = _load_yaml(default_path)

    # Project-level override
    if project_dir is not None:
        override_path = project_dir / ".tui-wbs" / "theme.yaml"
        if override_path.is_file():
            override = _load_yaml(override_path)
            if override:
                data = _deep_merge(data, override)

    _apply(data)


# Apply default theme on module import
load_theme()
