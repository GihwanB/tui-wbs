"""Help modal screen showing keybindings."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


HELP_ITEMS: list[tuple[str, str, str]] = [
    # (key_display, description, action_name_or_empty)
    # -- Common --
    ("↑ / k", "Previous item", ""),
    ("↓ / j", "Next item", ""),
    ("Enter", "Cycle status/priority, or edit field", ""),
    ("Esc", "Cancel / Close modal", ""),
    ("Space", "Fold/unfold toggle", "toggle_collapse"),
    ("Ctrl+S", "Save", "save"),
    ("?", "This help", ""),
    ("!", "Parse warnings", "warnings"),
    (",", "Settings", "settings"),
    ("q", "Quit", "quit_app"),
    # -- CRUD --
    ("a", "Add child node", "add_child"),
    ("A", "Add sibling node", "add_sibling"),
    ("e", "Edit single field", "edit_field"),
    ("d", "Delete node", "delete_node"),
    ("s", "Cycle status (TODO→IN_PROGRESS→DONE)", "cycle_status"),
    ("+ / -", "Increase / decrease duration", ""),
    ("Alt+↑/↓", "Increment / decrement cell value", ""),
    ("Ctrl+←/→", "Shrink / grow column width", ""),
    # -- Search --
    ("/", "Search", "search"),
    ("n / N", "Next / Previous match", ""),
    # -- Movement --
    ("K / J", "Move node up / down", ""),
    ("H / L", "Outdent / Indent node", ""),
    # -- Gantt --
    ("D/W/M/Q/Y", "Gantt scale", ""),
    ("< / >", "WBS level -/+", ""),
    ("t", "Go to today", "gantt_today"),
    # -- Kanban --
    ("h / l", "Kanban: move card / Gantt: scroll", ""),
    # -- Undo --
    ("Ctrl+Z", "Undo", "undo"),
    ("Ctrl+Y", "Redo", "redo"),
    # -- Export & Filter --
    ("Ctrl+E", "Export (JSON/CSV)", "export"),
    ("f", "Filter & Sort", "filter_prompt"),
    # -- Panel focus --
    ("1", "Focus: View Tabs", "focus_tabs"),
    ("2", "Focus: Filter Bar", "focus_filters"),
    ("3", "Focus: Content Area", "focus_content"),
    ("[ / ]", "Previous / Next view", ""),
    # -- Reset & Theme --
    ("r", "Reset view (clear filters/sort)", "reset_view"),
    ("R", "Reset config (restore defaults)", "reset_config"),
    ("T", "Toggle theme (dark/light)", "toggle_theme"),
    # -- Format --
    ("Cmd Palette", "Change date format", "change_date_format"),
    # -- CLI --
    ("--demo", "Launch demo mode (tui-wbs --demo)", ""),
    # -- Cmd Palette --
    ("Cmd Palette", "Init theme (copy default to project)", "init_theme"),
]


class HelpScreen(ModalScreen[str]):
    """Modal screen showing keybindings as a selectable list."""

    BINDINGS = [
        ("escape", "close", "Close"),
        ("question_mark", "close", "Close"),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-container {
        width: 80;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #help-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #help-list {
        height: auto;
        max-height: 100%;
    }
    #help-list > .option-list--option-highlighted {
        background: $accent;
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-container"):
            yield Static(
                "[bold]Keybindings[/bold]  (Enter to execute)", id="help-title"
            )
            ol = OptionList(id="help-list")
            for key_display, desc, action in HELP_ITEMS:
                label = f"  {key_display:<16} {desc}"
                ol.add_option(Option(label, id=action if action else None))
            yield ol

    def on_mount(self) -> None:
        self.set_timer(0.01, self._focus_list)

    def _focus_list(self) -> None:
        self.query_one("#help-list", OptionList).focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        action = event.option.id
        if action:
            self.dismiss(action)
        else:
            self.dismiss("")

    def action_close(self) -> None:
        self.dismiss("")
