"""Tests for the Kanban board widget."""

import pytest

from tui_wbs.models import Priority, Status, WBSNode, ViewConfig
from tui_wbs.widgets.kanban_board import KanbanBoard


class TestKanbanBoardGrouping:
    def _make_nodes(self):
        return [
            WBSNode(title="Root", level=1, status=Status.IN_PROGRESS, children=(
                WBSNode(title="Todo Task", level=2, status=Status.TODO, assignee="Alice"),
                WBSNode(title="Done Task", level=2, status=Status.DONE, assignee="Bob"),
                WBSNode(
                    title="In Progress",
                    level=2,
                    status=Status.IN_PROGRESS,
                    priority=Priority.HIGH,
                    assignee="Alice",
                ),
            )),
        ]

    def test_flatten_produces_all_nodes(self):
        board = KanbanBoard()
        nodes = self._make_nodes()
        flat: list[WBSNode] = []
        board._flatten(nodes[0], flat)
        assert len(flat) == 4  # root + 3 children

    def test_group_by_status(self):
        board = KanbanBoard()
        board._group_by = "status"
        nodes = self._make_nodes()
        flat: list[WBSNode] = []
        for n in nodes:
            board._flatten(n, flat)

        groups: dict[str, list[WBSNode]] = {}
        for s in Status:
            groups[s.value] = []
        for node in flat:
            groups.setdefault(node.status.value, []).append(node)

        assert len(groups["TODO"]) == 1
        assert len(groups["IN_PROGRESS"]) == 2  # root + child
        assert len(groups["DONE"]) == 1

    def test_group_by_priority(self):
        board = KanbanBoard()
        board._group_by = "priority"
        nodes = self._make_nodes()
        flat: list[WBSNode] = []
        for n in nodes:
            board._flatten(n, flat)

        groups: dict[str, list[WBSNode]] = {}
        for p in Priority:
            groups[p.value] = []
        for node in flat:
            groups.setdefault(node.priority.value, []).append(node)

        assert len(groups["HIGH"]) == 1
        assert len(groups["MEDIUM"]) == 3

    def test_group_by_assignee(self):
        board = KanbanBoard()
        board._group_by = "assignee"
        nodes = self._make_nodes()
        flat: list[WBSNode] = []
        for n in nodes:
            board._flatten(n, flat)

        groups: dict[str, list[WBSNode]] = {}
        for node in flat:
            key = node.assignee or "(unassigned)"
            groups.setdefault(key, []).append(node)

        assert "Alice" in groups
        assert "Bob" in groups
        assert "(unassigned)" in groups  # root has no assignee


class TestKanbanBoardMoveCard:
    def test_move_card_right(self):
        board = KanbanBoard()
        node = WBSNode(title="Task", level=1, status=Status.TODO, id="test-id")
        board._wbs_nodes = [node]

        # Capture emitted message
        messages = []
        original_post = board.post_message

        def capture_msg(msg):
            messages.append(msg)

        board.post_message = capture_msg

        board.move_card("test-id", 1)  # Move right: TODO -> IN_PROGRESS
        assert len(messages) == 1
        assert isinstance(messages[0], KanbanBoard.CardMoved)
        assert messages[0].new_status == Status.IN_PROGRESS

    def test_move_card_left_at_beginning(self):
        board = KanbanBoard()
        node = WBSNode(title="Task", level=1, status=Status.TODO, id="test-id")
        board._wbs_nodes = [node]

        messages = []
        board.post_message = lambda msg: messages.append(msg)

        board.move_card("test-id", -1)  # Already at leftmost (TODO)
        assert len(messages) == 0  # No movement

    def test_move_card_right_from_done(self):
        board = KanbanBoard()
        node = WBSNode(title="Task", level=1, status=Status.DONE, id="test-id")
        board._wbs_nodes = [node]

        messages = []
        board.post_message = lambda msg: messages.append(msg)

        board.move_card("test-id", 1)  # Already at rightmost (DONE)
        assert len(messages) == 0

    def test_move_nonexistent_card(self):
        board = KanbanBoard()
        board._wbs_nodes = []

        messages = []
        board.post_message = lambda msg: messages.append(msg)

        board.move_card("nonexistent", 1)
        assert len(messages) == 0


class TestKanbanCardDisplay:
    def test_card_label(self):
        from tui_wbs.widgets.kanban_board import KanbanCard

        node = WBSNode(
            title="Test Task",
            level=1,
            priority=Priority.HIGH,
            assignee="Alice",
        )
        card = KanbanCard(node)
        assert card.node_id == node.id

    def test_milestone_card_class(self):
        from tui_wbs.widgets.kanban_board import KanbanCard

        node = WBSNode(title="Milestone", level=1, milestone=True)
        card = KanbanCard(node)
        assert "card-milestone" in card.classes
