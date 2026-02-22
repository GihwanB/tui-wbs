"""Integration tests for the TUI app using Textual Pilot."""

from pathlib import Path

import pytest

from tui_wbs.app import WBSApp


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
def named_project(tmp_path):
    """Create a project with a config name."""
    cfg_dir = tmp_path / ".tui-wbs"
    cfg_dir.mkdir()
    (cfg_dir / "config.toml").write_text(
        '[project]\nname = "My Project"\n', encoding="utf-8"
    )
    (tmp_path / "overview.wbs.md").write_text(
        "# Root\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.asyncio
async def test_app_starts(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        assert len(app.project.documents) == 1


@pytest.mark.asyncio
async def test_app_title_from_config(named_project):
    app = WBSApp(project_dir=named_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert "My Project" in app.title


@pytest.mark.asyncio
async def test_app_help_modal(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_help()
        from tui_wbs.screens.help_screen import HelpScreen
        assert any(isinstance(s, HelpScreen) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_app_warning_modal(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_warnings()
        from tui_wbs.screens.warning_screen import WarningScreen
        assert any(isinstance(s, WarningScreen) for s in app.screen_stack)


@pytest.mark.asyncio
async def test_app_empty_project_confirm_yes(tmp_path):
    app = WBSApp(project_dir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.screens.confirm_screen import ConfirmScreen
        confirm = None
        for s in app.screen_stack:
            if isinstance(s, ConfirmScreen):
                confirm = s
                break
        assert confirm is not None
        confirm.dismiss(True)
        await pilot.pause(delay=PAUSE)
        assert (tmp_path / "project.wbs.md").exists()
        assert app.project is not None
        assert len(app.project.documents) == 1


@pytest.mark.asyncio
async def test_app_empty_project_confirm_no(tmp_path):
    app = WBSApp(project_dir=tmp_path)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        from tui_wbs.screens.confirm_screen import ConfirmScreen
        for s in app.screen_stack:
            if isinstance(s, ConfirmScreen):
                s.dismiss(False)
                break
        await pilot.pause(delay=PAUSE)
        assert not (tmp_path / "project.wbs.md").exists()
        assert app.project is not None
        assert len(app.project.documents) == 0


@pytest.mark.asyncio
async def test_app_save(sample_project):
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app.action_save()
        config_path = sample_project / ".tui-wbs" / "config.toml"
        assert config_path.exists()
        assert app._modified is False


@pytest.mark.asyncio
async def test_app_node_update(sample_project):
    """Test node update via _update_node."""
    from tui_wbs.models import Status
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        first_node = app.project.all_nodes()[0]
        app._update_node(first_node.id, status=Status.DONE)
        updated = app._node_map.get(first_node.id)
        assert updated is not None
        assert updated.status == Status.DONE
        assert app._modified is True


@pytest.mark.asyncio
async def test_app_undo_redo(sample_project):
    """Test undo/redo functionality."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        assert app.project is not None
        nodes_before = len(app.project.all_nodes())
        # Add a child node
        first_node = app.project.all_nodes()[0]
        app._update_node(first_node.id, status=app.project.all_nodes()[0].status)
        assert len(app._undo_stack) >= 1
        # Undo
        app.action_undo()
        assert len(app._redo_stack) >= 1


@pytest.mark.asyncio
async def test_app_quit_unsaved(sample_project):
    """Test quit with unsaved changes shows confirmation."""
    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        app._modified = True
        app.action_quit_app()
        from tui_wbs.screens.confirm_screen import ConfirmScreen
        assert any(isinstance(s, ConfirmScreen) for s in app.screen_stack)
