"""Tests for data models."""

from dataclasses import replace
from datetime import date

import pytest

from tui_wbs.models import (
    DATE_FORMAT_PRESETS,
    DEFAULT_DATE_FORMAT,
    LOCK_ICON,
    MILESTONE_ICON,
    PRIORITY_ICONS,
    STATUS_ICONS,
    Priority,
    ProjectConfig,
    Status,
    ViewConfig,
    WBSDocument,
    WBSNode,
    WBSProject,
    format_date,
    has_incomplete_dependencies,
)


class TestWBSNode:
    def test_default_values(self):
        node = WBSNode(title="Test", level=1)
        assert node.title == "Test"
        assert node.level == 1
        assert node.status == Status.TODO
        assert node.priority == Priority.MEDIUM
        assert node.assignee == ""
        assert node.duration == ""
        assert node.depends == ""
        assert node.start is None
        assert node.end is None
        assert not node.milestone
        assert node.progress is None
        assert node.memo == ""
        assert node.custom_fields == {}
        assert node.children == ()
        assert node.id  # UUID auto-generated

    def test_frozen(self):
        node = WBSNode(title="Test", level=1)
        with pytest.raises(AttributeError):
            node.title = "Changed"  # type: ignore

    def test_replace(self):
        node = WBSNode(title="Test", level=1, status=Status.TODO)
        updated = replace(node, status=Status.DONE)
        assert updated.status == Status.DONE
        assert node.status == Status.TODO  # original unchanged
        assert updated.id == node.id

    def test_with_child(self):
        parent = WBSNode(title="Parent", level=1)
        child = WBSNode(title="Child", level=2)
        updated = parent.with_child(child)
        assert len(updated.children) == 1
        assert updated.children[0].title == "Child"
        assert len(parent.children) == 0  # original unchanged

    def test_all_nodes(self):
        grandchild = WBSNode(title="GC", level=3)
        child = WBSNode(title="Child", level=2, children=(grandchild,))
        root = WBSNode(title="Root", level=1, children=(child,))
        all_nodes = root.all_nodes()
        assert len(all_nodes) == 3
        assert [n.title for n in all_nodes] == ["Root", "Child", "GC"]

    def test_status_icon(self):
        for status, icon in STATUS_ICONS.items():
            node = WBSNode(title="T", level=1, status=status)
            assert node.status_icon == icon

    def test_priority_icon(self):
        for priority, icon in PRIORITY_ICONS.items():
            node = WBSNode(title="T", level=1, priority=priority)
            assert node.priority_icon == icon

    def test_display_icon_milestone(self):
        node = WBSNode(title="T", level=1, milestone=True)
        assert node.display_icon == MILESTONE_ICON

    def test_display_icon_normal(self):
        node = WBSNode(title="T", level=1, status=Status.DONE)
        assert node.display_icon == "●"

    def test_depends_list(self):
        node = WBSNode(title="T", level=1, depends="Task A; Task B")
        assert node.depends_list == ["Task A", "Task B"]

    def test_depends_list_empty(self):
        node = WBSNode(title="T", level=1, depends="")
        assert node.depends_list == []

    def test_depends_list_single(self):
        node = WBSNode(title="T", level=1, depends="Task A")
        assert node.depends_list == ["Task A"]

    def test_icons_no_overlap(self):
        """Ensure status and priority icons don't overlap."""
        status_icons = set(STATUS_ICONS.values())
        priority_icons = set(PRIORITY_ICONS.values())
        assert status_icons.isdisjoint(priority_icons), (
            f"Overlapping icons: {status_icons & priority_icons}"
        )
        assert MILESTONE_ICON not in status_icons
        assert MILESTONE_ICON not in priority_icons


