"""GitHub-style filter bar showing active filters as removable chips."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.containers import Container
from textual.widgets import Static

from tui_wbs.models import FilterConfig, SortConfig

_OPERATOR_DISPLAY = {
    "eq": "=",
    "neq": "!=",
    "contains": "~",
}


class FilterBar(Container):
    """GitHub-style filter bar showing active filters as removable chips.

    Always visible: shows thin empty bar with hint when no filters are active.
    """

    can_focus = True

    class FilterRemoved(Message):
        """Emitted when a filter chip's x is clicked."""

        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    class EditFilterRequested(Message):
        """Emitted when Enter is pressed on the filter bar."""

    DEFAULT_CSS = """
    FilterBar {
        height: 3;
        padding: 0 1;
        background: $surface;
        border: round $surface-lighten-2;
        border-title-align: left;
    }
    FilterBar.has-filters {
        height: auto;
        max-height: 5;
    }
    FilterBar:focus {
        border: round $accent;
        border-title-color: $accent;
    }
    FilterBar Horizontal {
        height: auto;
        max-height: 3;
    }
    FilterBar .filter-chip {
        background: $primary-darken-2;
        color: $text;
        padding: 0 1;
        margin: 0 1 0 0;
        min-width: 8;
    }
    FilterBar .filter-chip-highlighted {
        background: $accent;
        color: $text;
        padding: 0 1;
        margin: 0 1 0 0;
        min-width: 8;
    }
    FilterBar .chip-remove {
        color: $error;
        padding: 0;
        min-width: 3;
        margin: 0 1 0 0;
    }
    FilterBar .filter-bar-label {
        color: $text-muted;
        padding: 0 1 0 0;
    }
    FilterBar #filter-bar-sort {
        color: $text-muted;
        padding: 0 0 0 1;
    }
    FilterBar #filter-bar-hint {
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._filters: list[FilterConfig] = []
        self._sort: SortConfig | None = None
        self._highlighted_index: int = -1
        self._render_timer = None
        self._rendering = False

    def compose(self) -> ComposeResult:
        yield Static("[dim]No filters  (f: add)[/dim]", id="filter-bar-hint")
        yield Horizontal(id="filter-bar-container")
        yield Static("", id="filter-bar-sort")

    def on_mount(self) -> None:
        self.border_title = "[2] Filters"

    def update_filters(
        self, filters: list[FilterConfig], sort: SortConfig | None = None
    ) -> None:
        self._filters = list(filters)
        self._sort = sort
        if self._highlighted_index >= len(self._filters):
            self._highlighted_index = max(0, len(self._filters) - 1) if self._filters else -1
        count = len(self._filters)
        self.border_title = f"[2] Filters ({count})" if count else "[2] Filters"
        self._schedule_render()

    def _schedule_render(self) -> None:
        if self._render_timer is not None:
            self._render_timer.stop()
        self._render_timer = self.set_timer(0.01, self._render_chips)

    async def _render_chips(self) -> None:
        if self._rendering:
            self._schedule_render()
            return
        self._rendering = True
        try:
            try:
                container = self.query_one("#filter-bar-container", Horizontal)
                hint = self.query_one("#filter-bar-hint", Static)
                sort_widget = self.query_one("#filter-bar-sort", Static)
            except Exception:
                return
            await container.remove_children()

            # Update sort display independently
            if self._sort:
                sort_widget.update(f"Sort: {self._sort.field} {self._sort.order.upper()}")
                sort_widget.display = True
            else:
                sort_widget.update("")
                sort_widget.display = False

            has_content = bool(self._filters) or bool(self._sort)
            if has_content:
                hint.display = False
                self.add_class("has-filters")
            else:
                hint.display = True
                self.remove_class("has-filters")
                return

            # Filter chips
            if self._filters:
                widgets = [Static("Filters:", classes="filter-bar-label")]
                for i, filt in enumerate(self._filters):
                    op = _OPERATOR_DISPLAY.get(filt.operator, filt.operator)
                    chip_class = "filter-chip-highlighted" if i == self._highlighted_index else "filter-chip"
                    widgets.append(
                        Static(
                            f"{filt.field} {op} {filt.value}",
                            classes=chip_class,
                        )
                    )
                    widgets.append(
                        Static(
                            "x",
                            id=f"remove-filter-{i}",
                            classes="chip-remove",
                        )
                    )
                await container.mount(*widgets)
        finally:
            self._rendering = False

    def on_focus(self) -> None:
        if self._filters:
            self._highlighted_index = 0
            self._schedule_render()

    def on_blur(self) -> None:
        self._highlighted_index = -1
        self._schedule_render()

    def key_left(self) -> None:
        if not self._filters:
            return
        self._highlighted_index = (self._highlighted_index - 1) % len(self._filters)
        self._schedule_render()

    def key_right(self) -> None:
        if not self._filters:
            return
        self._highlighted_index = (self._highlighted_index + 1) % len(self._filters)
        self._schedule_render()

    def key_enter(self) -> None:
        self.post_message(self.EditFilterRequested())

    def key_delete(self) -> None:
        self._remove_highlighted()

    def key_backspace(self) -> None:
        self._remove_highlighted()

    def key_x(self) -> None:
        self._remove_highlighted()

    def _remove_highlighted(self) -> None:
        if 0 <= self._highlighted_index < len(self._filters):
            self.post_message(self.FilterRemoved(self._highlighted_index))

    def on_click(self, event) -> None:
        widget = event.widget
        widget_id = getattr(widget, "id", None) or ""
        if widget_id.startswith("remove-filter-"):
            idx = int(widget_id.split("-")[-1])
            self.post_message(self.FilterRemoved(idx))
