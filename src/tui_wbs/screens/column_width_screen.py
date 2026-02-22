"""Column width adjustment screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static, Button
from textual.binding import Binding

from tui_wbs.models import ViewConfig
from tui_wbs.widgets.wbs_table import COLUMN_LABELS, DEFAULT_COLUMN_WIDTHS


class ColumnWidthScreen(ModalScreen[dict[str, int] | None]):
    """Modal for adjusting column widths."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "confirm", "Confirm"),
        Binding("left", "shrink", "Shrink", show=False),
        Binding("right", "grow", "Grow", show=False),
        Binding("up", "prev_column", "Prev", show=False),
        Binding("down", "next_column", "Next", show=False),
        Binding("r", "reset", "Reset", show=False),
    ]

    DEFAULT_CSS = """
    ColumnWidthScreen {
        align: center middle;
    }
    #cw-container {
        width: 50;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #cw-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #cw-help {
        color: $text-muted;
        margin-top: 1;
    }
    .cw-row {
        height: 1;
        width: 1fr;
    }
    .cw-row-selected {
        background: $accent;
    }
    .cw-label {
        width: 16;
    }
    .cw-bar {
        width: 1fr;
    }
    #cw-buttons {
        height: 1;
        margin-top: 1;
        align: center middle;
    }
    """

    def __init__(self, view_config: ViewConfig) -> None:
        super().__init__()
        self._columns = list(view_config.columns)
        self._widths: dict[str, int] = {}
        for col in self._columns:
            self._widths[col] = view_config.column_widths.get(
                col, DEFAULT_COLUMN_WIDTHS.get(col, 12)
            )
        self._selected_idx = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="cw-container"):
            yield Static("Column Widths", id="cw-title")
            for i, col in enumerate(self._columns):
                label = COLUMN_LABELS.get(col, col)
                width = self._widths[col]
                bar = "█" * min(width, 30)
                classes = "cw-row cw-row-selected" if i == 0 else "cw-row"
                yield Static(
                    f" {label:<12} {width:>3}  {bar}",
                    id=f"cw-{col}",
                    classes=classes,
                )
            yield Static("↑↓ Select  ←→ Adjust  r Reset  Enter OK  Esc Cancel", id="cw-help")

    def _refresh_rows(self) -> None:
        for i, col in enumerate(self._columns):
            try:
                row = self.query_one(f"#cw-{col}", Static)
                label = COLUMN_LABELS.get(col, col)
                width = self._widths[col]
                bar = "█" * min(width, 30)
                row.update(f" {label:<12} {width:>3}  {bar}")
                if i == self._selected_idx:
                    row.add_class("cw-row-selected")
                else:
                    row.remove_class("cw-row-selected")
            except Exception:
                pass

    def action_prev_column(self) -> None:
        if self._columns:
            self._selected_idx = (self._selected_idx - 1) % len(self._columns)
            self._refresh_rows()

    def action_next_column(self) -> None:
        if self._columns:
            self._selected_idx = (self._selected_idx + 1) % len(self._columns)
            self._refresh_rows()

    def action_shrink(self) -> None:
        if self._columns:
            col = self._columns[self._selected_idx]
            self._widths[col] = max(4, self._widths[col] - 2)
            self._refresh_rows()

    def action_grow(self) -> None:
        if self._columns:
            col = self._columns[self._selected_idx]
            self._widths[col] = min(60, self._widths[col] + 2)
            self._refresh_rows()

    def action_reset(self) -> None:
        for col in self._columns:
            self._widths[col] = DEFAULT_COLUMN_WIDTHS.get(col, 12)
        self._refresh_rows()

    def action_confirm(self) -> None:
        self.dismiss(dict(self._widths))

    def action_cancel(self) -> None:
        self.dismiss(None)
