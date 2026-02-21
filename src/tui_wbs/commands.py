"""Command Palette provider for TUI WBS."""

from __future__ import annotations

from dataclasses import dataclass

from textual.command import Hit, Hits, Provider


@dataclass(frozen=True)
class CommandDef:
    """A single command entry for the palette."""

    display: str
    action: str
    help: str = ""
    category: str = ""
    context: str = ""  # "" = always, "table+gantt", "kanban"


# Korean jamo → Latin key mapping (reuse the mapping from app.py)
_KOREAN_TO_LATIN: dict[str, str] = {
    "ㅁ": "a", "ㄴ": "s", "ㄷ": "d", "ㄹ": "f", "ㅎ": "g",
    "ㅗ": "h", "ㅓ": "j", "ㅏ": "k", "ㅣ": "l",
    "ㅂ": "q", "ㅈ": "w", "ㄱ": "e", "ㅅ": "r", "ㅛ": "t",
    "ㅕ": "y", "ㅑ": "u", "ㅐ": "o", "ㅔ": "p",
    "ㅋ": "z", "ㅌ": "x", "ㅊ": "c", "ㅍ": "v",
    "ㅠ": "b", "ㅜ": "n", "ㅡ": "m",
    "ㅃ": "Q", "ㅉ": "W", "ㄲ": "E", "ㅆ": "R",
    "ㅒ": "O", "ㅖ": "P",
}

COMMANDS: list[CommandDef] = [
    # -- File --
    CommandDef("Save", "save", "Save project (Ctrl+S)", "File"),
    CommandDef("Export", "export", "Export to JSON/CSV (Ctrl+E)", "File"),
    CommandDef("Init Theme", "init_theme", "Copy default theme to project (.tui-wbs/theme.yaml)", "File"),
    CommandDef("Quit", "quit_app", "Quit application (q)", "File"),
    # -- Edit --
    CommandDef("Add Child Node", "add_child", "Add child under selected node (a)", "Edit"),
    CommandDef("Add Sibling Node", "add_sibling", "Add sibling after selected node (A)", "Edit"),
    CommandDef("Edit Field", "edit_field", "Edit a single field (e)", "Edit"),
    CommandDef("Delete Node", "delete_node", "Delete selected node (d)", "Edit"),
    CommandDef("Cycle Status", "cycle_status", "TODO → IN_PROGRESS → DONE (s)", "Edit"),
    CommandDef("Move Node Up", "move_up", "Move node up among siblings (K)", "Edit"),
    CommandDef("Move Node Down", "move_down", "Move node down among siblings (J)", "Edit"),
    CommandDef("Outdent Node", "outdent", "Decrease indent level (H)", "Edit"),
    CommandDef("Indent Node", "indent", "Increase indent level (L)", "Edit"),
    CommandDef("Undo", "undo", "Undo last change (Ctrl+Z)", "Edit"),
    CommandDef("Redo", "redo", "Redo last change (Ctrl+Y)", "Edit"),
    # -- View --
    CommandDef("Fold/Unfold", "toggle_collapse", "Toggle fold on selected node (Space)", "View"),
    CommandDef("Previous View", "prev_view", "Switch to previous view ([)", "View"),
    CommandDef("Next View", "next_view", "Switch to next view (])", "View"),
    CommandDef("Settings", "settings", "Open settings (,)", "View"),
    CommandDef("Help", "help", "Show keybindings (?)", "View"),
    CommandDef("Warnings", "warnings", "Show parse warnings (!)", "View"),
    CommandDef("Reset View", "reset_view", "Clear filters and sort (r)", "View"),
    CommandDef("Reset Config", "reset_config", "Restore default settings (R)", "View"),
    # -- Search --
    CommandDef("Search", "search", "Search nodes (/)", "Search"),
    CommandDef("Filter & Sort", "filter_prompt", "Open filter/sort dialog (f)", "Search"),
    # -- Format --
    CommandDef("Change Date Format", "change_date_format", "Switch date display format", "Format"),
    # -- Navigation --
    CommandDef("Focus: View Tabs", "focus_tabs", "Focus view tabs panel (1)", "Navigation"),
    CommandDef("Focus: Filter Bar", "focus_filters", "Focus filter bar panel (2)", "Navigation"),
    CommandDef("Focus: Content Area", "focus_content", "Focus content area (3)", "Navigation"),
    # -- Gantt (context-dependent) --
    CommandDef("Gantt: Day Scale", "scale_day", "Set gantt scale to day (D)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Week Scale", "scale_week", "Set gantt scale to week (W)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Month Scale", "scale_month", "Set gantt scale to month (M)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Quarter Scale", "scale_quarter", "Set gantt scale to quarter (Q)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Year Scale", "scale_year", "Set gantt scale to year (Y)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Level Down", "gantt_level_down", "Decrease WBS level (<)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Level Up", "gantt_level_up", "Increase WBS level (>)", "Gantt", "table+gantt"),
    CommandDef("Gantt: Go to Today", "gantt_today", "Scroll gantt to today (t)", "Gantt", "table+gantt"),
    # -- Kanban (context-dependent) --
    CommandDef("Kanban: Move Card Left", "kanban_left", "Move card to previous column (h)", "Kanban", "kanban"),
    CommandDef("Kanban: Move Card Right", "kanban_right", "Move card to next column (l)", "Kanban", "kanban"),
]


def transliterate_korean(text: str) -> str:
    """Convert Korean jamo characters to their Latin key equivalents."""
    return "".join(_KOREAN_TO_LATIN.get(ch, ch) for ch in text)


class WBSCommandProvider(Provider):
    """Textual Command Palette provider for TUI WBS actions."""

    @property
    def _current_view_type(self) -> str:
        """Get the active view type from the app."""
        try:
            view = self.app._get_active_view()  # type: ignore[attr-defined]
            return view.type if view else "table"
        except Exception:
            return "table"

    async def discover(self) -> Hits:
        """Yield all commands available in the current context."""
        view_type = self._current_view_type
        for cmd in COMMANDS:
            if cmd.context and cmd.context != view_type:
                continue
            yield Hit(
                1.0,
                cmd.display,
                self._make_callback(cmd.action),
                help=cmd.help,
            )

    async def search(self, query: str) -> Hits:
        """Search commands with fuzzy matching and Korean transliteration."""
        view_type = self._current_view_type
        # Transliterate Korean jamo in query
        latin_query = transliterate_korean(query).lower()

        for cmd in COMMANDS:
            if cmd.context and cmd.context != view_type:
                continue

            # Match against display name, help text, and category
            searchable = f"{cmd.display} {cmd.help} {cmd.category}".lower()
            latin_searchable = transliterate_korean(searchable)

            if self._fuzzy_match(latin_query, latin_searchable):
                score = self._score(latin_query, cmd.display.lower())
                yield Hit(
                    score,
                    cmd.display,
                    self._make_callback(cmd.action),
                    help=cmd.help,
                )

    def _make_callback(self, action: str):
        """Create a callback that runs the given action on the app."""
        async def callback() -> None:
            await self.app.run_action(action)
        return callback

    @staticmethod
    def _fuzzy_match(query: str, text: str) -> bool:
        """Check if all characters of query appear in order in text."""
        it = iter(text)
        return all(ch in it for ch in query)

    @staticmethod
    def _score(query: str, text: str) -> float:
        """Score a match: higher is better (closer to 1.0)."""
        if not query:
            return 0.5
        if text == query:
            return 1.0
        if text.startswith(query):
            return 0.9
        if query in text:
            return 0.8
        return 0.7
