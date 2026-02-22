"""WBS Table view widget based on DataTable."""

from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import DataTable

from rich.text import Text

from tui_wbs.models import (
    LOCK_ICON,
    MILESTONE_ICON,
    Status,
    ViewConfig,
    WBSNode,
    format_date,
    has_incomplete_dependencies,
)
from tui_wbs import theme
from tui_wbs.widgets.gantt_chart import GanttToolbar


class SyncedDataTable(DataTable):
    """DataTable subclass that emits scroll changes for synchronization."""

    class ScrollChanged(Message):
        """Emitted when vertical scroll position changes."""

        def __init__(self, scroll_y: float) -> None:
            super().__init__()
            self.scroll_y = scroll_y

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        super().watch_scroll_y(old_value, new_value)
        self.post_message(self.ScrollChanged(new_value))


_PROGRESS_BAR_WIDTH = 8


def _make_progress_cell(progress: int | None, bar_width: int = _PROGRESS_BAR_WIDTH) -> Text | str:
    if progress is None:
        return ""
    progress = max(0, min(100, progress))
    filled = max(1, round(bar_width * progress / 100)) if progress > 0 else 0
    empty = bar_width - filled

    bar_color = theme.PROGRESS_THRESHOLDS[-1][1]
    for threshold, color_str in theme.PROGRESS_THRESHOLDS:
        if progress >= threshold:
            bar_color = color_str
            break

    text = Text()
    text.append(f"{progress:>3}% ", style="bold")
    text.append("█" * filled, style=bar_color)
    text.append("░" * empty, style="dim")
    return text


COLUMN_LABELS = {
    "id": "#",
    "title": "Title",
    "status": "Status",
    "assignee": "Assignee",
    "priority": "Priority",
    "duration": "Duration",
    "start": "Start",
    "end": "End",
    "progress": "Progress",
    "depends": "Depends",
    "milestone": "MS",
    "memo": "Memo",
    "file": "File",
    "label": "Label",
    "module": "Module",
}

DEFAULT_COLUMN_WIDTHS: dict[str, int] = {
    "id": 6,
    "title": 30,
    "status": 14,
    "assignee": 12,
    "priority": 12,
    "duration": 10,
    "start": 12,
    "end": 12,
    "progress": 16,
    "depends": 14,
    "milestone": 4,
    "memo": 20,
    "file": 16,
    "label": 14,
    "module": 12,
}


