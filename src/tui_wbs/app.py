"""Main Textual App for TUI WBS."""

from __future__ import annotations

import os
import uuid
from dataclasses import replace
from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Static, TextArea

from tui_wbs.config import get_custom_field_ids, get_holidays, load_config, load_settings, save_config
from tui_wbs.filelock import acquire_lock, release_lock
from tui_wbs.models import (
    FilterConfig,
    Priority,
    ProjectConfig,
    SortConfig,
    Status,
    ViewConfig,
    WBSDocument,
    WBSNode,
    WBSProject,
    adjust_duration,
    days_to_duration,
    duration_to_days,
    has_incomplete_dependencies,
)
from tui_wbs.parser import parse_project
from tui_wbs.screens.confirm_screen import ConfirmScreen
from tui_wbs.screens.help_screen import HelpScreen
from tui_wbs.screens.warning_screen import WarningScreen
from tui_wbs.widgets.filter_bar import FilterBar
from tui_wbs.widgets.gantt_chart import GanttChart, GanttToolbar
from tui_wbs.widgets.kanban_board import KanbanBoard
from tui_wbs.widgets.view_tabs import ViewTabs
from tui_wbs.widgets.wbs_table import SyncedDataTable, WBSTable
from tui_wbs.commands import WBSCommandProvider
from tui_wbs import theme
from tui_wbs.writer import write_project

# Korean jamo → Latin key mapping for Korean input mode compatibility
_KOREAN_TO_LATIN: dict[str, str] = {
    "ㅁ": "a", "ㄴ": "s", "ㄷ": "d", "ㄹ": "f", "ㅎ": "g",
    "ㅗ": "h", "ㅓ": "j", "ㅏ": "k", "ㅣ": "l",
    "ㅂ": "q", "ㅈ": "w", "ㄱ": "e", "ㅅ": "r", "ㅛ": "t",
    "ㅕ": "y", "ㅑ": "u", "ㅐ": "o", "ㅔ": "p",
    "ㅋ": "z", "ㅌ": "x", "ㅊ": "c", "ㅍ": "v",
    "ㅠ": "b", "ㅜ": "n", "ㅡ": "m",
    # Shift (double consonants / compound vowels)
    "ㅃ": "Q", "ㅉ": "W", "ㄲ": "E", "ㅆ": "R",
    "ㅒ": "O", "ㅖ": "P",
}

_AUTOSAVE_DELAY = 2.0  # seconds


