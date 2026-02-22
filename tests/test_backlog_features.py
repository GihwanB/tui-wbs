"""Tests for backlog features: hierarchical IDs, TODO delay warning, duration↔date sync, filter bar, columns, demo data, parent aggregation."""

from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from tui_wbs.app import WBSApp
from tui_wbs.models import (
    FilterConfig,
    ProjectConfig,
    SortConfig,
    Status,
    ViewConfig,
    WBSNode,
    duration_to_days,
    days_to_duration,
)

PAUSE = 0.1


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample project directory with WBS files."""
    (tmp_path / "project.wbs.md").write_text(
        "# My Project\n"
        "| status | assignee | priority |\n"
        "| --- | --- | --- |\n"
        "| IN_PROGRESS | Gihwan | HIGH |\n"
        "\n"
        "## Phase 1\n"
        "| status | assignee |\n"
        "| --- | --- |\n"
        "| TODO | Jane |\n"
        "\n"
        "### Task 1.1\n"
        "| status | assignee | duration |\n"
        "| --- | --- | --- |\n"
        "| DONE | Jane | 2d |\n"
        "\n"
        "### Task 1.2\n"
        "| status | assignee |\n"
        "| --- | --- |\n"
        "| IN_PROGRESS | John |\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def date_project(tmp_path):
    """Project with start/end/duration fields for date sync testing."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    (tmp_path / "project.wbs.md").write_text(
        f"# Project\n"
        f"| status | start | duration |\n"
        f"| --- | --- | --- |\n"
        f"| TODO | {today.isoformat()} | 5d |\n"
        f"\n"
        f"## Task A\n"
        f"| status | start |\n"
        f"| --- | --- |\n"
        f"| TODO | {yesterday.isoformat()} |\n"
        f"\n"
        f"## Task B\n"
        f"| status | start | end |\n"
        f"| --- | --- | --- |\n"
        f"| TODO | {today.isoformat()} | {(today + timedelta(days=10)).isoformat()} |\n",
        encoding="utf-8",
    )
    return tmp_path


# ── duration_to_days / days_to_duration unit tests ──


class TestDurationHelpers:
    def test_days(self):
        assert duration_to_days("5d") == 5

    def test_weeks(self):
        assert duration_to_days("2w") == 14

    def test_hours(self):
        assert duration_to_days("8h") == 1

    def test_hours_small(self):
        assert duration_to_days("1h") == 1  # min 1 day

    def test_months(self):
        assert duration_to_days("1m") == 30

    def test_empty(self):
        assert duration_to_days("") is None

    def test_invalid(self):
        assert duration_to_days("abc") is None

    def test_no_unit(self):
        assert duration_to_days("3") == 3

    def test_days_to_duration(self):
        assert days_to_duration(5) == "5d"

    def test_days_to_duration_zero(self):
        assert days_to_duration(0) == "0d"

    def test_days_to_duration_negative(self):
        assert days_to_duration(-1) == "0d"


# ── Hierarchical ID tests ──


@pytest.mark.asyncio
async def test_hierarchical_ids(sample_project):
    """Table should show hierarchical IDs like 1, 1.1, 1.1.1."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.widgets.wbs_table import WBSTable
        table = app.query_one(WBSTable)
        # Extract hierarchical IDs
        hier_ids = [hier_id for _, _, hier_id in table._flat_rows]
        assert hier_ids[0] == "1"       # My Project
        assert hier_ids[1] == "1.1"     # Phase 1
        assert hier_ids[2] == "1.1.1"   # Task 1.1
        assert hier_ids[3] == "1.1.2"   # Task 1.2


@pytest.mark.asyncio
async def test_hierarchical_ids_after_collapse(sample_project):
    """IDs should be stable after fold/unfold."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.widgets.wbs_table import WBSTable
        table = app.query_one(WBSTable)
        # Collapse Phase 1
        phase1_node = None
        for node, _, hier_id in table._flat_rows:
            if node.title == "Phase 1":
                phase1_node = node
                break
        assert phase1_node is not None
        table.toggle_collapse(phase1_node.id)
        # After collapse, children hidden but parent ID still correct
        hier_ids = [hier_id for _, _, hier_id in table._flat_rows]
        assert "1" in hier_ids
        assert "1.1" in hier_ids
        # Children are collapsed so 1.1.1 and 1.1.2 should not be visible
        assert "1.1.1" not in hier_ids
        assert "1.1.2" not in hier_ids