class WBSTable(Container):
    """Table view for WBS nodes with tree indentation."""

    DEFAULT_CSS = """
    WBSTable {
        width: 1fr;
        height: 1fr;
    }
    WBSTable #wbs-toolbar {
        height: 1;
    }
    WBSTable.gantt-side {
        width: auto;
    }
    WBSTable.gantt-side SyncedDataTable {
        width: auto;
        margin-top: 1;
    }
    WBSTable SyncedDataTable {
        height: 1fr;
    }
    """

    class NodeSelected(Message):
        """Emitted when a node is selected."""

        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    class CellActivated(Message):
        """Emitted when Enter is pressed on a cell."""

        def __init__(self, node_id: str, column_id: str) -> None:
            super().__init__()
            self.node_id = node_id
            self.column_id = column_id

    class CursorRowChanged(Message):
        """Emitted when the cursor row changes (for Gantt highlight sync)."""

        def __init__(self, row_index: int, node_id: str) -> None:
            super().__init__()
            self.row_index = row_index
            self.node_id = node_id

    class RowsChanged(Message):
        """Emitted when the flat row list changes (rebuild, collapse/expand)."""

        def __init__(self, flat_rows: list[tuple[WBSNode, int, str]]) -> None:
            super().__init__()
            self.flat_rows = flat_rows

    def __init__(self, nodes: list[WBSNode] | None = None, view_config: ViewConfig | None = None, title_map: dict[str, WBSNode] | None = None, date_format: str = "YYYY-MM-DD") -> None:
        super().__init__()
        self._wbs_nodes = nodes or []
        self._view_config = view_config or ViewConfig()
        self._title_map: dict[str, WBSNode] = title_map or {}
        self._date_format = date_format
        self._flat_rows: list[tuple[WBSNode, int, str]] = []
        self._collapsed: set[str] = set()

    def compose(self) -> ComposeResult:
        yield GanttToolbar(show_scale=False, id="wbs-toolbar")
        yield SyncedDataTable(id="wbs-data-table", cursor_type="cell")

    def on_mount(self) -> None:
        try:
            table = self.query_one("#wbs-data-table", SyncedDataTable)
            table.zebra_stripes = True
        except Exception:
            pass
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        """Rebuild the DataTable from nodes."""
        try:
            table = self.query_one("#wbs-data-table", SyncedDataTable)
        except Exception:
            return

        # Save cursor position before rebuild
        saved_node_id = self.highlighted_node_id
        saved_col_id = self.highlighted_column_id

        table.clear(columns=True)

        columns = self._view_config.columns
        custom_widths = self._view_config.column_widths
        for col_id in columns:
            label = COLUMN_LABELS.get(col_id, col_id)
            width = custom_widths.get(col_id, DEFAULT_COLUMN_WIDTHS.get(col_id))
            table.add_column(label, key=col_id, width=width)

        self._flat_rows = []
        for idx, node in enumerate(self._wbs_nodes, start=1):
            self._flatten_node(node, 0, str(idx))

        for node, depth, hier_id in self._flat_rows:
            row_data = self._make_row(node, depth, hier_id)
            table.add_row(*row_data, key=node.id)

        # Restore cursor position after rebuild
        if saved_node_id:
            for row_idx, (node, _, _) in enumerate(self._flat_rows):
                if node.id == saved_node_id:
                    col_idx = 0
                    if saved_col_id:
                        try:
                            col_idx = columns.index(saved_col_id)
                        except ValueError:
                            pass
                    table.move_cursor(row=row_idx, column=col_idx, animate=False)
                    break

        self.post_message(self.RowsChanged(list(self._flat_rows)))

    def _flatten_node(self, node: WBSNode, depth: int, prefix: str = "") -> None:
        self._flat_rows.append((node, depth, prefix))
        if node.id not in self._collapsed:
            for idx, child in enumerate(node.children, start=1):
                self._flatten_node(child, depth + 1, f"{prefix}.{idx}")

    def _make_row(self, node: WBSNode, depth: int, hier_id: str = "") -> list[str]:
        columns = self._view_config.columns
        row: list[str] = []

        for col_id in columns:
            if col_id == "id":
                row.append(hier_id)
            elif col_id == "title":
                indent = "  " * depth
                if node.children:
                    fold_icon = "▶ " if node.id in self._collapsed else "▼ "
                else:
                    fold_icon = "  "
                icon = node.display_icon
                lock = ""
                if node.depends_list and has_incomplete_dependencies(node, self._title_map):
                    lock = f" {LOCK_ICON}"
                prefix = f"{indent}{fold_icon}{icon} "
                title_text = Text()
                title_text.append(prefix)
                title_start = len(title_text)
                title_text.append(node.title)
                title_end = len(title_text)
                if lock:
                    title_text.append(lock)
                # Highlight overdue TODO nodes in red bold
                if (
                    node.status == Status.TODO
                    and node.start is not None
                    and node.start <= date.today()
                ):
                    title_text.stylize(f"{theme.OVERDUE_TITLE} bold", title_start, title_end)
                row.append(title_text)
            elif col_id == "status":
                color = theme.STATUS_COLORS.get(node.status, theme.STATUS_COLORS[Status.TODO])
                text = Text(f"{node.status_icon} {node.status.value}")
                text.stylize(color)
                row.append(text)
            elif col_id == "assignee":
                row.append(node.assignee)
            elif col_id == "priority":
                from tui_wbs.models import Priority
                color = theme.PRIORITY_COLORS.get(node.priority, theme.PRIORITY_COLORS[Priority.MEDIUM])
                text = Text(f"{node.priority_icon} {node.priority.value}")
                text.stylize(color)
                row.append(text)
            elif col_id == "duration":
                row.append(node.duration)
            elif col_id == "start":
                row.append(format_date(node.start, self._date_format))
            elif col_id == "end":
                row.append(format_date(node.end, self._date_format))
            elif col_id == "progress":
                row.append(_make_progress_cell(node.progress))
            elif col_id == "depends":
                row.append(node.depends)
            elif col_id == "milestone":
                row.append(MILESTONE_ICON if node.milestone else "")
            elif col_id == "memo":
                row.append(node.memo.replace("\n", " ")[:40])
            elif col_id == "file":
                row.append(node.source_file)
            elif col_id == "label":
                raw = node.custom_fields.get("label", "")
                if raw.strip():
                    tags = [t.strip() for t in raw.split(",") if t.strip()]
                    label_text = Text()
                    for i, tag in enumerate(tags):
                        if i > 0:
                            label_text.append(" ")
                        start = len(label_text)
                        label_text.append(f"[{tag}]")
                        label_text.stylize("dim", start, start + 1)
                        label_text.stylize("bold", start + 1, start + 1 + len(tag))
                        label_text.stylize("dim", start + 1 + len(tag), start + 2 + len(tag))
                    row.append(label_text)
                else:
                    row.append("")
            else:
                row.append(node.custom_fields.get(col_id, ""))

        return row

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        if event.coordinate is not None:
            row_key = event.cell_key.row_key
            col_key = event.cell_key.column_key
            if row_key and row_key.value:
                node_id = str(row_key.value)
                column_id = str(col_key.value) if col_key and col_key.value else ""
                self.post_message(self.NodeSelected(node_id))
                self.post_message(self.CellActivated(node_id, column_id))

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        row_key = event.cell_key.row_key
        if row_key and row_key.value:
            node_id = str(row_key.value)
            self.post_message(self.NodeSelected(node_id))
            row_index = event.coordinate.row
            self.post_message(self.CursorRowChanged(row_index, node_id))

    def toggle_collapse(self, node_id: str) -> None:
        if node_id in self._collapsed:
            self._collapsed.discard(node_id)
        else:
            self._collapsed.add(node_id)
        self._rebuild_table()

    def update_data(self, nodes: list[WBSNode], view_config: ViewConfig | None = None, title_map: dict[str, WBSNode] | None = None, date_format: str | None = None) -> None:
        self._wbs_nodes = nodes
        if view_config:
            self._view_config = view_config
        if title_map is not None:
            self._title_map = title_map
        if date_format is not None:
            self._date_format = date_format
        self._rebuild_table()

    def collapse_all(self) -> None:
        """Collapse all nodes that have children."""
        for node, _, _ in self._flat_rows:
            if node.children:
                self._collapsed.add(node.id)
        self._rebuild_table()

    def expand_all(self) -> None:
        """Expand all collapsed nodes."""
        self._collapsed.clear()
        self._rebuild_table()

    @property
    def highlighted_node_id(self) -> str | None:
        try:
            table = self.query_one("#wbs-data-table", SyncedDataTable)
        except Exception:
            return None
        if table.cursor_row is not None and table.cursor_row < len(self._flat_rows):
            node, _, _ = self._flat_rows[table.cursor_row]
            return node.id
        return None

    @property
    def highlighted_column_id(self) -> str | None:
        try:
            table = self.query_one("#wbs-data-table", SyncedDataTable)
        except Exception:
            return None
        columns = self._view_config.columns
        col_idx = table.cursor_column
        if col_idx is not None and 0 <= col_idx < len(columns):
            return columns[col_idx]
        return None