class TestFormatDate:
    def test_none_returns_empty(self):
        assert format_date(None) == ""

    def test_default_format(self):
        d = date(2026, 2, 21)
        assert format_date(d) == "02-21"

    def test_each_preset(self):
        d = date(2026, 1, 5)
        assert format_date(d, "YYYY-MM-DD") == "2026-01-05"
        assert format_date(d, "MM/DD/YYYY") == "01/05/2026"
        assert format_date(d, "DD/MM/YYYY") == "05/01/2026"
        assert format_date(d, "DD.MM.YYYY") == "05.01.2026"
        assert format_date(d, "YYYY/MM/DD") == "2026/01/05"
        assert format_date(d, "MMM DD, YYYY") == "Jan 05, 2026"

    def test_invalid_format_key_falls_back_to_iso(self):
        d = date(2026, 3, 15)
        assert format_date(d, "INVALID_FORMAT") == "2026-03-15"

    def test_none_with_custom_format(self):
        assert format_date(None, "DD.MM.YYYY") == ""

    def test_presets_dict_has_default(self):
        assert DEFAULT_DATE_FORMAT in DATE_FORMAT_PRESETS


class TestHasIncompleteDependencies:
    def test_no_depends(self):
        node = WBSNode(title="A", level=1)
        assert has_incomplete_dependencies(node, {}) is False

    def test_all_deps_done(self):
        dep = WBSNode(title="Dep1", level=1, status=Status.DONE)
        node = WBSNode(title="A", level=1, depends="Dep1")
        title_map = {"Dep1": dep}
        assert has_incomplete_dependencies(node, title_map) is False

    def test_dep_not_done(self):
        dep = WBSNode(title="Dep1", level=1, status=Status.IN_PROGRESS)
        node = WBSNode(title="A", level=1, depends="Dep1")
        title_map = {"Dep1": dep}
        assert has_incomplete_dependencies(node, title_map) is True

    def test_dep_todo(self):
        dep = WBSNode(title="Dep1", level=1, status=Status.TODO)
        node = WBSNode(title="A", level=1, depends="Dep1")
        title_map = {"Dep1": dep}
        assert has_incomplete_dependencies(node, title_map) is True

    def test_dep_missing_from_map(self):
        node = WBSNode(title="A", level=1, depends="NonExistent")
        assert has_incomplete_dependencies(node, {}) is True

    def test_multiple_deps_mixed(self):
        dep1 = WBSNode(title="D1", level=1, status=Status.DONE)
        dep2 = WBSNode(title="D2", level=1, status=Status.TODO)
        node = WBSNode(title="A", level=1, depends="D1; D2")
        title_map = {"D1": dep1, "D2": dep2}
        assert has_incomplete_dependencies(node, title_map) is True

    def test_multiple_deps_all_done(self):
        dep1 = WBSNode(title="D1", level=1, status=Status.DONE)
        dep2 = WBSNode(title="D2", level=1, status=Status.DONE)
        node = WBSNode(title="A", level=1, depends="D1; D2")
        title_map = {"D1": dep1, "D2": dep2}
        assert has_incomplete_dependencies(node, title_map) is False


class TestWBSDocument:
    def test_all_nodes(self):
        child = WBSNode(title="Child", level=2)
        root = WBSNode(title="Root", level=1, children=(child,))
        doc = WBSDocument(file_path="test.md", root_nodes=[root])
        assert len(doc.all_nodes()) == 2


class TestProjectConfig:
    def test_ensure_default_view(self):
        config = ProjectConfig()
        assert len(config.views) == 0
        config.ensure_default_view()
        assert len(config.views) == 3
        assert config.views[0].name == "Table"
        assert config.views[1].name == "Gantt"
        assert config.views[2].name == "Board"
        assert config.default_view == config.views[0].id

    def test_get_view(self):
        view = ViewConfig(id="v1", name="Test")
        config = ProjectConfig(views=[view])
        assert config.get_view("v1") is view
        assert config.get_view("nonexistent") is None


class TestWBSProject:
    def test_all_nodes(self):
        node1 = WBSNode(title="N1", level=1)
        node2 = WBSNode(title="N2", level=1)
        doc1 = WBSDocument(file_path="a.md", root_nodes=[node1])
        doc2 = WBSDocument(file_path="b.md", root_nodes=[node2])
        project = WBSProject(dir_path=".", documents=[doc1, doc2])
        assert len(project.all_nodes()) == 2

    def test_find_node_by_title(self):
        node = WBSNode(title="Target", level=1)
        doc = WBSDocument(file_path="a.md", root_nodes=[node])
        project = WBSProject(dir_path=".", documents=[doc])
        assert project.find_node_by_title("Target") is node
        assert project.find_node_by_title("Missing") is None
