"""Tests for --demo mode."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tui_wbs.app import WBSApp
from tui_wbs.demo_data import (
    _extract_anchor,
    _shift_dates_in_content,
    get_demo_dir,
)
from tui_wbs.models import Status
from tui_wbs.parser import parse_file


PAUSE = 0.1


@pytest.fixture
def demo_app():
    """Create a demo-mode WBSApp using the bundled demo directory."""
    demo_dir = get_demo_dir()
    return WBSApp(project_dir=demo_dir, demo_mode=True)


# ── Unit tests for demo data (file-based) ──


def test_demo_file_parses_without_warnings():
    """demo.wbs.md should parse cleanly with no warnings."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    assert doc.parse_warnings == [], [str(w) for w in doc.parse_warnings]


def test_demo_file_has_enough_nodes():
    """Demo data should have 25+ nodes."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    all_nodes = doc.all_nodes()
    assert len(all_nodes) >= 25


def test_demo_file_has_mixed_statuses():
    """Demo data should have all three statuses represented."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    statuses = {n.status for n in doc.all_nodes()}
    assert statuses == {Status.TODO, Status.IN_PROGRESS, Status.DONE}


def test_demo_file_has_assignees():
    """Demo data should have multiple different assignees."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    assignees = {n.assignee for n in doc.all_nodes() if n.assignee}
    assert len(assignees) >= 5


def test_demo_file_has_dates():
    """All tasks in demo data should have start/end dates."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    nodes_with_dates = [n for n in doc.all_nodes() if n.start and n.end]
    assert len(nodes_with_dates) >= 20


def test_demo_file_has_milestones():
    """Demo data should have milestone nodes."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    milestones = [n for n in doc.all_nodes() if n.milestone]
    assert len(milestones) >= 4


def test_demo_file_has_dependencies():
    """Demo data should have nodes with depends fields."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    with_deps = [n for n in doc.all_nodes() if n.depends]
    assert len(with_deps) >= 10


def test_demo_file_has_memos():
    """Demo data should have nodes with memo text."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    with_memo = [n for n in doc.all_nodes() if n.memo.strip()]
    assert len(with_memo) >= 5


def test_demo_file_has_three_level_hierarchy():
    """Demo data should have nodes at levels 1, 2, and 3."""
    doc = parse_file(get_demo_dir() / "demo.wbs.md")
    levels = {n.level for n in doc.all_nodes()}
    assert {1, 2, 3}.issubset(levels)


def test_demo_file_has_anchor():
    """demo.wbs.md should have a demo-anchor comment."""
    content = (get_demo_dir() / "demo.wbs.md").read_text(encoding="utf-8")
    anchor = _extract_anchor(content)
    assert anchor is not None


def test_demo_config_exists():
    """Demo project should have a config.toml."""
    config_path = get_demo_dir() / ".tui-wbs" / "config.toml"
    assert config_path.exists()


# ── Date shifting utility tests ──


def test_extract_anchor():
    """_extract_anchor should parse the anchor date."""
    content = "<!-- demo-anchor: 2026-01-15 -->\n# Title"
    assert _extract_anchor(content) == date(2026, 1, 15)


def test_extract_anchor_missing():
    """_extract_anchor should return None when no anchor."""
    assert _extract_anchor("# Title\nSome content") is None


def test_shift_dates_zero_delta():
    """Zero delta should return content unchanged."""
    content = "start: 2026-01-15 | end: 2026-02-01"
    result = _shift_dates_in_content(content, timedelta(days=0))
    assert result == content


def test_shift_dates_positive():
    """Positive delta should shift dates forward."""
    content = "<!-- demo-anchor: 2026-01-10 -->\nstart: 2026-01-10 | end: 2026-01-20"
    result = _shift_dates_in_content(content, timedelta(days=5))
    assert "2026-01-15" in result
    assert "2026-01-25" in result
    assert "2026-01-10" not in result


def test_shift_dates_negative():
    """Negative delta should shift dates backward."""
    content = "<!-- demo-anchor: 2026-03-10 -->\nstart: 2026-03-10 | end: 2026-03-20"
    result = _shift_dates_in_content(content, timedelta(days=-5))
    assert "2026-03-05" in result
    assert "2026-03-15" in result


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
async def test_demo_app_no_file_lock(demo_app):
    """Demo mode should not create a file lock."""
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        lock_file = get_demo_dir() / ".tui-wbs" / "lock"
        assert not lock_file.exists()


@pytest.mark.asyncio
async def test_demo_app_save_disabled(demo_app):
    """Save action in demo mode should not modify files."""
    config_path = get_demo_dir() / ".tui-wbs" / "config.toml"
    original_content = config_path.read_text(encoding="utf-8")
    async with demo_app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        demo_app.action_save()
        await pilot.pause(delay=PAUSE)
        assert config_path.read_text(encoding="utf-8") == original_content


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
