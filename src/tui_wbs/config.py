"""Project configuration management using tomlkit."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import tomlkit
import yaml
from tomlkit.items import Table as TomlTable

from tui_wbs.models import (
    ColumnDef,
    FilterConfig,
    ProjectConfig,
    SortConfig,
    ViewConfig,
)

CONFIG_DIR = ".tui-wbs"
CONFIG_FILE = "config.toml"
SETTINGS_FILE = "settings.yaml"


def _get_config_path(project_dir: Path) -> Path:
    return project_dir / CONFIG_DIR / CONFIG_FILE


def load_config(project_dir: Path) -> ProjectConfig:
    """Load project configuration from .tui-wbs/config.toml."""
    config_path = _get_config_path(project_dir)
    config = ProjectConfig()

    if not config_path.exists():
        config.ensure_default_view()
        return config

    try:
        content = config_path.read_text(encoding="utf-8")
        doc = tomlkit.parse(content)
    except Exception:
        config.ensure_default_view()
        return config

    # Parse [project] section
    project_section = doc.get("project", {})
    config.name = str(project_section.get("name", ""))
    config.default_view = str(project_section.get("default_view", ""))
    if "theme_name" in project_section:
        config.theme_name = str(project_section.get("theme_name", "default_dark"))
    elif "dark_mode" in project_section:
        # Backwards compat: migrate dark_mode → theme_name
        is_dark = bool(project_section.get("dark_mode", True))
        config.theme_name = "default_dark" if is_dark else "default_light"

    if "date_format" in project_section:
        from tui_wbs.models import DATE_FORMAT_PRESETS, DEFAULT_DATE_FORMAT
        raw_fmt = str(project_section.get("date_format", "YYYY-MM-DD"))
        config.date_format = raw_fmt if raw_fmt in DATE_FORMAT_PRESETS else DEFAULT_DATE_FORMAT

    default_cols = project_section.get("default_columns")
    if isinstance(default_cols, list):
        config.default_columns = [str(c) for c in default_cols]

    # Parse [[columns.custom]]
    columns_section = doc.get("columns", {})
    custom_cols = columns_section.get("custom", [])
    if isinstance(custom_cols, list):
        for col_data in custom_cols:
            if isinstance(col_data, dict):
                col = ColumnDef(
                    id=str(col_data.get("id", "")),
                    name=str(col_data.get("name", "")),
                    type=str(col_data.get("type", "text")),
                    values=[str(v) for v in col_data.get("values", [])],
                )
                config.custom_columns.append(col)

    # Parse [[views]]
    views_data = doc.get("views", [])
    if isinstance(views_data, list):
        for view_data in views_data:
            if isinstance(view_data, dict):
                view = _parse_view(view_data)
                config.views.append(view)

    config.ensure_default_view()
    return config


def _parse_view(data: dict) -> ViewConfig:
    """Parse a single view configuration from TOML data."""
    view = ViewConfig(
        id=str(data.get("id", "")),
        name=str(data.get("name", "Table")),
        type=str(data.get("type", "table")),
    )

    cols = data.get("columns")
    if isinstance(cols, list):
        view.columns = [str(c) for c in cols]

    sort_data = data.get("sort")
    if isinstance(sort_data, dict):
        view.sort = SortConfig(
            field=str(sort_data.get("field", "title")),
            order=str(sort_data.get("order", "asc")),
        )

    col_widths = data.get("column_widths")
    if isinstance(col_widths, dict):
        view.column_widths = {str(k): int(v) for k, v in col_widths.items()}

    view.gantt_scale = str(data.get("gantt_scale", "week"))
    view.gantt_level = int(data.get("gantt_level", 3))
    view.group_by = str(data.get("group_by", "status"))

    # Parse filters
    filters_data = data.get("filters", [])
    if isinstance(filters_data, list):
        for f_data in filters_data:
            if isinstance(f_data, dict):
                view.filters.append(FilterConfig(
                    field=str(f_data.get("field", "")),
                    operator=str(f_data.get("operator", "eq")),
                    value=str(f_data.get("value", "")),
                ))

    return view


def save_config(project_dir: Path, config: ProjectConfig) -> None:
    """Save project configuration to .tui-wbs/config.toml."""
    config_path = _get_config_path(project_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    doc = tomlkit.document()

    # [project]
    project_table = tomlkit.table()
    project_table.add("name", config.name)
    project_table.add("default_view", config.default_view)
    project_table.add("theme_name", config.theme_name)
    project_table.add("date_format", config.date_format)
    project_table.add("default_columns", config.default_columns)
    doc.add("project", project_table)

    # [columns]
    if config.custom_columns:
        columns_table = tomlkit.table()
        custom_array = tomlkit.aot()
        for col in config.custom_columns:
            col_table = tomlkit.table()
            col_table.add("id", col.id)
            col_table.add("name", col.name)
            col_table.add("type", col.type)
            if col.values:
                col_table.add("values", col.values)
            custom_array.append(col_table)
        columns_table.add("custom", custom_array)
        doc.add("columns", columns_table)

    # [[views]]
    views_array = tomlkit.aot()
    for view in config.views:
        view_table = tomlkit.table()
        view_table.add("id", view.id)
        view_table.add("name", view.name)
        view_table.add("type", view.type)
        view_table.add("columns", view.columns)

        sort_table = tomlkit.inline_table()
        sort_table.append("field", view.sort.field)
        sort_table.append("order", view.sort.order)
        view_table.add("sort", sort_table)

        if view.column_widths:
            cw_table = tomlkit.inline_table()
            for k, v in view.column_widths.items():
                cw_table.append(k, v)
            view_table.add("column_widths", cw_table)

        if view.type in ("table+gantt",):
            view_table.add("gantt_scale", view.gantt_scale)
            view_table.add("gantt_level", view.gantt_level)

        if view.type == "kanban":
            view_table.add("group_by", view.group_by)

        if view.filters:
            filters_array = tomlkit.aot()
            for f in view.filters:
                f_table = tomlkit.table()
                f_table.add("field", f.field)
                f_table.add("operator", f.operator)
                f_table.add("value", f.value)
                filters_array.append(f_table)
            view_table.add("filters", filters_array)

        views_array.append(view_table)

    doc.add("views", views_array)

    config_path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def get_custom_field_ids(config: ProjectConfig) -> set[str]:
    """Get the set of custom field IDs defined in the config."""
    return {col.id for col in config.custom_columns}


# ── Settings (YAML) ─────────────────────────────────────────────

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


def load_settings(project_dir: Path | None = None) -> dict[str, Any]:
    """Load settings from default_settings.yaml + optional project override.

    1. Load ``default_settings.yaml`` bundled with the package.
    2. If *project_dir* is given and ``{project_dir}/.tui-wbs/settings.yaml``
       exists, deep-merge it on top of the defaults.
    3. Return the merged dict.
    """
    default_path = Path(__file__).parent / "default_settings.yaml"
    data = _load_yaml(default_path)

    if project_dir is not None:
        override_path = project_dir / CONFIG_DIR / SETTINGS_FILE
        if override_path.is_file():
            override = _load_yaml(override_path)
            if override:
                data = _deep_merge(data, override)

    return data


def get_holidays(settings: dict[str, Any]) -> list[date]:
    """Parse holiday date strings from settings into date objects."""
    raw = settings.get("holidays", [])
    holidays: list[date] = []
    if isinstance(raw, list):
        for item in raw:
            try:
                holidays.append(date.fromisoformat(str(item)))
            except (ValueError, TypeError):
                pass
    return holidays
