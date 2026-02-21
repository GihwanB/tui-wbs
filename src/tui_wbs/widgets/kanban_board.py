"""Kanban board custom widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from tui_wbs.models import LOCK_ICON, Status, WBSNode, ViewConfig, has_incomplete_dependencies
from tui_wbs import theme


class KanbanCard(Static):
    """A single card on the Kanban board."""

    DEFAULT_CSS = """
    KanbanCard {
        width: 100%;
        height: auto;
        margin: 0 0 1 0;
        padding: 0 1;
        border: solid $primary;
    }
    KanbanCard.card-selected {
        border: heavy $accent;
    }
    KanbanCard.card-milestone {
        border: solid magenta;
    }
    """

    def __init__(self, node: WBSNode, title_map: dict[str, WBSNode] | None = None, **kwargs) -> None:
        lock_prefix = ""
        if title_map and node.depends_list and has_incomplete_dependencies(node, title_map):
            lock_prefix = f"{LOCK_ICON} "
        label = f"{lock_prefix}{node.priority_icon} {node.title}"
        if node.assignee:
            label += f"\n  [dim]{node.assignee}[/dim]"
        if node.milestone:
            label += f"\n  [{theme.MILESTONE.dark}]◇ Milestone[/{theme.MILESTONE.dark}]"
        classes = kwargs.pop("classes", "")
        if node.milestone:
            classes = f"{classes} card-milestone".strip()
        super().__init__(label, classes=classes, **kwargs)
        self.node_id = node.id


class KanbanColumn(Container):
    """A single column in the Kanban board."""

    DEFAULT_CSS = """
    KanbanColumn {
        width: 1fr;
        height: 1fr;
        border-right: solid $primary;
        padding: 0 1;
    }
    KanbanColumn #col-header {
        text-align: center;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, cards: list[WBSNode], title_map: dict[str, WBSNode] | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._cards = cards
        self._title_map = title_map or {}

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]{self._title}[/bold] ({len(self._cards)})", id="col-header"
        )
        with VerticalScroll():
            for node in self._cards:
                yield KanbanCard(node, title_map=self._title_map, id=f"card-{node.id}")


class KanbanBoard(Container):
    """Kanban board widget with columns for each status."""

    DEFAULT_CSS = """
    KanbanBoard {
        height: 1fr;
    }
    KanbanBoard #kanban-columns {
        height: 1fr;
    }
    """

    class NodeSelected(Message):
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    class CardMoved(Message):
        """Emitted when a card is moved to a new status."""

        def __init__(self, node_id: str, new_status: Status) -> None:
            super().__init__()
            self.node_id = node_id
            self.new_status = new_status

    def __init__(self) -> None:
        super().__init__()
        self._wbs_nodes: list[WBSNode] = []
        self._view_config: ViewConfig = ViewConfig()
        self._title_map: dict[str, WBSNode] = {}
        self._group_by: str = "status"
        self._selected_card_id: str = ""
        self._rebuild_timer = None

    def compose(self) -> ComposeResult:
        yield Horizontal(id="kanban-columns")

    def on_mount(self) -> None:
        self._schedule_rebuild()

    def update_data(
        self, nodes: list[WBSNode], view_config: ViewConfig | None = None, title_map: dict[str, WBSNode] | None = None
    ) -> None:
        self._wbs_nodes = nodes
        if view_config:
            self._view_config = view_config
            self._group_by = view_config.group_by
        if title_map is not None:
            self._title_map = title_map
        self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        """Debounce rebuild to avoid DuplicateIds from async remove_children."""
        if self._rebuild_timer is not None:
            self._rebuild_timer.stop()
        self._rebuild_timer = self.set_timer(0.01, self._rebuild)

    async def _rebuild(self) -> None:
        self._rebuild_timer = None
        try:
            container = self.query_one("#kanban-columns", Horizontal)
        except Exception:
            return
        await container.remove_children()

        # Flatten nodes
        flat: list[WBSNode] = []
        for node in self._wbs_nodes:
            self._flatten(node, flat)

        # Group by status
        groups: dict[str, list[WBSNode]] = {}
        if self._group_by == "status":
            for s in Status:
                groups[s.value] = []
            for node in flat:
                groups.setdefault(node.status.value, []).append(node)
        elif self._group_by == "priority":
            from tui_wbs.models import Priority

            for p in Priority:
                groups[p.value] = []
            for node in flat:
                groups.setdefault(node.priority.value, []).append(node)
        elif self._group_by == "assignee":
            for node in flat:
                key = node.assignee or "(unassigned)"
                groups.setdefault(key, []).append(node)
        else:
            groups["All"] = flat

        for i, (title, cards) in enumerate(groups.items()):
            col = KanbanColumn(title, cards, title_map=self._title_map, id=f"kanban-col-{i}")
            await container.mount(col)

    def _flatten(self, node: WBSNode, result: list[WBSNode]) -> None:
        result.append(node)
        for child in node.children:
            self._flatten(child, result)

    def move_card(self, node_id: str, direction: int) -> None:
        """Move card left (-1) or right (+1) in status columns."""
        statuses = list(Status)
        # Find current status
        for node in self._all_flat():
            if node.id == node_id:
                try:
                    idx = statuses.index(node.status)
                except ValueError:
                    return
                new_idx = max(0, min(len(statuses) - 1, idx + direction))
                if new_idx != idx:
                    self.post_message(self.CardMoved(node_id, statuses[new_idx]))
                return

    def _all_flat(self) -> list[WBSNode]:
        flat: list[WBSNode] = []
        for node in self._wbs_nodes:
            self._flatten(node, flat)
        return flat
