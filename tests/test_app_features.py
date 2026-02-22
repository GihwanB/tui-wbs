"""Integration tests for Phase 2-4 app features."""

from dataclasses import replace
from pathlib import Path

import pytest

from tui_wbs.app import WBSApp
from tui_wbs.models import (
    FilterConfig,
    Priority,
    ProjectConfig,
    SortConfig,
    Status,
    ViewConfig,
    WBSNode,
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
        "| status | assignee | depends |\n"
        "| --- | --- | --- |\n"
        "| IN_PROGRESS | John | Task 1.1 |\n",
        encoding="utf-8",
    )
    return tmp_path


# ── Node CRUD Tests ──


@pytest.mark.asyncio
async def test_add_child_node(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        count_before = len(app.project.all_nodes())
        first_node = app.project.all_nodes()[0]
        # Add a child node
        app._add_node_to_parent(
            first_node.id,
            WBSNode(
                title="New Child",
                level=first_node.level + 1,
                source_file=first_node.source_file,
                _meta_modified=True,
            ),
        )
        count_after = len(app.project.all_nodes())
        assert count_after == count_before + 1
        assert app._modified is True
        # Verify the new node exists
        new_node = app.project.find_node_by_title("New Child")
        assert new_node is not None
        assert new_node.level == first_node.level + 1


@pytest.mark.asyncio
async def test_add_sibling_node(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        count_before = len(app.project.all_nodes())
        # Get Task 1.1 and add a sibling
        task11 = app.project.find_node_by_title("Task 1.1")
        assert task11 is not None
        app._add_sibling_node(
            task11.id,
            WBSNode(
                title="Task 1.1b",
                level=task11.level,
                source_file=task11.source_file,
                _meta_modified=True,
            ),
        )
        count_after = len(app.project.all_nodes())
        assert count_after == count_before + 1


@pytest.mark.asyncio
async def test_delete_node(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        count_before = len(app.project.all_nodes())
        task12 = app.project.find_node_by_title("Task 1.2")
        assert task12 is not None
        app._delete_node_by_id(task12.id)
        count_after = len(app.project.all_nodes())
        assert count_after == count_before - 1
        assert app.project.find_node_by_title("Task 1.2") is None


@pytest.mark.asyncio
async def test_delete_node_with_children(sample_project):
    """Deleting a parent should remove all children."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        phase1 = app.project.find_node_by_title("Phase 1")
        assert phase1 is not None
        child_count = len(phase1.all_nodes())  # includes phase1 itself
        count_before = len(app.project.all_nodes())
        app._delete_node_by_id(phase1.id)
        count_after = len(app.project.all_nodes())
        assert count_after == count_before - child_count


# ── Status Change Tests ──


@pytest.mark.asyncio
async def test_status_change(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Task 1.1")
        assert task is not None
        assert task.status == Status.DONE
        app._update_node(task.id, status=Status.TODO)
        updated = app._node_map.get(task.id)
        assert updated is not None
        assert updated.status == Status.TODO


# ── Depends Auto-Update Tests ──


@pytest.mark.asyncio
async def test_depends_auto_update_on_rename(sample_project):
    """Renaming a node should update depends references."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        # Task 1.2 depends on "Task 1.1"
        task11 = app.project.find_node_by_title("Task 1.1")
        assert task11 is not None
        task12 = app.project.find_node_by_title("Task 1.2")
        assert task12 is not None
        assert "Task 1.1" in task12.depends

        # Simulate title edit + depends update
        app._on_title_edited(task11.id, "Requirements Done")

        # Verify Task 1.2's depends was updated
        updated_12 = app._node_map.get(task12.id)
        assert updated_12 is not None
        assert "Requirements Done" in updated_12.depends
        assert "Task 1.1" not in updated_12.depends


# ── Search Tests ──


@pytest.mark.asyncio
async def test_search_finds_matches(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app._perform_search("Jane")
        assert len(app._search_matches) == 2  # Phase 1 + Task 1.1
        assert app._search_index == 0


@pytest.mark.asyncio
async def test_search_no_matches(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app._perform_search("Nonexistent")
        assert len(app._search_matches) == 0
        assert app._search_index == -1


@pytest.mark.asyncio
async def test_search_next_prev(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app._perform_search("Task")
        assert len(app._search_matches) == 2
        assert app._search_index == 0
        app.action_search_next()
        assert app._search_index == 1
        app.action_search_next()
        assert app._search_index == 0  # Wraps around
        app.action_search_prev()
        assert app._search_index == 1  # Wraps backward


# ── Node Movement Tests ──


@pytest.mark.asyncio
async def test_move_node_down(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        phase1 = app.project.find_node_by_title("Phase 1")
        assert phase1 is not None
        # Phase 1 has children: Task 1.1, Task 1.2
        first_child_title = phase1.children[0].title
        assert first_child_title == "Task 1.1"

        # Move Task 1.1 down
        app._move_node_in_siblings(phase1.children[0].id, 1)

        # Re-fetch phase1 from project
        phase1_updated = app.project.find_node_by_title("Phase 1")
        assert phase1_updated is not None
        # Now Task 1.2 should be first
        assert phase1_updated.children[0].title == "Task 1.2"
        assert phase1_updated.children[1].title == "Task 1.1"


@pytest.mark.asyncio
async def test_change_node_level(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task11 = app.project.find_node_by_title("Task 1.1")
        assert task11 is not None
        original_level = task11.level
        app._change_node_level(task11.id, 1)  # Indent
        updated = app._node_map.get(task11.id)
        assert updated is not None
        assert updated.level == original_level + 1


@pytest.mark.asyncio
async def test_change_node_level_min_one(sample_project):
    """Level should not go below 1."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        root = app.project.all_nodes()[0]
        assert root.level == 1
        app._change_node_level(root.id, -1)  # Try to go below 1
        updated = app._node_map.get(root.id)
        assert updated is not None
        assert updated.level == 1  # Should remain 1


# ── View Management Tests ──


@pytest.mark.asyncio
async def test_create_new_view(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        views_before = len(app.config.views)
        app._on_new_view_name("My Kanban")
        assert len(app.config.views) == views_before + 1
        assert app.config.views[-1].name == "My Kanban"
        assert app._modified is True


@pytest.mark.asyncio
async def test_create_view_empty_name_ignored(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        views_before = len(app.config.views)
        app._on_new_view_name("")
        assert len(app.config.views) == views_before
        app._on_new_view_name(None)
        assert len(app.config.views) == views_before


# ── Settings Tests ──


@pytest.mark.asyncio
async def test_settings_save(sample_project):
    from tui_wbs.models import ProjectConfig
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        new_config = ProjectConfig(name="Updated Name")
        new_config.ensure_default_view()
        app._on_settings_saved(new_config)
        assert app.config.name == "Updated Name"
        assert app._modified is True


@pytest.mark.asyncio
async def test_settings_cancel(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        old_name = app.config.name
        app._on_settings_saved(None)
        assert app.config.name == old_name


# ── Undo/Redo Extended Tests ──


@pytest.mark.asyncio
async def test_undo_stack_limit(sample_project):
    """Undo stack should be limited to 50."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        first_node = app.project.all_nodes()[0]
        # Push 55 undo states
        for i in range(55):
            app._update_node(first_node.id, memo=f"memo-{i}")
        assert len(app._undo_stack) <= 50


@pytest.mark.asyncio
async def test_redo_cleared_on_new_change(sample_project):
    """Making a new change should clear redo stack."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        first_node = app.project.all_nodes()[0]
        app._update_node(first_node.id, memo="change1")
        app.action_undo()
        assert len(app._redo_stack) >= 1
        # Now make a new change
        app._update_node(first_node.id, memo="change2")
        assert len(app._redo_stack) == 0  # Redo cleared


# ── Filter & Sort Tests ──


class TestFilterSort:
    """Unit tests for filter/sort static methods (no app needed)."""

    def test_filter_eq(self):
        node = WBSNode(title="Task", level=1, status=Status.TODO)
        f = FilterConfig(field="status", operator="eq", value="TODO")
        assert WBSApp._node_matches_filter(node, f) is True

    def test_filter_eq_case_insensitive(self):
        node = WBSNode(title="Task", level=1, status=Status.TODO)
        f = FilterConfig(field="status", operator="eq", value="todo")
        assert WBSApp._node_matches_filter(node, f) is True

    def test_filter_neq(self):
        node = WBSNode(title="Task", level=1, status=Status.DONE)
        f = FilterConfig(field="status", operator="neq", value="TODO")
        assert WBSApp._node_matches_filter(node, f) is True

    def test_filter_contains(self):
        node = WBSNode(title="Task", level=1, assignee="Jane Doe")
        f = FilterConfig(field="assignee", operator="contains", value="jane")
        assert WBSApp._node_matches_filter(node, f) is True

    def test_filter_contains_no_match(self):
        node = WBSNode(title="Task", level=1, assignee="Jane Doe")
        f = FilterConfig(field="assignee", operator="contains", value="bob")
        assert WBSApp._node_matches_filter(node, f) is False

    def test_apply_filters_keeps_matching_parent(self):
        child = WBSNode(title="Child", level=2, status=Status.DONE)
        parent = WBSNode(title="Parent", level=1, status=Status.TODO, children=(child,))
        filters = [FilterConfig(field="status", operator="eq", value="DONE")]
        result = WBSApp._apply_filters([parent], filters)
        # Parent should be kept because child matches
        assert len(result) == 1
        assert result[0].title == "Parent"
        assert len(result[0].children) == 1
        assert result[0].children[0].title == "Child"

    def test_apply_filters_removes_all_non_matching(self):
        node = WBSNode(title="A", level=1, status=Status.TODO)
        filters = [FilterConfig(field="status", operator="eq", value="DONE")]
        result = WBSApp._apply_filters([node], filters)
        assert len(result) == 0

    def test_apply_filters_empty_filters(self):
        node = WBSNode(title="A", level=1)
        result = WBSApp._apply_filters([node], [])
        assert len(result) == 1

    def test_sort_by_status(self):
        n1 = WBSNode(title="C", level=1, status=Status.DONE)
        n2 = WBSNode(title="A", level=1, status=Status.TODO)
        n3 = WBSNode(title="B", level=1, status=Status.IN_PROGRESS)
        sort = SortConfig(field="status", order="asc")
        result = WBSApp._apply_sort([n1, n2, n3], sort)
        assert [n.status for n in result] == [Status.TODO, Status.IN_PROGRESS, Status.DONE]

    def test_sort_by_priority(self):
        n1 = WBSNode(title="A", level=1, priority=Priority.LOW)
        n2 = WBSNode(title="B", level=1, priority=Priority.HIGH)
        n3 = WBSNode(title="C", level=1, priority=Priority.MEDIUM)
        sort = SortConfig(field="priority", order="asc")
        result = WBSApp._apply_sort([n1, n2, n3], sort)
        assert [n.priority for n in result] == [Priority.HIGH, Priority.MEDIUM, Priority.LOW]

    def test_sort_by_title_desc(self):
        n1 = WBSNode(title="Alpha", level=1)
        n2 = WBSNode(title="Charlie", level=1)
        n3 = WBSNode(title="Bravo", level=1)
        sort = SortConfig(field="title", order="desc")
        result = WBSApp._apply_sort([n1, n2, n3], sort)
        assert [n.title for n in result] == ["Charlie", "Bravo", "Alpha"]

    def test_sort_recursive(self):
        c1 = WBSNode(title="B-Child", level=2, status=Status.DONE)
        c2 = WBSNode(title="A-Child", level=2, status=Status.TODO)
        parent = WBSNode(title="Parent", level=1, children=(c1, c2))
        sort = SortConfig(field="status", order="asc")
        result = WBSApp._apply_sort([parent], sort)
        assert result[0].children[0].title == "A-Child"  # TODO comes first
        assert result[0].children[1].title == "B-Child"  # DONE comes last


# ── Filter Integration Tests ──


@pytest.mark.asyncio
async def test_filter_applied_in_refresh_ui(sample_project):
    """Filters should affect nodes displayed in table."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        view = app._get_active_view()
        assert view is not None
        # Add filter: assignee contains "Jane"
        view.filters = [FilterConfig(field="assignee", operator="contains", value="Jane")]
        app._refresh_ui()
        # Table should only show nodes related to Jane
        from tui_wbs.widgets.wbs_table import WBSTable
        table = app.query_one(WBSTable)
        displayed_titles = [node.title for node, _, _ in table._flat_rows]
        assert "Phase 1" in displayed_titles  # Parent kept because child matches
        assert "Task 1.1" in displayed_titles  # Jane's task


# ── View Switching Tests ──


@pytest.mark.asyncio
async def test_switch_to_adjacent_view_next(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert len(app.config.views) >= 2
        first_view_id = app._active_view_id
        app._switch_to_adjacent_view(1)
        assert app._active_view_id != first_view_id
        assert app._active_view_id == app.config.views[1].id


@pytest.mark.asyncio
async def test_switch_to_adjacent_view_wraps(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Go to last view
        last_idx = len(app.config.views) - 1
        app._active_view_id = app.config.views[last_idx].id
        app._switch_to_adjacent_view(1)
        assert app._active_view_id == app.config.views[0].id


@pytest.mark.asyncio
async def test_switch_to_view_by_index(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert len(app.config.views) >= 3
        # Simulate switching to view 2 (index 1)
        app._active_view_id = app.config.views[1].id
        app._refresh_ui()
        assert app._active_view_id == app.config.views[1].id


@pytest.mark.asyncio
async def test_focus_tabs_action(sample_project):
    """Test that action_focus_tabs focuses the ViewTabs widget."""
    from tui_wbs.widgets.view_tabs import ViewTabs
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_focus_tabs()
        await pilot.pause(delay=PAUSE)
        assert isinstance(app.focused, ViewTabs)


@pytest.mark.asyncio
async def test_focus_content_action(sample_project):
    """Test that action_focus_content focuses the DataTable."""
    from textual.widgets import DataTable
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_focus_content()
        await pilot.pause(delay=PAUSE)
        assert isinstance(app.focused, DataTable)


@pytest.mark.asyncio
async def test_focus_filters_no_filters(sample_project):
    """Focus filters should focus FilterBar (always visible even without filters)."""
    from tui_wbs.widgets.filter_bar import FilterBar
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_focus_filters()
        await pilot.pause(delay=PAUSE)
        # FilterBar is always visible now, so it should be focusable
        assert isinstance(app.focused, FilterBar)


@pytest.mark.asyncio
async def test_view_tabs_arrow_navigation(sample_project):
    """After focusing ViewTabs, arrow keys should switch views."""
    from tui_wbs.widgets.view_tabs import ViewTabs
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert len(app.config.views) >= 2
        first_view_id = app._active_view_id
        app.action_focus_tabs()
        await pilot.pause(delay=PAUSE)
        # Press right arrow to switch to next view
        await pilot.press("right")
        await pilot.pause(delay=PAUSE)
        assert app._active_view_id != first_view_id
        assert app._active_view_id == app.config.views[1].id


@pytest.mark.asyncio
async def test_cycle_status(sample_project):
    """Test status cycling: TODO → IN_PROGRESS → DONE → TODO."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        assert task.status == Status.TODO
        app._update_node(task.id, status=Status.IN_PROGRESS)
        updated = app._node_map.get(task.id)
        assert updated.status == Status.IN_PROGRESS
        app._update_node(task.id, status=Status.DONE)
        updated = app._node_map.get(task.id)
        assert updated.status == Status.DONE
        app._update_node(task.id, status=Status.TODO)
        updated = app._node_map.get(task.id)
        assert updated.status == Status.TODO


@pytest.mark.asyncio
async def test_autosave_timer_scheduled(sample_project):
    """Test that _mark_modified schedules an autosave timer."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app._autosave_timer is None
        assert app.project is not None
        first_node = app.project.all_nodes()[0]
        app._update_node(first_node.id, memo="test autosave")
        assert app._modified is True
        assert app._autosave_timer is not None


# ── No-Color Tests ──


@pytest.mark.asyncio
async def test_no_color_sets_env(tmp_path, monkeypatch):
    """--no-color should set NO_COLOR env var before Textual init."""
    import os
    monkeypatch.delenv("NO_COLOR", raising=False)
    (tmp_path / "project.wbs.md").write_text(
        "# Test\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n",
        encoding="utf-8",
    )
    app = WBSApp(project_dir=tmp_path, no_color=True)
    assert os.environ.get("NO_COLOR") == "1"
    # Clean up
    monkeypatch.delenv("NO_COLOR", raising=False)


@pytest.mark.asyncio
async def test_no_color_false_no_env(tmp_path, monkeypatch):
    """Without --no-color, NO_COLOR should not be set by app."""
    import os
    monkeypatch.delenv("NO_COLOR", raising=False)
    (tmp_path / "project.wbs.md").write_text(
        "# Test\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n",
        encoding="utf-8",
    )
    _ = WBSApp(project_dir=tmp_path, no_color=False)
    assert os.environ.get("NO_COLOR") is None


# ── Reset Tests ──


@pytest.mark.asyncio
async def test_reset_view_clears_filters_and_sort(sample_project):
    """r key should clear filters and reset sort to defaults."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        view = app._get_active_view()
        assert view is not None
        # Add filter and custom sort
        view.filters = [FilterConfig(field="status", operator="eq", value="TODO")]
        view.sort = SortConfig(field="status", order="desc")
        app.action_reset_view()
        assert view.filters == []
        assert view.sort.field == "title"
        assert view.sort.order == "asc"
        assert app._modified is True


@pytest.mark.asyncio
async def test_reset_config_restores_defaults(sample_project):
    """R key + confirm should reset config to defaults."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Set a custom config state
        app.config.name = "My Project"
        app.config.views = [ViewConfig(name="Custom", type="table")]
        old_name = app.config.name
        app._on_reset_config_confirmed(True)
        assert app.config.name == old_name  # name preserved
        assert len(app.config.views) == 3  # default 3 views restored
        view_types = {v.type for v in app.config.views}
        assert "table" in view_types
        assert "table+gantt" in view_types
        assert "kanban" in view_types
        assert app._active_view_id == app.config.views[0].id
        assert app._modified is True


@pytest.mark.asyncio
async def test_reset_config_cancelled(sample_project):
    """R key + cancel should not change anything."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        views_before = len(app.config.views)
        app._on_reset_config_confirmed(False)
        assert len(app.config.views) == views_before


# ── Field Edit Tests ──


@pytest.mark.asyncio
async def test_apply_field_edit_title(sample_project):
    """Editing title via _apply_field_edit should update node and depends."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task11 = app.project.find_node_by_title("Task 1.1")
        assert task11 is not None
        task12 = app.project.find_node_by_title("Task 1.2")
        assert task12 is not None
        assert "Task 1.1" in task12.depends

        app._apply_field_edit(task11.id, "title", "Analysis Done")
        updated = app._node_map.get(task11.id)
        assert updated is not None
        assert updated.title == "Analysis Done"
        # Depends should be auto-updated
        updated_12 = app._node_map.get(task12.id)
        assert updated_12 is not None
        assert "Analysis Done" in updated_12.depends


@pytest.mark.asyncio
async def test_apply_field_edit_status(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "status", "DONE")
        updated = app._node_map.get(task.id)
        assert updated.status == Status.DONE


@pytest.mark.asyncio
async def test_apply_field_edit_priority(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "priority", "LOW")
        updated = app._node_map.get(task.id)
        assert updated.priority == Priority.LOW


@pytest.mark.asyncio
async def test_apply_field_edit_date(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "start", "2026-03-01")
        updated = app._node_map.get(task.id)
        from datetime import date
        assert updated.start == date(2026, 3, 1)


@pytest.mark.asyncio
async def test_apply_field_edit_invalid_date(sample_project):
    """Invalid date should not crash, should show notification."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "start", "not-a-date")
        updated = app._node_map.get(task.id)
        assert updated.start is None  # unchanged


@pytest.mark.asyncio
async def test_apply_field_edit_progress(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "progress", "50")
        updated = app._node_map.get(task.id)
        assert updated.progress == 50


@pytest.mark.asyncio
async def test_apply_field_edit_progress_invalid(sample_project):
    """Progress > 100 should be rejected."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "progress", "150")
        updated = app._node_map.get(task.id)
        assert updated.progress is None  # unchanged


@pytest.mark.asyncio
async def test_apply_field_edit_milestone(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        assert task.milestone is False
        app._apply_field_edit(task.id, "milestone", "true")
        updated = app._node_map.get(task.id)
        assert updated.milestone is True


@pytest.mark.asyncio
async def test_apply_field_edit_custom_field(sample_project):
    """Custom field edits should update custom_fields dict."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._apply_field_edit(task.id, "custom:label", "backend")
        updated = app._node_map.get(task.id)
        assert updated.custom_fields.get("label") == "backend"


@pytest.mark.asyncio
async def test_apply_field_edit_none_value_ignored(sample_project):
    """Passing None value should be a no-op."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        original_title = task.title
        app._apply_field_edit(task.id, "title", None)
        updated = app._node_map.get(task.id)
        assert updated.title == original_title


# ── NodeEditScreen Callback Tests ──


@pytest.mark.asyncio
async def test_on_node_edited_multiple_fields(sample_project):
    """_on_node_edited should apply a dict of changes."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        assert task is not None
        app._on_node_edited(task.id, {
            "assignee": "Alice",
            "duration": "10d",
        })
        updated = app._node_map.get(task.id)
        assert updated.assignee == "Alice"
        assert updated.duration == "10d"


@pytest.mark.asyncio
async def test_on_node_edited_title_updates_depends(sample_project):
    """_on_node_edited with title change should update depends."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task11 = app.project.find_node_by_title("Task 1.1")
        task12 = app.project.find_node_by_title("Task 1.2")
        assert task11 is not None
        assert "Task 1.1" in task12.depends

        app._on_node_edited(task11.id, {"title": "Req Analysis"})
        updated_12 = app._node_map.get(task12.id)
        assert "Req Analysis" in updated_12.depends
        assert "Task 1.1" not in updated_12.depends


@pytest.mark.asyncio
async def test_on_node_edited_none_is_noop(sample_project):
    """_on_node_edited with None should be a no-op."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        task = app.project.find_node_by_title("Phase 1")
        undo_len = len(app._undo_stack)
        app._on_node_edited(task.id, None)
        assert len(app._undo_stack) == undo_len  # no undo state pushed