# ── TODO Delay Warning tests ──


@pytest.mark.asyncio
async def test_todo_overdue_red_text(date_project):
    """TODO nodes with past start dates should have red bold title."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.widgets.wbs_table import WBSTable
        from rich.text import Text

        table = app.query_one(WBSTable)
        # Find Task A (has yesterday's start date, TODO status)
        task_a = None
        for node, _, _ in table._flat_rows:
            if node.title == "Task A":
                task_a = node
                break
        assert task_a is not None
        assert task_a.status == Status.TODO
        assert task_a.start is not None
        assert task_a.start <= date.today()

        # Check that the row's title column is a Text object with red bold
        view_config = table._view_config
        row_data = table._make_row(task_a, 1, "1.1")
        title_idx = view_config.columns.index("title") if "title" in view_config.columns else -1
        assert title_idx >= 0
        title_cell = row_data[title_idx]
        assert isinstance(title_cell, Text)
        # The title text should contain "Task A" with "red bold" style
        plain = title_cell.plain
        assert "Task A" in plain


@pytest.mark.asyncio
async def test_done_node_no_red_text(date_project):
    """DONE nodes should NOT get red text even if start is past."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Change Task A to DONE
        task_a = app.project.find_node_by_title("Task A")
        assert task_a is not None
        app._update_node(task_a.id, status=Status.DONE)

        from tui_wbs.widgets.wbs_table import WBSTable
        from rich.text import Text

        table = app.query_one(WBSTable)
        updated_node = app._node_map[task_a.id]
        row_data = table._make_row(updated_node, 1, "1.1")
        view_config = table._view_config
        title_idx = view_config.columns.index("title")
        title_cell = row_data[title_idx]
        assert isinstance(title_cell, Text)
        # Should NOT have red bold style on the title portion
        # Find the "Task A" span and check it doesn't have red
        start_pos = title_cell.plain.index("Task A")
        end_pos = start_pos + len("Task A")
        spans = title_cell._spans
        red_bold_on_title = any(
            s.style and "red" in str(s.style) and "bold" in str(s.style)
            for s in spans
            if s.start <= start_pos and s.end >= end_pos
        )
        assert not red_bold_on_title


# ── Duration ↔ Date Sync tests ──


@pytest.mark.asyncio
async def test_duration_edit_updates_end(date_project):
    """Editing duration when start exists should auto-calculate end."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Project node has start=today, duration=5d
        project_node = app.project.find_node_by_title("Project")
        assert project_node is not None
        today = date.today()
        assert project_node.start == today

        # Edit duration to 10d
        app._apply_field_edit(project_node.id, "duration", "10d")
        updated = app._node_map[project_node.id]
        assert updated.duration == "10d"
        assert updated.end == today + timedelta(days=10)


@pytest.mark.asyncio
async def test_start_edit_updates_end_when_duration_exists(date_project):
    """Editing start when duration exists should auto-calculate end."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        project_node = app.project.find_node_by_title("Project")
        assert project_node is not None
        new_start = date.today() + timedelta(days=5)
        app._apply_field_edit(project_node.id, "start", new_start.isoformat())
        updated = app._node_map[project_node.id]
        assert updated.start == new_start
        # duration is "5d" → end = start + 5
        assert updated.end == new_start + timedelta(days=5)


@pytest.mark.asyncio
async def test_end_edit_updates_duration(date_project):
    """Editing end when start exists should auto-calculate duration."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Task B has start=today, end=today+10
        task_b = app.project.find_node_by_title("Task B")
        assert task_b is not None
        new_end = date.today() + timedelta(days=20)
        app._apply_field_edit(task_b.id, "end", new_end.isoformat())
        updated = app._node_map[task_b.id]
        assert updated.end == new_end
        diff = (new_end - updated.start).days
        assert updated.duration == f"{diff}d"


@pytest.mark.asyncio
async def test_start_edit_calculates_duration_when_end_exists_no_duration(date_project):
    """Editing start when end exists and no duration should calculate duration."""
    app = WBSApp(project_dir=date_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Task B has start, end, but let's clear duration first
        task_b = app.project.find_node_by_title("Task B")
        assert task_b is not None
        app._update_node(task_b.id, duration="")
        task_b = app._node_map[task_b.id]
        assert task_b.duration == ""

        new_start = date.today()
        app._apply_field_edit(task_b.id, "start", new_start.isoformat())
        updated = app._node_map[task_b.id]
        # end was today+10, start is today → duration = 10d
        expected_days = (task_b.end - new_start).days
        assert updated.duration == f"{expected_days}d"


# ── Filter Bar Display tests ──


@pytest.mark.asyncio
async def test_filter_bar_shows_hint_when_empty(sample_project):
    """FilterBar should show hint text when no filters and no sort active."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.widgets.filter_bar import FilterBar
        from textual.widgets import Static

        filter_bar = app.query_one(FilterBar)
        # Clear sort to test fully empty state
        filter_bar.update_filters([], None)
        await pilot.pause(delay=PAUSE)
        hint = filter_bar.query_one("#filter-bar-hint", Static)
        assert hint.display is True


