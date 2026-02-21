"""Tests for project configuration."""

from pathlib import Path

import pytest

from tui_wbs.config import get_custom_field_ids, load_config, save_config
from tui_wbs.models import ColumnDef, FilterConfig, ProjectConfig, SortConfig, ViewConfig


class TestLoadConfig:
    def test_load_nonexistent(self, tmp_path):
        config = load_config(tmp_path)
        assert len(config.views) == 3  # default views: Table, Gantt, Board
        assert config.views[0].name == "Table"
        assert config.views[1].name == "Gantt"
        assert config.views[2].name == "Board"

    def test_load_existing(self, tmp_path):
        config_dir = tmp_path / ".tui-wbs"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(
            """
[project]
name = "Test Project"
default_view = "overview"
default_columns = ["title", "status"]

[[views]]
id = "overview"
name = "Overview"
type = "table"
columns = ["title", "status", "assignee"]
sort = { field = "status", order = "asc" }

[[views]]
id = "board"
name = "Board"
type = "kanban"
group_by = "status"
columns = ["title", "priority"]

  [[views.filters]]
  field = "assignee"
  operator = "eq"
  value = "Gihwan"
""",
            encoding="utf-8",
        )

        config = load_config(tmp_path)
        assert config.name == "Test Project"
        assert config.default_view == "overview"
        assert config.default_columns == ["title", "status"]
        assert len(config.views) == 2
        assert config.views[0].name == "Overview"
        assert config.views[0].sort.field == "status"
        assert config.views[1].name == "Board"
        assert config.views[1].type == "kanban"
        assert len(config.views[1].filters) == 1
        assert config.views[1].filters[0].field == "assignee"

    def test_load_with_custom_columns(self, tmp_path):
        config_dir = tmp_path / ".tui-wbs"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(
            """
[project]
name = "Test"

[[columns.custom]]
id = "team"
name = "Team"
type = "enum"
values = ["Frontend", "Backend"]

[[views]]
id = "v1"
name = "Table"
type = "table"
columns = ["title"]
sort = { field = "title", order = "asc" }
""",
            encoding="utf-8",
        )

        config = load_config(tmp_path)
        assert len(config.custom_columns) == 1
        assert config.custom_columns[0].id == "team"
        assert config.custom_columns[0].values == ["Frontend", "Backend"]


class TestSaveConfig:
    def test_save_and_reload(self, tmp_path):
        config = ProjectConfig(
            name="My Project",
            default_view="v1",
            default_columns=["title", "status", "priority"],
            custom_columns=[
                ColumnDef(id="team", name="Team", type="enum", values=["A", "B"]),
            ],
            views=[
                ViewConfig(
                    id="v1",
                    name="Main",
                    type="table",
                    columns=["title", "status"],
                    sort=SortConfig(field="priority", order="desc"),
                ),
                ViewConfig(
                    id="v2",
                    name="Gantt",
                    type="table+gantt",
                    columns=["title", "start", "end"],
                    gantt_scale="month",
                    gantt_level=2,
                ),
            ],
        )

        save_config(tmp_path, config)
        reloaded = load_config(tmp_path)

        assert reloaded.name == "My Project"
        assert reloaded.default_view == "v1"
        assert len(reloaded.views) == 2
        assert reloaded.views[0].name == "Main"
        assert reloaded.views[0].sort.field == "priority"
        assert reloaded.views[1].type == "table+gantt"
        assert reloaded.views[1].gantt_scale == "month"
        assert len(reloaded.custom_columns) == 1
        assert reloaded.custom_columns[0].values == ["A", "B"]


class TestDateFormatConfig:
    def test_default_date_format(self, tmp_path):
        """No date_format in config → default YYYY-MM-DD."""
        config = load_config(tmp_path)
        assert config.date_format == "YYYY-MM-DD"

    def test_save_and_load_date_format(self, tmp_path):
        """Round-trip: save date_format, reload, verify."""
        config = ProjectConfig(name="Test", date_format="DD.MM.YYYY")
        config.ensure_default_view()
        save_config(tmp_path, config)
        reloaded = load_config(tmp_path)
        assert reloaded.date_format == "DD.MM.YYYY"

    def test_invalid_date_format_falls_back(self, tmp_path):
        """Invalid date_format in TOML → falls back to default."""
        config_dir = tmp_path / ".tui-wbs"
        config_dir.mkdir()
        (config_dir / "config.toml").write_text(
            """
[project]
name = "Test"
date_format = "INVALID"

[[views]]
id = "v1"
name = "Table"
type = "table"
columns = ["title"]
sort = { field = "title", order = "asc" }
""",
            encoding="utf-8",
        )
        config = load_config(tmp_path)
        assert config.date_format == "YYYY-MM-DD"

    def test_all_valid_presets_round_trip(self, tmp_path):
        """Each preset survives save/load."""
        from tui_wbs.models import DATE_FORMAT_PRESETS
        for preset_key in DATE_FORMAT_PRESETS:
            config = ProjectConfig(name="Test", date_format=preset_key)
            config.ensure_default_view()
            save_config(tmp_path, config)
            reloaded = load_config(tmp_path)
            assert reloaded.date_format == preset_key, f"Failed for {preset_key}"


class TestGetCustomFieldIds:
    def test_get_ids(self):
        config = ProjectConfig(
            custom_columns=[
                ColumnDef(id="team", name="Team"),
                ColumnDef(id="risk", name="Risk"),
            ]
        )
        assert get_custom_field_ids(config) == {"team", "risk"}

    def test_empty(self):
        config = ProjectConfig()
        assert get_custom_field_ids(config) == set()
