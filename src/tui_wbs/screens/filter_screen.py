"""Filter and sort screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from tui_wbs.models import FilterConfig, ViewConfig


FILTER_FIELDS = [
    ("status", "Status"),
    ("priority", "Priority"),
    ("assignee", "Assignee"),
    ("duration", "Duration"),
    ("milestone", "Milestone"),
    ("label", "Label"),
    ("module", "Module"),
]

FILTER_OPERATORS = [
    ("eq", "equals"),
    ("neq", "not equals"),
    ("contains", "contains"),
]

SORT_FIELDS = [
    ("title", "Title"),
    ("status", "Status"),
    ("priority", "Priority"),
    ("assignee", "Assignee"),
    ("duration", "Duration"),
    ("start", "Start"),
    ("end", "End"),
]


class FilterScreen(ModalScreen[dict | None]):
    """Modal for configuring filters and sort."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    FilterScreen {
        align: center middle;
    }
    #filter-container {
        width: 65;
        max-height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #filter-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    .filter-row {
        height: 3;
    }
    .filter-label {
        text-style: bold;
        color: $text-muted;
    }
    #filter-buttons {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    #filter-buttons Button {
        margin: 0 1;
    }
    #filter-list {
        margin-bottom: 1;
    }
    """

    def __init__(self, view: ViewConfig | None = None) -> None:
        super().__init__()
        self._view = view

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="filter-container"):
            yield Static("[bold]Filter & Sort[/bold]", id="filter-title")

            # Existing filters display
            yield Static("[dim]Active Filters:[/dim]", classes="filter-label")
            if self._view and self._view.filters:
                for i, f in enumerate(self._view.filters):
                    yield Static(f"  {f.field} {f.operator} '{f.value}'", id=f"existing-filter-{i}")
            else:
                yield Static("  (none)")

            yield Button("Clear All Filters", id="clear-filters-btn", variant="warning")

            # Add new filter
            yield Static("")
            yield Static("[dim]Add Filter:[/dim]", classes="filter-label")
            yield Select(
                [(label, fid) for fid, label in FILTER_FIELDS],
                prompt="Field",
                id="filter-field",
                allow_blank=True,
            )
            yield Select(
                [(label, op) for op, label in FILTER_OPERATORS],
                value="eq",
                id="filter-op",
                allow_blank=False,
            )
            yield Input(placeholder="Value", id="filter-value")
            yield Button("Add Filter", id="add-filter-btn", variant="primary")

            # Sort
            yield Static("")
            yield Static("[dim]Sort:[/dim]", classes="filter-label")
            current_sort_field = self._view.sort.field if self._view else "title"
            current_sort_order = self._view.sort.order if self._view else "asc"
            yield Select(
                [(label, fid) for fid, label in SORT_FIELDS],
                value=current_sort_field,
                id="sort-field",
                allow_blank=False,
            )
            yield Select(
                [("Ascending", "asc"), ("Descending", "desc")],
                value=current_sort_order,
                id="sort-order",
                allow_blank=False,
            )

            with Horizontal(id="filter-buttons"):
                yield Button("Apply", variant="primary", id="apply-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id or ""
        if btn == "apply-btn":
            self.dismiss(self._collect_result())
        elif btn == "cancel-btn":
            self.dismiss(None)
        elif btn == "clear-filters-btn":
            if self._view:
                self._view.filters.clear()
            self.dismiss(self._collect_result())
        elif btn == "add-filter-btn":
            self._add_filter()

    def _add_filter(self) -> None:
        try:
            field_sel = self.query_one("#filter-field", Select)
            op_sel = self.query_one("#filter-op", Select)
            val_inp = self.query_one("#filter-value", Input)
            if field_sel.value and val_inp.value.strip():
                new_filter = FilterConfig(
                    field=str(field_sel.value),
                    operator=str(op_sel.value) if op_sel.value else "eq",
                    value=val_inp.value.strip(),
                )
                if self._view:
                    self._view.filters.append(new_filter)
                val_inp.value = ""
                self.notify(f"Filter added: {new_filter.field} {new_filter.operator} '{new_filter.value}'")
        except Exception:
            pass

    def _collect_result(self) -> dict:
        result: dict = {}
        if self._view:
            result["filters"] = list(self._view.filters)
        try:
            sort_field = self.query_one("#sort-field", Select)
            if sort_field.value:
                result["sort_field"] = str(sort_field.value)
        except Exception:
            pass
        try:
            sort_order = self.query_one("#sort-order", Select)
            if sort_order.value:
                result["sort_order"] = str(sort_order.value)
        except Exception:
            pass
        return result

    def action_cancel(self) -> None:
        self.dismiss(None)