@pytest.mark.asyncio
async def test_filter_bar_shows_sort_without_filters(sample_project):
    """Sort info should display even when no filters are active."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.widgets.filter_bar import FilterBar
        from tui_wbs.models import SortConfig
        from textual.widgets import Static

        filter_bar = app.query_one(FilterBar)
        # Apply sort without filters
        filter_bar.update_filters([], SortConfig(field="title", order="asc"))
        await pilot.pause(delay=PAUSE)
        # Hint should be hidden
        hint = filter_bar.query_one("#filter-bar-hint", Static)
        assert hint.display is False
        # Sort info should be visible
        sort_widget = filter_bar.query_one("#filter-bar-sort", Static)
        assert sort_widget.display is True


# ── Default Column Order tests ──


class TestDefaultColumns:
    def test_project_config_default_columns_order(self):
        """ProjectConfig.default_columns should have progress and correct order."""
        config = ProjectConfig()
        expected = [
            "id", "title", "status", "priority", "progress", "assignee", "start", "end", "duration",
            "module", "label",
        ]
        assert config.default_columns == expected

    def test_view_config_default_columns_order(self):
        """ViewConfig default columns should have priority before assignee."""
        view = ViewConfig()
        assert view.columns == ["title", "status", "priority", "assignee", "duration"]

    def test_ensure_default_view_table_columns(self):
        """ensure_default_view() table view should include progress column."""
        config = ProjectConfig()
        config.ensure_default_view()
        table_view = config.get_view("default-table")
        assert table_view is not None
        expected = [
            "id", "title", "status", "priority", "progress", "assignee", "start", "end", "duration",
            "module", "label",
        ]
        assert table_view.columns == expected


# ── Demo Data Label/Module tests ──


class TestDemoDataLabelModule:
    def _parse_demo(self):
        from tui_wbs.demo_data import get_demo_dir
        from tui_wbs.parser import parse_markdown
        demo_file = get_demo_dir() / "demo.wbs.md"
        content = demo_file.read_text(encoding="utf-8")
        return parse_markdown(content, "demo.wbs.md")

    def test_all_nodes_have_label(self):
        """Every node in demo data should have a label custom field."""
        doc = self._parse_demo()
        for node in doc.all_nodes():
            assert "label" in node.custom_fields, f"Node '{node.title}' missing label"
            assert node.custom_fields["label"], f"Node '{node.title}' has empty label"

    def test_all_nodes_have_module(self):
        """Every node in demo data should have a module custom field."""
        doc = self._parse_demo()
        for node in doc.all_nodes():
            assert "module" in node.custom_fields, f"Node '{node.title}' missing module"
            assert node.custom_fields["module"], f"Node '{node.title}' has empty module"

    def test_phase1_labels(self):
        """Phase 1 nodes should have label=planning, module=project-mgmt."""
        doc = self._parse_demo()
        phase1_titles = {"Phase 1: Discovery & Planning", "Stakeholder Interviews",
                         "Competitive Analysis", "Requirements Document", "Planning Milestone"}
        for node in doc.all_nodes():
            if node.title in phase1_titles:
                assert node.custom_fields["label"] == "planning"
                assert node.custom_fields["module"] == "project-mgmt"

    def test_backend_labels(self):
        """Backend development nodes should have label=backend."""
        doc = self._parse_demo()
        backend_titles = {"API Gateway Setup", "Authentication Service",
                          "Task CRUD Backend", "Real-time Sync Engine",
                          "Notification System", "Search & Filtering"}
        for node in doc.all_nodes():
            if node.title in backend_titles:
                assert node.custom_fields["label"] == "backend"


# ── Parent Date Aggregation tests ──


@pytest.fixture
def aggregation_project(tmp_path):
    """Project for testing parent date aggregation."""
    (tmp_path / "project.wbs.md").write_text(
        "# Root\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n"
        "\n"
        "## Parent\n"
        "| status | start | end |\n"
        "| --- | --- | --- |\n"
        "| TODO | 2025-01-01 | 2025-01-10 |\n"
        "\n"
        "### Child A\n"
        "| status | start | end |\n"
        "| --- | --- | --- |\n"
        "| TODO | 2025-01-05 | 2025-01-15 |\n"
        "\n"
        "### Child B\n"
        "| status | start | end |\n"
        "| --- | --- | --- |\n"
        "| TODO | 2025-01-03 | 2025-01-20 |\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.asyncio
async def test_propagate_dates_updates_parent(aggregation_project):
    """Editing child start/end should update parent's start/end."""
    app = WBSApp(project_dir=aggregation_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        child_a = app.project.find_node_by_title("Child A")
        assert child_a is not None
        # Move Child A start earlier
        app._apply_field_edit(child_a.id, "start", "2025-01-01")
        parent = app.project.find_node_by_title("Parent")
        parent_node = app._node_map[parent.id]
        # Parent start should be min(Child A start=Jan 1, Child B start=Jan 3) = Jan 1
        assert parent_node.start == date(2025, 1, 1)


@pytest.mark.asyncio
async def test_propagate_dates_max_end(aggregation_project):
    """Parent end should be max of children's end dates."""
    app = WBSApp(project_dir=aggregation_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        child_b = app.project.find_node_by_title("Child B")
        assert child_b is not None
        # Extend Child B's end
        app._apply_field_edit(child_b.id, "end", "2025-02-28")
        parent = app.project.find_node_by_title("Parent")
        parent_node = app._node_map[parent.id]
        assert parent_node.end == date(2025, 2, 28)


@pytest.mark.asyncio
async def test_propagate_dates_no_change_when_within_range(aggregation_project):
    """Parent dates should not change if child dates stay within existing range."""
    app = WBSApp(project_dir=aggregation_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        parent = app.project.find_node_by_title("Parent")
        parent_node = app._node_map[parent.id]
        original_start = parent_node.start
        original_end = parent_node.end

        # Set parent to match children's range first
        app._update_node(parent.id, start=date(2025, 1, 3), end=date(2025, 1, 20))
        parent_node = app._node_map[parent.id]

        # Edit Child A start to be within range - parent should get min(children starts)
        child_a = app.project.find_node_by_title("Child A")
        app._apply_field_edit(child_a.id, "start", "2025-01-04")
        parent_node = app._node_map[parent.id]
        # min start = Child B Jan 3, so parent stays Jan 3
        assert parent_node.start == date(2025, 1, 3)


@pytest.mark.asyncio
async def test_propagate_dates_cascades_to_grandparent(aggregation_project):
    """Date changes should cascade from child → parent → grandparent."""
    app = WBSApp(project_dir=aggregation_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Set Root to have dates so we can test cascade
        root = app.project.find_node_by_title("Root")
        app._update_node(root.id, start=date(2025, 1, 1), end=date(2025, 1, 10))

        child_b = app.project.find_node_by_title("Child B")
        app._apply_field_edit(child_b.id, "end", "2025-03-15")

        # Parent should update
        parent_node = app._node_map[app.project.find_node_by_title("Parent").id]
        assert parent_node.end == date(2025, 3, 15)
        # Root (grandparent) should also update
        root_node = app._node_map[root.id]
        assert root_node.end == date(2025, 3, 15)


@pytest.mark.asyncio
async def test_propagate_dates_via_duration(aggregation_project):
    """Editing duration should propagate recalculated end to parent."""
    app = WBSApp(project_dir=aggregation_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        child_a = app.project.find_node_by_title("Child A")
        assert child_a is not None
        # Child A start=Jan 5, set duration=30d → end=Jan 5+30=Feb 4
        app._apply_field_edit(child_a.id, "duration", "30d")
        updated_a = app._node_map[child_a.id]
        assert updated_a.end == date(2025, 1, 5) + timedelta(days=30)

        parent_node = app._node_map[app.project.find_node_by_title("Parent").id]
        # Parent end should be max(Child A end=Feb 4, Child B end=Jan 20) = Feb 4
        assert parent_node.end == date(2025, 1, 5) + timedelta(days=30)
