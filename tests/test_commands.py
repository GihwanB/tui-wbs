"""Tests for Command Palette provider."""

from __future__ import annotations

from pathlib import Path

import pytest

from tui_wbs.commands import COMMANDS, CommandDef, WBSCommandProvider, transliterate_korean


# ── COMMANDS list integrity ──


def test_commands_not_empty():
    assert len(COMMANDS) > 0


def test_commands_all_have_required_fields():
    for cmd in COMMANDS:
        assert isinstance(cmd, CommandDef)
        assert cmd.display, f"Missing display for action={cmd.action}"
        assert cmd.action, f"Missing action for display={cmd.display}"


def test_commands_unique_actions():
    actions = [cmd.action for cmd in COMMANDS]
    assert len(actions) == len(set(actions)), "Duplicate actions found"


def test_commands_valid_context():
    valid_contexts = {"", "table+gantt", "kanban"}
    for cmd in COMMANDS:
        assert cmd.context in valid_contexts, (
            f"Invalid context '{cmd.context}' for {cmd.display}"
        )


def test_commands_categories_present():
    categories = {cmd.category for cmd in COMMANDS}
    expected = {"File", "Edit", "View", "Search", "Navigation", "Gantt", "Kanban", "Format"}
    assert categories == expected


# ── transliterate_korean ──


def test_transliterate_korean_basic():
    assert transliterate_korean("ㅁ") == "a"
    assert transliterate_korean("ㄴ") == "s"
    assert transliterate_korean("ㅂ") == "q"


def test_transliterate_korean_passthrough():
    assert transliterate_korean("abc") == "abc"
    assert transliterate_korean("save") == "save"


def test_transliterate_korean_mixed():
    # Korean "ㅅㅁㅍㄱ" should become "ravе" → "rave"
    assert transliterate_korean("ㅅㅁㅍㄱ") == "rave"


def test_transliterate_korean_empty():
    assert transliterate_korean("") == ""


def test_transliterate_korean_shift_consonants():
    assert transliterate_korean("ㅃ") == "Q"
    assert transliterate_korean("ㅉ") == "W"
    assert transliterate_korean("ㄲ") == "E"


# ── Provider registration ──


def test_provider_registered():
    from tui_wbs.app import WBSApp

    assert WBSCommandProvider in WBSApp.COMMANDS


# ── Integration: Ctrl+P opens Command Palette ──


@pytest.fixture
def sample_project(tmp_path):
    (tmp_path / "project.wbs.md").write_text(
        "# My Project\n"
        "<!-- status: TODO -->\n"
        "\n"
        "## Task 1\n"
        "<!-- status: TODO -->\n",
        encoding="utf-8",
    )
    return tmp_path


PAUSE = 0.15


@pytest.mark.asyncio
async def test_command_palette_opens(sample_project):
    """Ctrl+P should open the command palette."""
    from tui_wbs.app import WBSApp

    app = WBSApp(project_dir=sample_project)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(delay=PAUSE)
        await pilot.press("ctrl+p")
        await pilot.pause(delay=PAUSE)
        # The command palette is pushed as a screen
        from textual.command import CommandPalette

        assert any(
            isinstance(screen, CommandPalette) for screen in app.screen_stack
        ), "Command Palette did not open"
