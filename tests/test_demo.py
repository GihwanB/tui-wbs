"""Tests for --demo mode."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tui_wbs.app import WBSApp
from tui_wbs.demo_data import get_demo_content
from tui_wbs.models import Status
from tui_wbs.parser import parse_markdown


PAUSE = 0.1


@pytest.fixture
def demo_app(tmp_path):
    """Create a demo-mode WBSApp."""
    return WBSApp(project_dir=tmp_path, demo_mode=True)


# ── Unit tests for demo data ──


def test_demo_content_parses_without_warnings():
    """get_demo_content() should parse cleanly with no warnings."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    assert doc.parse_warnings == [], [str(w) for w in doc.parse_warnings]


def test_demo_content_has_enough_nodes():
    """Demo data should have 25+ nodes."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    all_nodes = doc.all_nodes()
    assert len(all_nodes) >= 25


def test_demo_content_has_mixed_statuses():
    """Demo data should have all three statuses represented."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    statuses = {n.status for n in doc.all_nodes()}
    assert statuses == {Status.TODO, Status.IN_PROGRESS, Status.DONE}


def test_demo_content_has_assignees():
    """Demo data should have multiple different assignees."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    assignees = {n.assignee for n in doc.all_nodes() if n.assignee}
    assert len(assignees) >= 5


def test_demo_content_has_dates():
    """All tasks in demo data should have start/end dates."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    nodes_with_dates = [n for n in doc.all_nodes() if n.start and n.end]
    assert len(nodes_with_dates) >= 20


def test_demo_content_has_milestones():
    """Demo data should have milestone nodes."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    milestones = [n for n in doc.all_nodes() if n.milestone]
    assert len(milestones) >= 4


def test_demo_content_has_dependencies():
    """Demo data should have nodes with depends fields."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    with_deps = [n for n in doc.all_nodes() if n.depends]
    assert len(with_deps) >= 10


def test_demo_content_has_memos():
    """Demo data should have nodes with memo text."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    with_memo = [n for n in doc.all_nodes() if n.memo.strip()]
    assert len(with_memo) >= 5


def test_demo_content_has_three_level_hierarchy():
    """Demo data should have nodes at levels 1, 2, and 3."""
    content = get_demo_content()
    doc = parse_markdown(content, "demo.wbs.md")
    levels = {n.level for n in doc.all_nodes()}
    assert {1, 2, 3}.issubset(levels)


# ── Integration tests for demo app ──


@pytest.mark.asyncio
async def test_demo_app_starts_and_loads(demo_app):
    """Demo app should start and load data without errors."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert demo_app.project is not None
        assert len(demo_app.project.documents) == 1
        assert len(demo_app.project.all_nodes()) >= 25


@pytest.mark.asyncio
async def test_demo_app_title_contains_demo(demo_app):
    """Demo app title should contain [DEMO]."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert "[DEMO]" in demo_app.title


@pytest.mark.asyncio
async def test_demo_app_no_file_lock(tmp_path):
    """Demo mode should not create a file lock."""
    app = WBSApp(project_dir=tmp_path, demo_mode=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        lock_file = tmp_path / ".tui-wbs" / "lock"
        assert not lock_file.exists()


@pytest.mark.asyncio
async def test_demo_app_save_disabled(demo_app):
    """Save action in demo mode should not write files."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        demo_app.action_save()
        await pilot.pause(delay=PAUSE)
        config_path = demo_app.project_dir / ".tui-wbs" / "config.toml"
        assert not config_path.exists()


@pytest.mark.asyncio
async def test_demo_app_in_memory_editing(demo_app):
    """In-memory editing should work in demo mode."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert demo_app.project is not None
        first_node = demo_app.project.all_nodes()[0]
        original_status = first_node.status
        new_status = Status.DONE if original_status != Status.DONE else Status.TODO
        demo_app._update_node(first_node.id, status=new_status)
        updated = demo_app._node_map.get(first_node.id)
        assert updated is not None
        assert updated.status == new_status


@pytest.mark.asyncio
async def test_demo_app_no_autosave(demo_app):
    """Autosave should not be scheduled in demo mode."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert demo_app.project is not None
        first_node = demo_app.project.all_nodes()[0]
        demo_app._update_node(first_node.id, status=Status.DONE)
        assert demo_app._autosave_timer is None


@pytest.mark.asyncio
async def test_demo_app_quit_no_confirm(demo_app):
    """Quit in demo mode should not show unsaved confirmation dialog."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        # Make modifications so _modified is True
        assert demo_app.project is not None
        first_node = demo_app.project.all_nodes()[0]
        demo_app._update_node(first_node.id, status=Status.DONE)
        assert demo_app._modified is True
        # Quit should not push a ConfirmScreen
        demo_app.action_quit_app()
        from tui_wbs.screens.confirm_screen import ConfirmScreen
        assert not any(isinstance(s, ConfirmScreen) for s in demo_app.screen_stack)
