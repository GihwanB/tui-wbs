"""Tests for the Gantt chart widget."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from tui_wbs.models import Status, WBSNode, ViewConfig
from tui_wbs.widgets.gantt_chart import SCALE_CONFIG, GanttView


PAUSE = 0.15


@pytest.fixture
def gantt_project(tmp_path):
    """Create a project with date-bearing tasks spanning a wide range for Gantt tests."""
    (tmp_path / "project.wbs.md").write_text(
        "# Gantt Project\n"
        "<!-- status: IN_PROGRESS | start: 2026-01-01 | end: 2026-12-31 -->\n"
        "\n"
        "## Phase 1\n"
        "<!-- status: TODO | start: 2026-01-01 | end: 2026-06-30 | duration: 180d -->\n"
        "\n"
        "### Task 1.1\n"
        "<!-- status: TODO | start: 2026-01-01 | end: 2026-03-31 | duration: 90d -->\n"
        "\n"
        "### Task 1.2\n"
        "<!-- status: TODO | start: 2026-04-01 | end: 2026-06-30 | duration: 90d -->\n"
        "\n"
        "## Phase 2\n"
        "<!-- status: TODO | start: 2026-07-01 | end: 2026-12-31 | duration: 180d -->\n",
        encoding="utf-8",
    )
    return tmp_path


class TestScaleConfig:
    def test_all_scales_present(self):
        assert set(SCALE_CONFIG.keys()) == {"day", "week", "week2", "month", "quarter", "year"}

    def test_scale_values(self):
        assert SCALE_CONFIG["day"] == 1
        assert SCALE_CONFIG["week"] == 7
        assert SCALE_CONFIG["week2"] == 7
        assert SCALE_CONFIG["month"] == 30
        assert SCALE_CONFIG["quarter"] == 91
        assert SCALE_CONFIG["year"] == 365


class TestGanttViewDateRange:
    def test_date_range_from_nodes(self):
        view = GanttView()
        today = date(2026, 3, 1)
        nodes = [
            (
                WBSNode(
                    title="Task A",
                    level=1,
                    start=date(2026, 3, 1),
                    end=date(2026, 3, 10),
                ),
                0,
            ),
            (
                WBSNode(
                    title="Task B",
                    level=2,
                    start=date(2026, 3, 5),
                    end=date(2026, 3, 20),
                ),
                1,
            ),
        ]
        view.update_gantt(nodes, "week", today, 0)
        # date_start should be before earliest node start
        assert view._date_start <= date(2026, 3, 1)
        # date_end should be after latest node end
        assert view._date_end >= date(2026, 3, 20)

    def test_empty_rows(self):
        view = GanttView()
        today = date(2026, 3, 1)
        view.update_gantt([], "week", today, 0)
        assert view._rows == []

    def test_scroll_offset_shifts_date_range(self):
        view = GanttView()
        today = date(2026, 3, 1)
        node = (
            WBSNode(title="Task", level=1, start=date(2026, 3, 1), end=date(2026, 3, 10)),
            0,
        )
        view.update_gantt([node], "week", today, 0)
        start_no_offset = view._date_start

        view.update_gantt([node], "week", today, 5)
        start_offset = view._date_start
        assert start_offset > start_no_offset

    def test_scale_changes_days_per_col(self):
        view = GanttView()
        today = date(2026, 3, 1)
        node = (
            WBSNode(title="Task", level=1, start=date(2026, 3, 1), end=date(2026, 3, 10)),
            0,
        )
        view.update_gantt([node], "day", today, 0)
        assert view._days_per_col == 1

        view.update_gantt([node], "month", today, 0)
        assert view._days_per_col == 30


class TestGanttViewVirtualSize:
    def test_virtual_size_equals_row_count(self):
        """virtual_size height should equal len(rows), no header offset."""
        view = GanttView()
        today = date(2026, 3, 1)
        nodes = [
            (WBSNode(title="A", level=1, start=date(2026, 3, 1), end=date(2026, 3, 5)), 0),
            (WBSNode(title="B", level=2, start=date(2026, 3, 3), end=date(2026, 3, 10)), 1),
        ]
        view.update_gantt(nodes, "week", today, 0)
        assert view.virtual_size.height == 2

    def test_virtual_size_empty(self):
        view = GanttView()
        today = date(2026, 3, 1)
        view.update_gantt([], "week", today, 0)
        assert view.virtual_size.height == 0


class TestGanttViewDateToCol:
    def test_date_to_col_same_as_start(self):
        view = GanttView()
        view._date_start = date(2026, 3, 1)
        view._days_per_col = 7
        assert view._date_to_col(date(2026, 3, 1)) == 0

    def test_date_to_col_one_week_later(self):
        view = GanttView()
        view._date_start = date(2026, 3, 1)
        view._days_per_col = 7
        result = view._date_to_col(date(2026, 3, 8))
        assert result == 6

    def test_date_to_col_before_start_returns_zero(self):
        view = GanttView()
        view._date_start = date(2026, 3, 10)
        view._days_per_col = 7
        result = view._date_to_col(date(2026, 3, 1))
        assert result == 0


class TestGanttChartUpdateRows:
    def test_update_rows_from_table_format(self):
        """GanttChart.update_rows accepts (node, depth, hier_id) tuples."""
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        child = WBSNode(title="Child", level=2, start=date(2026, 3, 5))
        root = WBSNode(
            title="Root",
            level=1,
            start=date(2026, 3, 1),
            children=(child,),
        )
        flat_rows = [(root, 0, "1"), (child, 1, "1.1")]
        chart.update_rows(flat_rows)
        assert len(chart._flat_rows) == 2
        assert chart._flat_rows[0] == (root, 0)
        assert chart._flat_rows[1] == (child, 1)

    def test_update_rows_collapsed(self):
        """When table sends only root (collapsed), gantt shows only root."""
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        child = WBSNode(title="Child", level=2, start=date(2026, 3, 5))
        root = WBSNode(
            title="Root",
            level=1,
            start=date(2026, 3, 1),
            children=(child,),
        )
        flat_rows = [(root, 0, "1")]  # Child collapsed
        chart.update_rows(flat_rows)
        assert len(chart._flat_rows) == 1

    def test_set_scale(self):
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        chart._scale = "week"
        chart.set_scale("day")
        assert chart._scale == "day"

    def test_set_invalid_scale_ignored(self):
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        chart._scale = "week"
        chart.set_scale("invalid")
        assert chart._scale == "week"

    def test_go_to_today_resets_offset(self):
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        chart._scroll_offset = 10
        chart.go_to_today()
        assert chart._scroll_offset == 0

    def test_update_config_sets_scale(self):
        from tui_wbs.widgets.gantt_chart import GanttChart

        chart = GanttChart()
        chart._scale = "week"
        config = ViewConfig(gantt_scale="month")
        chart.update_config(config)
        assert chart._scale == "month"


# ── Gantt horizontal scroll via h/l keys ──


@pytest.mark.asyncio
async def test_gantt_scroll_right_with_l_key(gantt_project):
    """l key should scroll GanttView right in table+gantt view."""
    from tui_wbs.app import WBSApp

    app = WBSApp(project_dir=gantt_project)
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Switch to table+gantt view
        for v in app.config.views:
            if v.type == "table+gantt":
                app._active_view_id = v.id
                break
        app._refresh_ui()
        await pilot.pause(delay=PAUSE)

        from tui_wbs.widgets.gantt_chart import GanttChart

        gantt = app.query_one(GanttChart)

        initial_offset = gantt._scroll_offset

        app.action_kanban_right()
        await pilot.pause(delay=PAUSE)

        assert gantt._scroll_offset > initial_offset


@pytest.mark.asyncio
async def test_gantt_scroll_left_with_h_key(gantt_project):
    """h key should scroll GanttView left in table+gantt view."""
    from tui_wbs.app import WBSApp

    app = WBSApp(project_dir=gantt_project)
    async with app.run_test(size=(80, 30)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Switch to table+gantt view
        for v in app.config.views:
            if v.type == "table+gantt":
                app._active_view_id = v.id
                break
        app._refresh_ui()
        await pilot.pause(delay=PAUSE)

        from tui_wbs.widgets.gantt_chart import GanttChart

        gantt = app.query_one(GanttChart)

        # First scroll right to have room to scroll left
        gantt.scroll_gantt(3)
        await pilot.pause(delay=PAUSE)
        scrolled_right = gantt._scroll_offset
        assert scrolled_right > 0

        app.action_kanban_left()
        await pilot.pause(delay=PAUSE)

        assert gantt._scroll_offset < scrolled_right


@pytest.mark.asyncio
async def test_kanban_h_l_still_works(gantt_project):
    """h/l keys should still move kanban cards in kanban view."""
    from tui_wbs.app import WBSApp

    app = WBSApp(project_dir=gantt_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Switch to kanban view
        for v in app.config.views:
            if v.type == "kanban":
                app._active_view_id = v.id
                break
        app._refresh_ui()
        await pilot.pause(delay=PAUSE)

        # In kanban view, action_kanban_left/right should not raise
        app.action_kanban_left()
        app.action_kanban_right()
        await pilot.pause(delay=PAUSE)