def _build_sample_content(name: str = "My Project") -> str:
    """Build sample WBS content with today-based start/end dates."""
    from datetime import date, timedelta

    today = date.today()

    def d(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    return f"""\
# {name}
| status | priority | start | end |
| --- | --- | --- | --- |
| IN_PROGRESS | HIGH | {d(0)} | {d(30)} |

Project overview memo.

## Phase 1: Design
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | HIGH | {d(0)} | {d(5)} |

### Task 1.1: Requirements Analysis
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | HIGH | {d(0)} | {d(2)} |

### Task 1.2: Technical Review
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | MEDIUM | {d(2)} | {d(5)} |

## Phase 2: Implementation
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | HIGH | {d(5)} | {d(25)} |

### Task 2.1: Core Development
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | HIGH | {d(5)} | {d(15)} |

### Task 2.2: Testing
| status | priority | start | end |
| --- | --- | --- | --- |
| TODO | MEDIUM | {d(15)} | {d(25)} |
"""


class WBSApp(App):
    """TUI WBS Application."""

    TITLE = "TUI WBS"
    CSS = """
    #main-content {
        height: 1fr;
        border: round $surface-lighten-2;
        border-title-align: left;
    }
    #main-content:focus-within {
        border: round $accent;
        border-title-color: $accent;
    }
    #gantt-content {
        height: 1fr;
    }
    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $primary-background;
        color: $text;
    }
    #search-bar {
        dock: bottom;
        height: 1;
        display: none;
    }
    """

    COMMANDS = App.COMMANDS | {WBSCommandProvider}

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", priority=True),
        Binding("question_mark", "help", "Help"),
        Binding("exclamation_mark", "warnings", "Warnings"),
        Binding("q", "quit_app", "Quit"),
        Binding("space", "toggle_collapse", "Fold/Unfold", show=False),
        # Panel focus (lazygit-style)
        Binding("1", "focus_tabs", "Focus Tabs", show=False),
        Binding("2", "focus_filters", "Focus Filters", show=False),
        Binding("3", "focus_content", "Focus Content", show=False),
        Binding("left_square_bracket", "prev_view", "Prev View", show=False),
        Binding("right_square_bracket", "next_view", "Next View", show=False),
        # Status cycle
        Binding("s", "cycle_status", "Cycle Status", show=False),
        # Node CRUD
        Binding("a", "add_child", "Add child", show=False),
        Binding("A", "add_sibling", "Add sibling", show=False),
        Binding("e", "edit_field", "Edit Field", show=False),
        Binding("d", "delete_node", "Delete", show=False),
        # Search
        Binding("slash", "search", "Search", show=False),
        Binding("n", "search_next", show=False),
        Binding("N", "search_prev", show=False),
        # Node movement
        Binding("K", "move_up", show=False),
        Binding("J", "move_down", show=False),
        Binding("H", "outdent", show=False),
        Binding("L", "indent", show=False),
        # Gantt scale
        Binding("D", "scale_day", show=False),
        Binding("W", "scale_week", show=False),
        Binding("M", "scale_month", show=False),
        Binding("Q", "scale_quarter", show=False),
        Binding("Y", "scale_year", show=False),
        Binding("less_than_sign", "gantt_level_down", show=False),
        Binding("greater_than_sign", "gantt_level_up", show=False),
        Binding("t", "gantt_today", show=False),
        # Kanban
        Binding("h", "kanban_left", show=False),
        Binding("l", "kanban_right", show=False),
        # Settings
        Binding("comma", "settings", "Settings", show=False),
        # Undo/Redo
        Binding("ctrl+z", "undo", "Undo", show=False, priority=True),
        Binding("ctrl+y", "redo", "Redo", show=False, priority=True),
        # Export
        Binding("ctrl+e", "export", "Export", show=False, priority=True),
        # Filter
        Binding("f", "filter_prompt", "Filter", show=False),
        # Reset
        Binding("r", "reset_view", "Reset View", show=False),
        Binding("R", "reset_config", "Reset Config", show=False),
        # Duration
        Binding("plus", "increment_duration", "Duration +1", show=False),
        Binding("minus", "decrement_duration", "Duration -1", show=False),
        # Theme
        Binding("T", "cycle_theme", "Cycle Theme", show=False),
        # Cell value increment/decrement
        Binding("alt+up", "increment_cell_value", "Increment Cell", show=False),
        Binding("alt+down", "decrement_cell_value", "Decrement Cell", show=False),
        # Column width
        Binding("ctrl+left", "shrink_column", "Shrink Column", show=False, priority=True),
        Binding("ctrl+right", "grow_column", "Grow Column", show=False, priority=True),
    ]

    def __init__(self, project_dir: Path, no_color: bool = False, demo_mode: bool = False) -> None:
        if no_color:
            os.environ["NO_COLOR"] = "1"
        super().__init__()
        self.project_dir = project_dir
        self.no_color = no_color
        self.demo_mode = demo_mode
        self.project: WBSProject | None = None
        self.config: ProjectConfig = ProjectConfig()
        self._active_view_id: str = ""
        self._modified: bool = False
        self._node_map: dict[str, WBSNode] = {}
        self._parent_map: dict[str, str] = {}  # child_id → parent_id
        self._search_query: str = ""
        self._search_matches: list[str] = []  # node IDs
        self._search_index: int = -1
        self._undo_stack: list[list[WBSDocument]] = []
        self._redo_stack: list[list[WBSDocument]] = []
        self._kanban_selected_id: str = ""
        self._autosave_timer: object | None = None
        self._settings: dict = {}
        self._scroll_syncing: bool = False
        self._holidays: list = []
        # Build latin key → action map from BINDINGS for Korean input mapping
        self._latin_to_action: dict[str, str] = {}
        for binding in self.BINDINGS:
            if isinstance(binding, Binding) and len(binding.key) == 1:
                self._latin_to_action[binding.key] = binding.action

    def on_mount(self) -> None:
        self.set_timer(0.01, self._load_project)

    def _load_project(self) -> None:
        theme.load_theme(self.project_dir, self.config.theme_name)
        self.register_theme(theme.build_textual_theme())
        if self.demo_mode:
            self._load_demo_project()
            return
        if not acquire_lock(self.project_dir):
            self.notify("Project locked by another process", severity="error")
        self.config = load_config(self.project_dir)
        custom_fields = get_custom_field_ids(self.config)
        self.project = parse_project(self.project_dir, custom_fields or None)
        self.project.config = self.config

        if not self.project.documents:
            self.push_screen(
                ConfirmScreen("No *.wbs.md files found. Create a sample file?"),
                callback=self._on_sample_confirmed,
            )
            return
        self._finish_load()

    def _load_demo_project(self) -> None:
        from tui_wbs.demo_data import get_demo_dir

        demo_dir = get_demo_dir()
        self.config = load_config(demo_dir)
        self.config.name = self.config.name or "TaskFlow App v2.0 (Demo)"
        custom_fields = get_custom_field_ids(self.config)
        self.project = parse_project(demo_dir, custom_fields or None)
        self.project.config = self.config
        self._finish_load()

    def _on_sample_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            sample_path = self.project_dir / "project.wbs.md"
            sample_path.write_text(_build_sample_content(), encoding="utf-8")
            save_config(self.project_dir, self.config)
            custom_fields = get_custom_field_ids(self.config)
            self.project = parse_project(self.project_dir, custom_fields or None)
            self.project.config = self.config
        self._finish_load()

    def _finish_load(self) -> None:
        self.config.ensure_default_view()
        if not self._active_view_id and self.config.views:
            self._active_view_id = (
                self.config.default_view
                if self.config.default_view
                else self.config.views[0].id
            )
        self._rebuild_node_map()
        self.theme = "wbs-theme"
        project_name = self.config.name or self.project_dir.name
        self.title = f"TUI WBS - {project_name}"
        # Load settings and push holidays to Gantt
        self._settings = load_settings(self.project_dir)
        self._holidays = get_holidays(self._settings)
        self._refresh_ui()

    def _rebuild_node_map(self) -> None:
        self._node_map = {}
        self._parent_map = {}
        if self.project:
            for node in self.project.all_nodes():
                self._node_map[node.id] = node

            def _walk(node: WBSNode) -> None:
                for child in node.children:
                    self._parent_map[child.id] = node.id
                    _walk(child)

            for root in self.project.all_root_nodes():
                _walk(root)

    def compose(self) -> ComposeResult:
        yield Header()
        yield ViewTabs([], "")
        yield FilterBar()
        with Horizontal(id="main-content"):
            yield WBSTable()
        yield Input(placeholder="Search...", id="search-bar")
        yield Static("", id="status-bar")
        yield Footer()

    def _get_active_view(self) -> ViewConfig | None:
        return self.config.get_view(self._active_view_id)

    # ── UI Refresh ──

    def _build_title_map(self) -> dict[str, WBSNode]:
        """Build a mapping from node title to node (first occurrence wins)."""
        title_map: dict[str, WBSNode] = {}
        if self.project:
            for node in self.project.all_nodes():
                if node.title not in title_map:
                    title_map[node.title] = node
        return title_map

    # ── Filter & Sort ──

    @staticmethod
    def _get_node_field_value(node: WBSNode, field: str) -> str:
        """Get a string value for a node field for filtering/sorting."""
        if field == "title":
            return node.title
        elif field == "status":
            return node.status.value
        elif field == "priority":
            return node.priority.value
        elif field == "assignee":
            return node.assignee
        elif field == "duration":
            return node.duration
        elif field == "start":
            return node.start.isoformat() if node.start else ""
        elif field == "end":
            return node.end.isoformat() if node.end else ""
        elif field == "milestone":
            return "true" if node.milestone else "false"
        elif field == "depends":
            return node.depends
        elif field == "memo":
            return node.memo
        else:
            return node.custom_fields.get(field, "")

    @staticmethod
    def _node_matches_filter(node: WBSNode, filt: FilterConfig) -> bool:
        """Check if a node matches a single filter condition."""
        value = WBSApp._get_node_field_value(node, filt.field).lower()
        target = filt.value.lower()
        if filt.operator == "eq":
            return value == target
        elif filt.operator == "neq":
            return value != target
        elif filt.operator == "contains":
            return target in value
        return True

    @staticmethod
    def _filter_node_tree(node: WBSNode, filters: list[FilterConfig]) -> WBSNode | None:
        """Recursively filter a node tree. Keep parent if any child matches."""
        # Filter children first
        filtered_children: list[WBSNode] = []
        for child in node.children:
            result = WBSApp._filter_node_tree(child, filters)
            if result is not None:
                filtered_children.append(result)

        # Check if this node itself matches all filters
        self_matches = all(WBSApp._node_matches_filter(node, f) for f in filters)

        if self_matches or filtered_children:
            if tuple(filtered_children) != node.children:
                return replace(node, children=tuple(filtered_children))
            return node
        return None

    @staticmethod
    def _apply_filters(root_nodes: list[WBSNode], filters: list[FilterConfig]) -> list[WBSNode]:
        """Apply filters to root nodes list."""
        if not filters:
            return root_nodes
        result: list[WBSNode] = []
        for node in root_nodes:
            filtered = WBSApp._filter_node_tree(node, filters)
            if filtered is not None:
                result.append(filtered)
        return result

    _STATUS_SORT_ORDER = {"TODO": 0, "IN_PROGRESS": 1, "DONE": 2}
    _PRIORITY_SORT_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    @staticmethod
    def _sort_key(node: WBSNode, field: str) -> tuple:
        """Generate a sort key for a node by field."""
        if field == "status":
            return (WBSApp._STATUS_SORT_ORDER.get(node.status.value, 99),)
        elif field == "priority":
            return (WBSApp._PRIORITY_SORT_ORDER.get(node.priority.value, 99),)
        else:
            return (WBSApp._get_node_field_value(node, field).lower(),)

    @staticmethod
    def _sort_node_tree(node: WBSNode, sort: SortConfig) -> WBSNode:
        """Recursively sort children at each level."""
        if not node.children:
            return node
        sorted_children = sorted(
            node.children, key=lambda n: WBSApp._sort_key(n, sort.field),
            reverse=(sort.order == "desc"),
        )
        sorted_children = tuple(
            WBSApp._sort_node_tree(c, sort) for c in sorted_children
        )
        if sorted_children != node.children:
            return replace(node, children=sorted_children)
        return node

    @staticmethod
    def _apply_sort(root_nodes: list[WBSNode], sort: SortConfig) -> list[WBSNode]:
        """Sort root nodes and their descendants."""
        sorted_roots = sorted(
            root_nodes, key=lambda n: WBSApp._sort_key(n, sort.field),
            reverse=(sort.order == "desc"),
        )
        return [WBSApp._sort_node_tree(n, sort) for n in sorted_roots]

    def _refresh_ui(self) -> None:
        try:
            tabs = self.query_one(ViewTabs)
            tabs.update_views(self.config.views, self._active_view_id)
        except Exception:
            pass

        view = self._get_active_view()

        # Update FilterBar
        try:
            filter_bar = self.query_one(FilterBar)
            filter_bar.update_filters(
                view.filters if view else [],
                view.sort if view else None,
            )
        except Exception:
            pass
        view_type = view.type if view else "table"
        root_nodes = self.project.all_root_nodes() if self.project else []

        # Apply filters and sort
        if view:
            if view.filters:
                root_nodes = self._apply_filters(root_nodes, view.filters)
            root_nodes = self._apply_sort(root_nodes, view.sort)

        title_map = self._build_title_map()

        # Show/hide widgets based on view type
        self._switch_view_widgets(view_type)

        if view_type == "kanban":
            try:
                board = self.query_one(KanbanBoard)
                board.update_data(root_nodes, view, title_map)
            except Exception:
                pass
        elif view_type == "table+gantt":
            try:
                table = self.query_one(WBSTable)
                table.update_data(root_nodes, view, title_map, date_format=self.config.date_format)
            except Exception:
                pass
            try:
                gantt = self.query_one(GanttChart)
                if hasattr(self, '_holidays'):
                    gantt.set_holidays(self._holidays)
                gantt.update_config(view)
                gantt.update_rows(table._flat_rows)
            except Exception:
                pass
            # Sync initial cursor position to Gantt and focus DataTable
            try:
                from tui_wbs.widgets.gantt_chart import GanttView

                table = self.query_one(WBSTable)
                dt = table.query_one("#wbs-data-table", SyncedDataTable)
                gantt = self.query_one(GanttChart)
                gantt_view = gantt.query_one("#gantt-view", GanttView)
                gantt_view._highlighted_row = dt.cursor_row
                gantt_view.refresh()
                dt.focus()
            except Exception:
                pass
        else:
            try:
                table = self.query_one(WBSTable)
                table.update_data(root_nodes, view, title_map, date_format=self.config.date_format)
            except Exception:
                pass

        self._update_status_bar()
        self._update_title()

        # Update main-content panel title and subtitle
        try:
            content = self.query_one("#main-content", Horizontal)
            content.border_title = {
                "table": "[3] Table",
                "table+gantt": "[3] Table + Gantt",
                "kanban": "[3] Kanban",
            }.get(view_type, "[3] Content")

            def _count_nodes(nodes: list[WBSNode]) -> int:
                total = 0
                for n in nodes:
                    total += 1
                    total += _count_nodes(list(n.children))
                return total

            total = _count_nodes(root_nodes)
            content.border_subtitle = f"{total} items"
        except Exception:
            pass

    def _switch_view_widgets(self, view_type: str) -> None:
        """Mount/unmount widgets for the active view type."""
        try:
            content = self.query_one("#main-content", Horizontal)
        except Exception:
            return

        has_table = bool(self.query(WBSTable))
        has_gantt = bool(self.query(GanttChart))
        has_kanban = bool(self.query(KanbanBoard))

        if view_type == "kanban":
            if has_table:
                self.query_one(WBSTable).remove()
            if has_gantt:
                self.query_one(GanttChart).remove()
            if not has_kanban:
                content.mount(KanbanBoard())
        elif view_type == "table+gantt":
            if has_kanban:
                self.query_one(KanbanBoard).remove()
            if not has_table:
                content.mount(WBSTable(date_format=self.config.date_format), before=0)
            if not has_gantt:
                content.mount(GanttChart())
            try:
                self.query_one(WBSTable).add_class("gantt-side")
                self.query_one("#wbs-toolbar", GanttToolbar).show_scale = True
            except Exception:
                pass
        else:  # table
            if has_kanban:
                self.query_one(KanbanBoard).remove()
            if has_gantt:
                self.query_one(GanttChart).remove()
            if not has_table:
                content.mount(WBSTable(date_format=self.config.date_format))
            try:
                self.query_one(WBSTable).remove_class("gantt-side")
                self.query_one("#wbs-toolbar", GanttToolbar).show_scale = False
            except Exception:
                pass

    def _update_status_bar(self) -> None:
        try:
            bar = self.query_one("#status-bar", Static)
        except Exception:
            return
        parts: list[str] = []
        if self.demo_mode:
            parts.append(f"[bold {theme.STATUSBAR_DEMO}]DEMO[/bold {theme.STATUSBAR_DEMO}]")
        warning_count = len(self.project.parse_warnings) if self.project else 0
        if warning_count > 0:
            parts.append(f"[{theme.STATUSBAR_WARNING}]⚠ {warning_count} warning(s)[/{theme.STATUSBAR_WARNING}]")
        if self._search_query:
            parts.append(
                f"Search: '{self._search_query}' "
                f"({self._search_index + 1}/{len(self._search_matches)})"
            )
        # Show Gantt scale when in table+gantt view
        view = self._get_active_view()
        if view and view.type == "table+gantt":
            try:
                gantt = self.query_one(GanttChart)
                parts.append(f"Scale: {gantt._scale}")
            except Exception:
                pass
        bar.update(" | ".join(parts) if parts else "")

    def on_gantt_toolbar_scale_changed(self, event: GanttToolbar.ScaleChanged) -> None:
        """Handle scale button click from the toolbar."""
        self._set_gantt_scale(event.scale)

    def on_wbstable_rows_changed(self, event: WBSTable.RowsChanged) -> None:
        """Forward table's flat rows to Gantt chart for synchronized display."""
        view = self._get_active_view()
        if view and view.type == "table+gantt":
            try:
                gantt = self.query_one(GanttChart)
                gantt.update_rows(event.flat_rows)
            except Exception:
                pass

    def on_wbstable_cursor_row_changed(self, event: WBSTable.CursorRowChanged) -> None:
        """Sync table cursor highlight to Gantt chart."""
        view = self._get_active_view()
        if view and view.type == "table+gantt":
            try:
                from tui_wbs.widgets.gantt_chart import GanttView

                gantt = self.query_one(GanttChart)
                gantt_view = gantt.query_one("#gantt-view", GanttView)
                if gantt_view._highlighted_row != event.row_index:
                    gantt_view._highlighted_row = event.row_index
                    gantt_view.refresh()
                # Sync DataTable scroll_y to GanttView
                dt = self.query_one(WBSTable).query_one("#wbs-data-table", SyncedDataTable)
                gantt_view.scroll_y = dt.scroll_y
            except Exception:
                pass

    def _reset_scroll_syncing(self) -> None:
        self._scroll_syncing = False

    def on_synced_data_table_scroll_changed(self, event: SyncedDataTable.ScrollChanged) -> None:
        """Synchronize table vertical scroll to Gantt view."""
        if self._scroll_syncing:
            return
        view = self._get_active_view()
        if view and view.type == "table+gantt":
            try:
                self._scroll_syncing = True
                from tui_wbs.widgets.gantt_chart import GanttView

                gantt = self.query_one(GanttChart)
                gantt_view = gantt.query_one("#gantt-view", GanttView)
                gantt_view.scroll_y = event.scroll_y
            except Exception:
                pass
            # Delay flag reset so bounce-back messages are caught
            self.set_timer(0.05, self._reset_scroll_syncing)

    def on_gantt_view_scroll_y_changed(self, event) -> None:
        """Synchronize Gantt view vertical scroll to table."""
        if self._scroll_syncing:
            return
        view = self._get_active_view()
        if view and view.type == "table+gantt":
            try:
                self._scroll_syncing = True
                dt = self.query_one(WBSTable).query_one("#wbs-data-table", SyncedDataTable)
                dt.scroll_y = event.scroll_y
            except Exception:
                pass
            # Delay flag reset so bounce-back messages are caught
            self.set_timer(0.05, self._reset_scroll_syncing)

    def _update_title(self) -> None:
        project_name = self.config.name or self.project_dir.name
        mod = " [*]" if self._modified else ""
        demo = " [DEMO]" if self.demo_mode else ""
        self.title = f"TUI WBS - {project_name}{mod}{demo}"

    # ── Autosave ──

    def _mark_modified(self) -> None:
        self._modified = True
        if self.demo_mode:
            self._update_title()
            return
        self._schedule_autosave()

    def _schedule_autosave(self) -> None:
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
        self._autosave_timer = self.set_timer(_AUTOSAVE_DELAY, self._do_autosave)

    def _do_autosave(self) -> None:
        self._autosave_timer = None
        if self.demo_mode:
            return
        if self._modified and self.project:
            write_project(self.project)
            save_config(self.project_dir, self.config)
            self._modified = False
            self._update_title()

    # ── Helpers for node mutation ──

    def _save_undo_state(self) -> None:
        if self.project:
            snapshot = [
                WBSDocument(
                    file_path=doc.file_path,
                    root_nodes=list(doc.root_nodes),
                    raw_content=doc.raw_content,
                    modified=doc.modified,
                    parse_warnings=list(doc.parse_warnings),
                )
                for doc in self.project.documents
            ]
            self._undo_stack.append(snapshot)
            self._redo_stack.clear()
            if len(self._undo_stack) > 50:
                self._undo_stack.pop(0)

    def _get_highlighted_node_id(self) -> str | None:
        try:
            table = self.query_one(WBSTable)
            return table.highlighted_node_id
        except Exception:
            return None

    def _update_node(self, node_id: str, **kwargs) -> None:
        """Update a node in the project tree by ID."""
        if not self.project:
            return
        self._save_undo_state()
        old_node = self._node_map.get(node_id)
        if not old_node:
            return
        new_node = replace(old_node, _meta_modified=True, **kwargs)

        for doc in self.project.documents:
            new_roots = []
            changed = False
            for root in doc.root_nodes:
                new_root = self._replace_in_tree(root, node_id, new_node)
                if new_root is not root:
                    changed = True
                new_roots.append(new_root)
            if changed:
                doc.root_nodes = new_roots
                doc.modified = True

        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()

    def _propagate_dates_to_parents(self, node_id: str) -> None:
        """Propagate start/end dates upward from node to its ancestors."""
        if not self.project:
            return
        visited: set[str] = set()
        current_id = node_id
        while current_id in self._parent_map:
            parent_id = self._parent_map[current_id]
            if parent_id in visited:
                break
            visited.add(parent_id)
            parent = self._node_map.get(parent_id)
            if not parent or not parent.children:
                break
            # Compute min start, max end from children
            min_start: date | None = None
            max_end: date | None = None
            for child in parent.children:
                if child.start is not None:
                    if min_start is None or child.start < min_start:
                        min_start = child.start
                if child.end is not None:
                    if max_end is None or child.end > max_end:
                        max_end = child.end
            # Check if parent needs updating
            changed = False
            kwargs: dict = {}
            if min_start is not None and min_start != parent.start:
                kwargs["start"] = min_start
                changed = True
            if max_end is not None and max_end != parent.end:
                kwargs["end"] = max_end
                changed = True
            if not changed:
                break
            # Apply update without triggering undo (already saved by caller)
            new_parent = replace(parent, _meta_modified=True, **kwargs)
            for doc in self.project.documents:
                new_roots = []
                doc_changed = False
                for root in doc.root_nodes:
                    new_root = self._replace_in_tree(root, parent_id, new_parent)
                    if new_root is not root:
                        doc_changed = True
                    new_roots.append(new_root)
                if doc_changed:
                    doc.root_nodes = new_roots
                    doc.modified = True
            # Rebuild both maps from the updated tree
            self._node_map = {}
            self._parent_map = {}
            for node in self.project.all_nodes():
                self._node_map[node.id] = node

            def _walk_prop(n: WBSNode) -> None:
                for c in n.children:
                    self._parent_map[c.id] = n.id
                    _walk_prop(c)

            for root in self.project.all_root_nodes():
                _walk_prop(root)
            current_id = parent_id

    def _replace_in_tree(
        self, node: WBSNode, target_id: str, replacement: WBSNode
    ) -> WBSNode:
        if node.id == target_id:
            return replacement
        new_children = tuple(
            self._replace_in_tree(c, target_id, replacement) for c in node.children
        )
        if new_children != node.children:
            return replace(node, children=new_children)
        return node

    def _add_node_to_parent(self, parent_id: str, new_node: WBSNode) -> None:
        """Add a child node to a parent."""
        if not self.project:
            return
        self._save_undo_state()
        parent = self._node_map.get(parent_id)
        if not parent:
            return
        new_parent = parent.with_child(new_node)
        for doc in self.project.documents:
            new_roots = []
            changed = False
            for root in doc.root_nodes:
                new_root = self._replace_in_tree(root, parent_id, new_parent)
                if new_root is not root:
                    changed = True
                new_roots.append(new_root)
            if changed:
                doc.root_nodes = new_roots
                doc.modified = True
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()

    def _add_sibling_node(self, sibling_id: str, new_node: WBSNode) -> None:
        """Add a sibling after the specified node."""
        if not self.project:
            return
        self._save_undo_state()
        for doc in self.project.documents:
            new_roots = self._insert_sibling_in_list(
                list(doc.root_nodes), sibling_id, new_node
            )
            if new_roots is not None:
                doc.root_nodes = new_roots
                doc.modified = True
                break
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()

    def _insert_sibling_in_list(
        self, nodes: list[WBSNode], sibling_id: str, new_node: WBSNode
    ) -> list[WBSNode] | None:
        for i, node in enumerate(nodes):
            if node.id == sibling_id:
                result = list(nodes)
                result.insert(i + 1, new_node)
                return result
            # Recurse into children
            child_list = list(node.children)
            new_children = self._insert_sibling_in_list(
                child_list, sibling_id, new_node
            )
            if new_children is not None:
                new_node_replaced = replace(node, children=tuple(new_children))
                result = list(nodes)
                result[i] = new_node_replaced
                return result
        return None

    def _delete_node_by_id(self, node_id: str) -> None:
        if not self.project:
            return
        self._save_undo_state()
        for doc in self.project.documents:
            new_roots = self._remove_from_list(list(doc.root_nodes), node_id)
            if new_roots is not None:
                doc.root_nodes = new_roots
                doc.modified = True
                break
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()

    def _remove_from_list(
        self, nodes: list[WBSNode], target_id: str
    ) -> list[WBSNode] | None:
        for i, node in enumerate(nodes):
            if node.id == target_id:
                result = list(nodes)
                result.pop(i)
                return result
            child_list = list(node.children)
            new_children = self._remove_from_list(child_list, target_id)
            if new_children is not None:
                new_node = replace(node, children=tuple(new_children))
                result = list(nodes)
                result[i] = new_node
                return result
        return None

    def _move_node_in_siblings(self, node_id: str, direction: int) -> None:
        """Move node up (-1) or down (+1) among siblings."""
        if not self.project:
            return
        self._save_undo_state()
        for doc in self.project.documents:
            if self._swap_in_list(doc.root_nodes, node_id, direction):
                doc.modified = True
                break
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()

    def _swap_in_list(
        self, nodes: list[WBSNode], target_id: str, direction: int
    ) -> bool:
        for i, node in enumerate(nodes):
            if node.id == target_id:
                j = i + direction
                if 0 <= j < len(nodes):
                    nodes[i], nodes[j] = nodes[j], nodes[i]
                    return True
                return False
            child_list = list(node.children)
            if self._swap_in_list(child_list, target_id, direction):
                nodes[nodes.index(node)] = replace(
                    node, children=tuple(child_list)
                )
                return True
        return False

    def _change_node_level(self, node_id: str, direction: int) -> None:
        """Indent (+1) or outdent (-1) a node."""
        if not self.project:
            return
        node = self._node_map.get(node_id)
        if not node:
            return
        new_level = max(1, node.level + direction)
        if new_level == node.level:
            return
        self._update_node(node_id, level=new_level)

    # ── Event handlers ──

    def on_view_tabs_view_selected(self, event: ViewTabs.ViewSelected) -> None:
        self._active_view_id = event.view_id
        self._refresh_ui()

    def on_view_tabs_add_view_requested(self, event: ViewTabs.AddViewRequested) -> None:
        """Handle + button click to create a new view."""
        from tui_wbs.screens.edit_screen import EditScreen

        self.push_screen(
            EditScreen("New View Name", "New View"),
            callback=self._on_new_view_name,
        )

    def _on_new_view_name(self, name: str | None) -> None:
        if name and name.strip():
            new_view = ViewConfig(name=name.strip(), type="table")
            self.config.views.append(new_view)
            self._active_view_id = new_view.id
            self._mark_modified()
            self._refresh_ui()

    def on_wbstable_cell_activated(self, event: WBSTable.CellActivated) -> None:
        """Handle Enter key on a table cell — cycle enum or edit."""
        node = self._node_map.get(event.node_id)
        if not node:
            return
        if event.column_id == "status":
            new_status = self._STATUS_CYCLE.get(node.status, Status.TODO)
            self._update_node(event.node_id, status=new_status)
        elif event.column_id == "priority":
            new_priority = self._PRIORITY_CYCLE.get(node.priority, Priority.MEDIUM)
            self._update_node(event.node_id, priority=new_priority)
        else:
            self._edit_node_column(event.node_id, event.column_id)

    def on_view_tabs_edit_view_requested(self, event: ViewTabs.EditViewRequested) -> None:
        self.action_filter_prompt()

    def on_filter_bar_edit_filter_requested(self, event: FilterBar.EditFilterRequested) -> None:
        self.action_filter_prompt()

    def on_filter_bar_filter_removed(self, event: FilterBar.FilterRemoved) -> None:
        """Handle × click on a filter chip."""
        view = self._get_active_view()
        if view and 0 <= event.index < len(view.filters):
            view.filters.pop(event.index)
            self._mark_modified()
            self._refresh_ui()

    def on_kanban_board_card_moved(self, event: KanbanBoard.CardMoved) -> None:
        self._update_node(event.node_id, status=event.new_status)

    def on_kanban_board_node_selected(self, event: KanbanBoard.NodeSelected) -> None:
        self._kanban_selected_id = event.node_id

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-bar":
            self._perform_search(event.value)
            event.input.display = False
            self.query_one(WBSTable).focus()

    # ── Actions ──

    def action_save(self) -> None:
        if self.demo_mode:
            self.notify("Demo mode: saving disabled", severity="warning")
            return
        if self._autosave_timer is not None:
            self._autosave_timer.stop()
            self._autosave_timer = None
        if self.project:
            write_project(self.project)
            save_config(self.project_dir, self.config)
            self._modified = False
            self._update_title()
            self.notify("Saved", severity="information")

    def action_help(self) -> None:
        self.push_screen(HelpScreen(), callback=self._on_help_action)

    def _on_help_action(self, action: str) -> None:
        if action:
            self.run_action(action)

    def action_warnings(self) -> None:
        warnings = self.project.parse_warnings if self.project else []
        self.push_screen(WarningScreen(warnings))

    def action_quit_app(self) -> None:
        if self.demo_mode:
            self.exit()
            return
        if self._modified:
            self.push_screen(
                ConfirmScreen("Unsaved changes. Quit anyway?"),
                callback=self._on_quit_confirmed,
            )
        else:
            release_lock(self.project_dir)
            self.exit()

    def _on_quit_confirmed(self, confirmed: bool) -> None:
        if confirmed:
            if not self.demo_mode:
                release_lock(self.project_dir)
            self.exit()

    def action_toggle_collapse(self) -> None:
        try:
            table = self.query_one(WBSTable)
            node_id = table.highlighted_node_id
            if node_id:
                table.toggle_collapse(node_id)
        except Exception:
            pass

    # Panel focus (lazygit-style)
    def action_focus_tabs(self) -> None:
        self.query_one(ViewTabs).focus()

    def action_focus_filters(self) -> None:
        filter_bar = self.query_one(FilterBar)
        filter_bar.focus()

    def action_focus_content(self) -> None:
        view = self._get_active_view()
        view_type = view.type if view else "table"
        if view_type == "kanban":
            try:
                self.query_one(KanbanBoard).focus()
            except Exception:
                pass
        else:
            try:
                table = self.query_one(WBSTable)
                table.query_one("#wbs-data-table").focus()
            except Exception:
                pass

    def action_prev_view(self) -> None: self._switch_to_adjacent_view(-1)
    def action_next_view(self) -> None: self._switch_to_adjacent_view(1)

    # Status cycle
    _STATUS_CYCLE = {
        Status.TODO: Status.IN_PROGRESS,
        Status.IN_PROGRESS: Status.DONE,
        Status.DONE: Status.TODO,
    }

    _PRIORITY_CYCLE = {
        Priority.HIGH: Priority.MEDIUM,
        Priority.MEDIUM: Priority.LOW,
        Priority.LOW: Priority.HIGH,
    }

    def action_cycle_status(self) -> None:
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        node = self._node_map.get(nid)
        if not node:
            return
        new_status = self._STATUS_CYCLE.get(node.status, Status.TODO)
        self._update_node(nid, status=new_status)

    # Duration increment/decrement
    def action_increment_duration(self) -> None:
        self._adjust_node_duration(1)

    def action_decrement_duration(self) -> None:
        self._adjust_node_duration(-1)

    def _adjust_node_duration(self, delta: int) -> None:
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        node = self._node_map.get(nid)
        if not node:
            return
        new_duration = adjust_duration(node.duration, delta)
        if new_duration != node.duration:
            self._update_node(nid, duration=new_duration)

    # Column width adjustment (Ctrl+Left/Right)
    def action_shrink_column(self) -> None:
        self._adjust_column_width(-2)

    def action_grow_column(self) -> None:
        self._adjust_column_width(2)

    def _adjust_column_width(self, delta: int) -> None:
        view = self._get_active_view()
        if not view:
            return
        try:
            table = self.query_one(WBSTable)
            col_id = table.highlighted_column_id
        except Exception:
            return
        if not col_id:
            return
        from tui_wbs.widgets.wbs_table import DEFAULT_COLUMN_WIDTHS
        current = view.column_widths.get(col_id, DEFAULT_COLUMN_WIDTHS.get(col_id, 12))
        new_width = max(4, current + delta)
        view.column_widths[col_id] = new_width
        self._mark_modified()
        self._refresh_ui()

    # Cell value increment/decrement (Alt+Up/Down)
    def action_increment_cell_value(self) -> None:
        self._adjust_cell_value(1)

    def action_decrement_cell_value(self) -> None:
        self._adjust_cell_value(-1)

    def _adjust_cell_value(self, delta: int) -> None:
        """Adjust the value of the focused cell by delta."""
        try:
            table = self.query_one(WBSTable)
            col_id = table.highlighted_column_id
            nid = table.highlighted_node_id
        except Exception:
            return
        if not nid or not col_id:
            return
        node = self._node_map.get(nid)
        if not node:
            return

        from datetime import timedelta

        if col_id in ("start", "end"):
            current = getattr(node, col_id, None)
            if current is not None:
                new_date = current + timedelta(days=delta)
                kwargs: dict = {col_id: new_date}
                # Auto-sync duration
                if col_id == "start" and node.end is not None:
                    diff = (node.end - new_date).days
                    if diff > 0:
                        kwargs["duration"] = days_to_duration(diff)
                elif col_id == "end" and node.start is not None:
                    diff = (new_date - node.start).days
                    if diff > 0:
                        kwargs["duration"] = days_to_duration(diff)
                self._update_node(nid, **kwargs)
                self._propagate_dates_to_parents(nid)
        elif col_id == "progress":
            current_progress = node.progress or 0
            new_val = max(0, min(100, current_progress + delta * 5))
            self._update_node(nid, progress=new_val)
        elif col_id == "duration":
            self._adjust_node_duration(delta)

    # Node CRUD
    def action_add_child(self) -> None:
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        parent = self._node_map.get(nid)
        if not parent:
            return
        new_node = WBSNode(
            title="New Task",
            level=parent.level + 1,
            source_file=parent.source_file,
            _meta_modified=True,
        )
        self._add_node_to_parent(nid, new_node)

    def action_add_sibling(self) -> None:
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        sibling = self._node_map.get(nid)
        if not sibling:
            return
        new_node = WBSNode(
            title="New Task",
            level=sibling.level,
            source_file=sibling.source_file,
            _meta_modified=True,
        )
        self._add_sibling_node(nid, new_node)

    # Editable fields and their types for the 'e' key workflow
    _EDITABLE_FIELDS: list[tuple[str, str, str]] = [
        # (field_id, display_name, editor_type)
        ("title", "Title", "text"),
        ("status", "Status", "enum"),
        ("priority", "Priority", "enum"),
        ("assignee", "Assignee", "text"),
        ("duration", "Duration", "text"),
        ("start", "Start Date", "date"),
        ("end", "End Date", "date"),
        ("depends", "Dependencies", "text"),
        ("milestone", "Milestone", "bool"),
        ("progress", "Progress", "number"),
        ("memo", "Memo", "memo"),
    ]

    def _edit_node_column(self, node_id: str, column_id: str) -> None:
        """Route editing to the correct editor based on column_id."""
        node = self._node_map.get(node_id)
        if not node:
            return

        # Check if it's a known editable field
        editable_ids = {fid for fid, _, _ in self._EDITABLE_FIELDS}
        if column_id in editable_ids:
            self._on_field_selected(node_id, column_id)
        elif column_id == "file" or column_id == "label" or column_id == "module":
            # Non-standard or non-editable columns → open full NodeEditScreen
            from tui_wbs.screens.node_edit_screen import NodeEditScreen

            self.push_screen(
                NodeEditScreen(node, custom_columns=self.config.custom_columns, focus_field=column_id),
                callback=lambda changes: self._on_node_edited(node_id, changes),
            )
        else:
            # Assume custom field
            self._on_field_selected(node_id, f"custom:{column_id}")

    def action_edit_field(self) -> None:
        """Context-aware edit: edit the focused cell's field directly."""
        focused = self.focused
        # If ViewTabs or FilterBar focused → open filter screen
        if isinstance(focused, ViewTabs) or (focused is not None and isinstance(focused.parent, ViewTabs)):
            self.action_filter_prompt()
            return
        if isinstance(focused, FilterBar) or (focused is not None and isinstance(focused.parent, FilterBar)):
            self.action_filter_prompt()
            return

        # If DataTable focused → edit the highlighted cell's column directly
        try:
            table = self.query_one(WBSTable)
            nid = table.highlighted_node_id
            col_id = table.highlighted_column_id
            if nid and col_id:
                self._edit_node_column(nid, col_id)
                return
        except Exception:
            pass

        # Fallback: old behavior with SelectScreen
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        node = self._node_map.get(nid)
        if not node:
            return

        from tui_wbs.screens.select_screen import SelectScreen

        options: list[tuple[str, str]] = [
            (fid, name) for fid, name, _ in self._EDITABLE_FIELDS
        ]
        for col in self.config.custom_columns:
            options.append((f"custom:{col.id}", col.name))

        self.push_screen(
            SelectScreen("Edit Field", options),
            callback=lambda field: self._on_field_selected(nid, field),
        )

    def _on_field_selected(self, node_id: str, field: str | None) -> None:
        if not field:
            return
        node = self._node_map.get(node_id)
        if not node:
            return

        from tui_wbs.screens.edit_screen import EditScreen
        from tui_wbs.screens.select_screen import SelectScreen

        # Determine editor type
        editor_type = "text"
        for fid, _, etype in self._EDITABLE_FIELDS:
            if fid == field:
                editor_type = etype
                break

        # Custom fields
        if field.startswith("custom:"):
            col_id = field[7:]
            for col in self.config.custom_columns:
                if col.id == col_id:
                    if col.type == "enum" and col.values:
                        opts = [(v, v) for v in col.values]
                        self.push_screen(
                            SelectScreen(f"Edit {col.name}", opts),
                            callback=lambda val, nid=node_id, cid=col_id: (
                                self._apply_field_edit(nid, f"custom:{cid}", val)
                            ),
                        )
                    else:
                        current = node.custom_fields.get(col_id, "")
                        self.push_screen(
                            EditScreen(f"Edit {col.name}", current),
                            callback=lambda val, nid=node_id, cid=col_id: (
                                self._apply_field_edit(nid, f"custom:{cid}", val)
                            ),
                        )
                    return
            return

        if editor_type == "enum":
            if field == "status":
                opts = [(s.value, s.value) for s in Status]
                initial = node.status.value
            elif field == "priority":
                opts = [(p.value, p.value) for p in Priority]
                initial = node.priority.value
            else:
                return
            self.push_screen(
                SelectScreen(f"Select {field.title()}", opts, initial_value=initial),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )
        elif editor_type == "bool":
            opts = [("true", "Yes"), ("false", "No")]
            self.push_screen(
                SelectScreen(f"Milestone?", opts),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )
        elif editor_type == "date":
            current = self._get_node_field_value(node, field)
            self.push_screen(
                EditScreen(f"Edit {field.title()}", current, placeholder="YYYY-MM-DD"),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )
        elif editor_type == "number":
            current = str(node.progress) if node.progress is not None else ""
            self.push_screen(
                EditScreen(f"Edit Progress", current, placeholder="0-100"),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )
        elif editor_type == "memo":
            self.push_screen(
                EditScreen(f"Edit Memo", node.memo, multiline=True),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )
        else:  # text
            current = self._get_node_field_value(node, field)
            self.push_screen(
                EditScreen(f"Edit {field.title()}", current),
                callback=lambda val, nid=node_id, f=field: self._apply_field_edit(nid, f, val),
            )

    def _apply_field_edit(self, node_id: str, field: str, value: str | None) -> None:
        """Validate and apply a single field edit."""
        if value is None:
            return
        node = self._node_map.get(node_id)
        if not node:
            return

        # Custom fields
        if field.startswith("custom:"):
            col_id = field[7:]
            new_custom = dict(node.custom_fields)
            new_custom[col_id] = value.strip()
            self._update_node(node_id, custom_fields=new_custom)
            return

        if field == "title":
            if value.strip():
                old_title = node.title
                self._update_node(node_id, title=value.strip())
                if old_title != value.strip():
                    self._update_depends_references(old_title, value.strip())
        elif field == "status":
            try:
                self._update_node(node_id, status=Status(value))
            except ValueError:
                self.notify(f"Invalid status: {value}", severity="error")
        elif field == "priority":
            try:
                self._update_node(node_id, priority=Priority(value))
            except ValueError:
                self.notify(f"Invalid priority: {value}", severity="error")
        elif field == "assignee":
            self._update_node(node_id, assignee=value.strip())
        elif field == "duration":
            from datetime import timedelta
            new_dur = value.strip()
            kwargs: dict = {"duration": new_dur}
            days = duration_to_days(new_dur)
            if days is not None and node.start is not None:
                kwargs["end"] = node.start + timedelta(days=days)
            self._update_node(node_id, **kwargs)
            self._propagate_dates_to_parents(node_id)
        elif field in ("start", "end"):
            from datetime import date as date_cls, timedelta
            val = value.strip()
            if not val:
                self._update_node(node_id, **{field: None})
            else:
                try:
                    parsed = date_cls.fromisoformat(val)
                    kwargs_date: dict = {field: parsed}
                    if field == "start":
                        days = duration_to_days(node.duration)
                        if days is not None:
                            kwargs_date["end"] = parsed + timedelta(days=days)
                        elif node.end is not None and not node.duration:
                            diff = (node.end - parsed).days
                            if diff > 0:
                                kwargs_date["duration"] = days_to_duration(diff)
                    elif field == "end":
                        if node.start is not None:
                            diff = (parsed - node.start).days
                            if diff > 0:
                                kwargs_date["duration"] = days_to_duration(diff)
                    self._update_node(node_id, **kwargs_date)
                    self._propagate_dates_to_parents(node_id)
                except ValueError:
                    self.notify(f"Invalid date format: {val} (use YYYY-MM-DD)", severity="error")
        elif field == "depends":
            self._update_node(node_id, depends=value.strip())
        elif field == "milestone":
            self._update_node(node_id, milestone=(value == "true"))
        elif field == "progress":
            val = value.strip()
            if not val:
                self._update_node(node_id, progress=None)
            else:
                try:
                    p = int(val)
                    if not (0 <= p <= 100):
                        raise ValueError
                    self._update_node(node_id, progress=p)
                except ValueError:
                    self.notify("Progress must be 0-100", severity="error")
        elif field == "memo":
            self._update_node(node_id, memo=value)

    def _on_node_edited(self, node_id: str, changes: dict | None) -> None:
        """Apply changes from NodeEditScreen full-form editor."""
        if not changes:
            return
        node = self._node_map.get(node_id)
        if not node:
            return

        # Extract old_title for depends auto-update
        old_title = node.title
        new_title = changes.get("title", old_title)

        # Auto-sync duration ↔ start/end
        from datetime import timedelta
        new_start = changes.get("start", node.start)
        new_end = changes.get("end", node.end)
        new_duration = changes.get("duration", node.duration)
        if "duration" in changes and new_start is not None:
            days = duration_to_days(new_duration)
            if days is not None:
                changes["end"] = new_start + timedelta(days=days)
        elif "start" in changes and new_start is not None:
            days = duration_to_days(new_duration)
            if days is not None:
                changes["end"] = new_start + timedelta(days=days)
            elif new_end is not None and not new_duration:
                diff = (new_end - new_start).days
                if diff > 0:
                    changes["duration"] = days_to_duration(diff)
        elif "end" in changes and new_end is not None and new_start is not None:
            diff = (new_end - new_start).days
            if diff > 0:
                changes["duration"] = days_to_duration(diff)

        self._update_node(node_id, **changes)

        # Propagate dates to parents if start/end changed
        if "start" in changes or "end" in changes:
            self._propagate_dates_to_parents(node_id)

        # Auto-update depends references if title changed
        if new_title != old_title:
            self._update_depends_references(old_title, new_title)

    # Reset
    def action_reset_view(self) -> None:
        """Reset current view's filters and sort to defaults."""
        view = self._get_active_view()
        if not view:
            return
        view.filters.clear()
        view.sort = SortConfig()
        self._mark_modified()
        self._refresh_ui()
        self.notify("View reset", severity="information")

    def action_reset_config(self) -> None:
        """Reset entire project config after confirmation."""
        self.push_screen(
            ConfirmScreen("Reset all views and settings to defaults?"),
            callback=self._on_reset_config_confirmed,
        )

    def _on_reset_config_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return
        old_name = self.config.name
        self.config = ProjectConfig(name=old_name)
        self.config.ensure_default_view()
        self._active_view_id = self.config.views[0].id
        self._mark_modified()
        self._refresh_ui()
        self.notify("Config reset to defaults", severity="information")

    # Init Theme
    def action_init_theme(self) -> None:
        """Copy default theme to project .tui-wbs/theme.yaml."""
        if self.demo_mode:
            self.notify("Demo mode: init-theme disabled", severity="warning")
            return
        try:
            dest = theme.init_theme(self.project_dir)
            self.notify(f"Created {dest.name}", severity="information")
        except FileExistsError:
            self.notify(".tui-wbs/theme.yaml already exists", severity="warning")

    # Date format
    def action_change_date_format(self) -> None:
        """Show date format selection dialog (deferred to let command palette dismiss)."""
        self.set_timer(0.1, self._show_date_format_screen)

    def _show_date_format_screen(self) -> None:
        from tui_wbs.models import DATE_FORMAT_PRESETS, format_date
        from tui_wbs.screens.select_screen import SelectScreen

        today = date.today()
        options = [(fmt, f"{fmt}  ({format_date(today, fmt)})") for fmt in DATE_FORMAT_PRESETS]
        self.push_screen(
            SelectScreen("Date Format", options, initial_value=self.config.date_format),
            callback=self._on_date_format_selected,
        )

    def _on_date_format_selected(self, fmt: str | None) -> None:
        if fmt and fmt != self.config.date_format:
            self.config.date_format = fmt
            self._mark_modified()
            self._refresh_ui()
            self.notify(f"Date format: {fmt}", severity="information")

    # Theme
    def action_cycle_theme(self) -> None:
        """Cycle through preset themes."""
        presets = theme.list_presets()
        if not presets:
            return
        current = self.config.theme_name
        try:
            idx = presets.index(current)
        except ValueError:
            idx = -1
        next_idx = (idx + 1) % len(presets)
        next_name = presets[next_idx]
        theme.load_theme(self.project_dir, next_name)
        self.register_theme(theme.build_textual_theme())
        self.theme = "wbs-theme"
        self.config.theme_name = next_name
        self._mark_modified()
        self._refresh_ui()
        self.notify(f"Theme: {theme.THEME_NAME}", severity="information")

    def _on_title_edited(self, node_id: str, new_title: str | None) -> None:
        if new_title is not None and new_title.strip():
            old_node = self._node_map.get(node_id)
            if old_node:
                old_title = old_node.title
                self._update_node(node_id, title=new_title.strip())
                # Auto-update depends references
                if self.project and old_title != new_title.strip():
                    self._update_depends_references(old_title, new_title.strip())

    def _update_depends_references(self, old_title: str, new_title: str) -> None:
        """Update depends fields that reference old_title."""
        if not self.project:
            return
        for node in self.project.all_nodes():
            if old_title in node.depends_list:
                new_deps = [
                    new_title if d == old_title else d for d in node.depends_list
                ]
                self._update_node(node.id, depends="; ".join(new_deps))

    def action_delete_node(self) -> None:
        nid = self._get_highlighted_node_id()
        if not nid:
            return
        node = self._node_map.get(nid)
        if not node:
            return
        child_count = len(node.all_nodes()) - 1
        msg = f"Delete '{node.title}'"
        if child_count > 0:
            msg += f" and {child_count} children"
        msg += "?"
        self.push_screen(
            ConfirmScreen(msg),
            callback=lambda confirmed: (
                self._delete_node_by_id(nid) if confirmed else None
            ),
        )

    # Search
    def action_search(self) -> None:
        try:
            search_bar = self.query_one("#search-bar", Input)
            search_bar.display = True
            search_bar.value = self._search_query
            search_bar.focus()
        except Exception:
            pass

    def _perform_search(self, query: str) -> None:
        self._search_query = query
        self._search_matches = []
        self._search_index = -1
        if not query or not self.project:
            self._update_status_bar()
            return
        q = query.lower()
        for node in self.project.all_nodes():
            if (
                q in node.title.lower()
                or q in node.memo.lower()
                or q in node.assignee.lower()
            ):
                self._search_matches.append(node.id)
        if self._search_matches:
            self._search_index = 0
            self._jump_to_search_match()
        self._update_status_bar()

    def _jump_to_search_match(self) -> None:
        if not self._search_matches or self._search_index < 0:
            return
        node_id = self._search_matches[self._search_index]
        try:
            table = self.query_one(WBSTable)
            dt = table.query_one("#wbs-data-table")
            dt.move_cursor(row=self._find_row_index(table, node_id))
        except Exception:
            pass

    def _find_row_index(self, table: WBSTable, node_id: str) -> int:
        for i, (node, _, _) in enumerate(table._flat_rows):
            if node.id == node_id:
                return i
        return 0

    def action_search_next(self) -> None:
        if self._search_matches:
            self._search_index = (self._search_index + 1) % len(self._search_matches)
            self._jump_to_search_match()
            self._update_status_bar()

    def action_search_prev(self) -> None:
        if self._search_matches:
            self._search_index = (self._search_index - 1) % len(self._search_matches)
            self._jump_to_search_match()
            self._update_status_bar()

    # Node movement
    def action_move_up(self) -> None:
        nid = self._get_highlighted_node_id()
        if nid:
            self._move_node_in_siblings(nid, -1)

    def action_move_down(self) -> None:
        nid = self._get_highlighted_node_id()
        if nid:
            self._move_node_in_siblings(nid, 1)

    def action_outdent(self) -> None:
        nid = self._get_highlighted_node_id()
        if nid:
            self._change_node_level(nid, -1)

    def action_indent(self) -> None:
        nid = self._get_highlighted_node_id()
        if nid:
            self._change_node_level(nid, 1)

    # Gantt
    def action_scale_day(self) -> None:
        self._set_gantt_scale("day")

    def action_scale_week(self) -> None:
        self._set_gantt_scale("week")

    def action_scale_month(self) -> None:
        self._set_gantt_scale("month")

    def action_scale_quarter(self) -> None:
        self._set_gantt_scale("quarter")

    def action_scale_year(self) -> None:
        self._set_gantt_scale("year")

    def _set_gantt_scale(self, scale: str) -> None:
        try:
            gantt = self.query_one(GanttChart)
            gantt.set_scale(scale)
        except Exception:
            pass
        self._sync_toolbar_scale(scale)

    def _sync_toolbar_scale(self, scale: str) -> None:
        try:
            toolbar = self.query_one("#wbs-toolbar", GanttToolbar)
            toolbar.update_toolbar(scale=scale)
        except Exception:
            pass

    def action_gantt_level_down(self) -> None:
        try:
            table = self.query_one(WBSTable)
            table.collapse_all()
        except Exception:
            pass

    def action_gantt_level_up(self) -> None:
        try:
            table = self.query_one(WBSTable)
            table.expand_all()
        except Exception:
            pass

    def action_gantt_today(self) -> None:
        try:
            gantt = self.query_one(GanttChart)
            gantt.go_to_today()
        except Exception:
            pass

    # Kanban / Gantt horizontal scroll
    _GANTT_SCROLL_STEP = 12  # default scroll step (adjusted dynamically)

    def action_kanban_left(self) -> None:
        view = self._get_active_view()
        view_type = view.type if view else "table"
        if view_type == "kanban" and self._kanban_selected_id:
            try:
                board = self.query_one(KanbanBoard)
                board.move_card(self._kanban_selected_id, -1)
            except Exception:
                pass
        elif view_type == "table+gantt":
            try:
                gantt = self.query_one(GanttChart)
                gantt.scroll_gantt(-1)
            except Exception:
                pass

    def action_kanban_right(self) -> None:
        view = self._get_active_view()
        view_type = view.type if view else "table"
        if view_type == "kanban" and self._kanban_selected_id:
            try:
                board = self.query_one(KanbanBoard)
                board.move_card(self._kanban_selected_id, 1)
            except Exception:
                pass
        elif view_type == "table+gantt":
            try:
                gantt = self.query_one(GanttChart)
                gantt.scroll_gantt(1)
            except Exception:
                pass

    # Settings
    def action_settings(self) -> None:
        from tui_wbs.widgets.settings_modal import SettingsModal

        self.push_screen(
            SettingsModal(self.config), callback=self._on_settings_saved
        )

    def _on_settings_saved(self, config: ProjectConfig | None) -> None:
        if config is not None:
            self.config = config
            self._mark_modified()
            self._refresh_ui()

    # Undo/Redo
    def action_undo(self) -> None:
        if not self._undo_stack or not self.project:
            self.notify("Nothing to undo", severity="warning")
            return
        # Save current state to redo
        current = [
            WBSDocument(
                file_path=doc.file_path,
                root_nodes=list(doc.root_nodes),
                raw_content=doc.raw_content,
                modified=doc.modified,
                parse_warnings=list(doc.parse_warnings),
            )
            for doc in self.project.documents
        ]
        self._redo_stack.append(current)
        prev = self._undo_stack.pop()
        self.project.documents = prev
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()
        self.notify("Undone", severity="information")

    def action_redo(self) -> None:
        if not self._redo_stack or not self.project:
            self.notify("Nothing to redo", severity="warning")
            return
        current = [
            WBSDocument(
                file_path=doc.file_path,
                root_nodes=list(doc.root_nodes),
                raw_content=doc.raw_content,
                modified=doc.modified,
                parse_warnings=list(doc.parse_warnings),
            )
            for doc in self.project.documents
        ]
        self._undo_stack.append(current)
        next_state = self._redo_stack.pop()
        self.project.documents = next_state
        self._mark_modified()
        self._rebuild_node_map()
        self._refresh_ui()
        self.notify("Redone", severity="information")

    # Export
    def action_export(self) -> None:
        """Show export dialog."""
        from tui_wbs.screens.edit_screen import EditScreen

        self.push_screen(
            EditScreen("Export filename (json/csv/mmd/md)", "export.json"),
            callback=self._on_export_filename,
        )

    def _on_export_filename(self, filename: str | None) -> None:
        if not filename or not self.project:
            return
        filename = filename.strip()
        base_dir = Path.cwd() if self.demo_mode else self.project_dir
        output_path = base_dir / filename
        try:
            if filename.endswith(".csv"):
                from tui_wbs.export import export_csv

                export_csv(self.project, output_path)
            elif filename.endswith(".mmd"):
                from tui_wbs.export import export_mermaid

                export_mermaid(self.project, output_path)
            elif filename.endswith(".md"):
                from tui_wbs.export import export_markdown_table

                export_markdown_table(self.project, output_path)
            else:
                from tui_wbs.export import export_json

                export_json(self.project, output_path)
            self.notify(f"Exported to {filename}", severity="information")
        except Exception as e:
            self.notify(f"Export failed: {e}", severity="error")

    # Filter prompt
    def action_filter_prompt(self) -> None:
        """Show filter input dialog."""
        from tui_wbs.screens.filter_screen import FilterScreen

        view = self._get_active_view()
        self.push_screen(
            FilterScreen(view),
            callback=self._on_filter_applied,
        )

    def _on_filter_applied(self, result: dict | None) -> None:
        if result is None:
            return
        view = self._get_active_view()
        if not view:
            return
        # Apply filter
        if "filters" in result:
            view.filters = result["filters"]
        if "sort_field" in result:
            view.sort = SortConfig(
                field=result["sort_field"],
                order=result.get("sort_order", "asc"),
            )
        self._mark_modified()
        self._refresh_ui()

    # ── Korean input mapping ──

    def on_key(self, event) -> None:
        """Map Korean jamo keys to Latin equivalents for shortcut compatibility."""
        key_char = event.character
        if not key_char:
            return
        # Skip mapping when focus is on an input widget
        focused = self.focused
        if focused and isinstance(focused, (Input, TextArea)):
            return
        latin = _KOREAN_TO_LATIN.get(key_char)
        if latin is None:
            return
        event.prevent_default()
        event.stop()
        # Number keys → panel focus (1/2/3 are in BINDINGS, handled via action lookup)
        if latin in "123":
            action = self._latin_to_action.get(latin)
            if action:
                self.run_action(action)
            return
        # Look up action from BINDINGS
        action = self._latin_to_action.get(latin)
        if action:
            self.run_action(action)

    def _switch_to_adjacent_view(self, direction: int) -> None:
        """Switch to next (+1) or previous (-1) view."""
        if not self.config.views:
            return
        current_idx = 0
        for i, v in enumerate(self.config.views):
            if v.id == self._active_view_id:
                current_idx = i
                break
        new_idx = (current_idx + direction) % len(self.config.views)
        self._active_view_id = self.config.views[new_idx].id
        self._refresh_ui()
