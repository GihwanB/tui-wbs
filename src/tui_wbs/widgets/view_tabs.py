"""View tabs bar widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Click
from textual.message import Message
from textual.containers import Container
from textual.widgets import Static

from tui_wbs.models import ViewConfig


class ViewTabs(Container):
    """A tab bar for switching between views."""

    can_focus = True

    DEFAULT_CSS = """
    ViewTabs {
        height: 4;
        padding: 0;
        overflow: hidden;
        background: $surface-darken-1;
        border: round $surface-lighten-2;
        border-title-align: left;
    }
    ViewTabs:focus {
        border: round $accent;
        border-title-color: $accent;
    }
    ViewTabs Horizontal {
        height: 2;
    }
    ViewTabs .tab-button {
        width: auto;
        height: 2;
        min-width: 8;
        padding: 0 1;
        margin: 0;
        color: $text-muted;
        background: $surface-darken-1;
        content-align: center middle;
        text-style: none;
    }
    ViewTabs .tab-active {
        color: $text;
        background: $primary;
        text-style: bold;
    }
    ViewTabs #add-view-btn {
        width: auto;
        height: 2;
        min-width: 3;
        padding: 0 1;
        color: $text-disabled;
        background: $surface-darken-1;
    }
    """

    class ViewSelected(Message):
        """Emitted when a view tab is clicked."""

        def __init__(self, view_id: str) -> None:
            super().__init__()
            self.view_id = view_id

    class AddViewRequested(Message):
        """Emitted when the + button is clicked."""

    class EditViewRequested(Message):
        """Emitted when Enter is pressed on the view tabs."""

    def __init__(self, views: list[ViewConfig], active_id: str = "") -> None:
        super().__init__()
        self._views = views
        self._active_id = active_id
        self._render_timer = None
        self._rendering = False

    def compose(self) -> ComposeResult:
        yield Horizontal(id="view-tabs-container")

    def on_mount(self) -> None:
        self.border_title = "[1] Views"
        self._schedule_render()

    def _schedule_render(self) -> None:
        """Debounce tab rendering to avoid DuplicateIds from async remove_children."""
        if self._render_timer is not None:
            self._render_timer.stop()
        self._render_timer = self.set_timer(0.01, self._render_tabs)

    async def _render_tabs(self) -> None:
        """Render tab buttons inside the container."""
        self._render_timer = None
        if self._rendering:
            self._schedule_render()
            return
        self._rendering = True
        try:
            container = self.query_one("#view-tabs-container", Horizontal)
            await container.remove_children()
            children = []
            for i, view in enumerate(self._views):
                classes = "tab-button"
                if view.id == self._active_id:
                    classes += " tab-active"
                children.append(Static(
                    f" {view.name} ",
                    id=f"tab-{view.id}-{i}",
                    classes=classes,
                ))
            children.append(Static("+", id="add-view-btn"))
            await container.mount(*children)
        except Exception:
            pass
        finally:
            self._rendering = False

    def on_click(self, event: Click) -> None:
        widget = event.widget
        widget_id = widget.id or ""
        if widget_id == "add-view-btn":
            self.post_message(self.AddViewRequested())
        elif widget_id.startswith("tab-"):
            parts = widget_id.split("-")
            if len(parts) >= 3:
                view_id = "-".join(parts[1:-1])
                self.post_message(self.ViewSelected(view_id))

    def key_enter(self) -> None:
        self.post_message(self.EditViewRequested())

    def key_left(self) -> None:
        self._navigate(-1)

    def key_right(self) -> None:
        self._navigate(1)

    def _navigate(self, direction: int) -> None:
        if not self._views:
            return
        current_idx = next(
            (i for i, v in enumerate(self._views) if v.id == self._active_id), 0
        )
        new_idx = (current_idx + direction) % len(self._views)
        self._active_id = self._views[new_idx].id
        self.post_message(self.ViewSelected(self._active_id))

    def update_views(self, views: list[ViewConfig], active_id: str) -> None:
        """Rebuild the tab bar with new data."""
        self._views = views
        self._active_id = active_id
        self._schedule_render()
