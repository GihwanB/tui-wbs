"""Full-field node edit form screen."""

from __future__ import annotations

from datetime import date as date_cls

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static, TextArea

from tui_wbs.models import ColumnDef, Priority, Status, WBSNode


class NodeEditScreen(ModalScreen[dict | None]):
    """Modal form for editing all fields of a WBS node."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    NodeEditScreen {
        align: center middle;
    }
    #node-edit-container {
        width: 70;
        max-height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #node-edit-title {
        text-style: bold;
        margin-bottom: 1;
    }
    .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    .field-input {
        margin-bottom: 0;
    }
    #node-edit-memo {
        height: 5;
        margin-bottom: 0;
    }
    #node-edit-buttons {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    #node-edit-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        node: WBSNode,
        custom_columns: list[ColumnDef] | None = None,
        focus_field: str = "",
    ) -> None:
        super().__init__()
        self._node = node
        self._custom_columns = custom_columns or []
        self._focus_field = focus_field

    def compose(self) -> ComposeResult:
        node = self._node
        with VerticalScroll(id="node-edit-container"):
            yield Static("[bold]Edit Node[/bold]", id="node-edit-title")

            # Title
            yield Static("Title", classes="field-label")
            yield Input(value=node.title, id="field-title", classes="field-input")

            # Status
            yield Static("Status", classes="field-label")
            yield Select(
                [(s.value, s.value) for s in Status],
                value=node.status.value,
                id="field-status",
                classes="field-input",
            )

            # Priority
            yield Static("Priority", classes="field-label")
            yield Select(
                [(p.value, p.value) for p in Priority],
                value=node.priority.value,
                id="field-priority",
                classes="field-input",
            )

            # Assignee
            yield Static("Assignee", classes="field-label")
            yield Input(value=node.assignee, id="field-assignee", classes="field-input")

            # Duration
            yield Static("Duration", classes="field-label")
            yield Input(
                value=node.duration,
                placeholder="e.g. 5d, 2w",
                id="field-duration",
                classes="field-input",
            )

            # Start
            yield Static("Start Date", classes="field-label")
            yield Input(
                value=node.start.isoformat() if node.start else "",
                placeholder="YYYY-MM-DD",
                id="field-start",
                classes="field-input",
            )

            # End
            yield Static("End Date", classes="field-label")
            yield Input(
                value=node.end.isoformat() if node.end else "",
                placeholder="YYYY-MM-DD",
                id="field-end",
                classes="field-input",
            )

            # Dependencies
            yield Static("Dependencies", classes="field-label")
            yield Input(
                value=node.depends,
                placeholder="Title1; Title2",
                id="field-depends",
                classes="field-input",
            )

            # Milestone
            yield Static("Milestone", classes="field-label")
            yield Select(
                [("Yes", "true"), ("No", "false")],
                value="true" if node.milestone else "false",
                id="field-milestone",
                classes="field-input",
            )

            # Progress
            yield Static("Progress", classes="field-label")
            yield Input(
                value=str(node.progress) if node.progress is not None else "",
                placeholder="0-100 (empty = auto)",
                id="field-progress",
                classes="field-input",
            )

            # Memo
            yield Static("Memo", classes="field-label")
            yield TextArea(node.memo, id="node-edit-memo")

            # Custom fields
            for col in self._custom_columns:
                yield Static(col.name, classes="field-label")
                current_val = node.custom_fields.get(col.id, "")
                if col.type == "enum" and col.values:
                    # Include empty option + defined values
                    options = [("(none)", "")] + [(v, v) for v in col.values]
                    yield Select(
                        options,
                        value=current_val if current_val else "",
                        id=f"field-custom-{col.id}",
                        classes="field-input",
                    )
                else:
                    yield Input(
                        value=current_val,
                        id=f"field-custom-{col.id}",
                        classes="field-input",
                    )

            with Horizontal(id="node-edit-buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        self.set_timer(0.01, self._focus_first)

    def _focus_first(self) -> None:
        if self._focus_field:
            # Try standard field first, then custom field
            for target_id in (f"#field-{self._focus_field}", f"#field-custom-{self._focus_field}"):
                try:
                    widget = self.query_one(target_id)
                    widget.focus()
                    return
                except Exception:
                    continue
        try:
            self.query_one("#field-title", Input).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._submit()
        else:
            self.dismiss(None)

    def _submit(self) -> None:
        changes = self._collect_changes()
        if changes is None:
            return  # validation error shown
        self.dismiss(changes)

    def _collect_changes(self) -> dict | None:
        """Collect changed fields. Returns None on validation error."""
        node = self._node
        changes: dict = {}

        # Title
        title = self.query_one("#field-title", Input).value.strip()
        if not title:
            self.notify("Title cannot be empty", severity="error")
            return None
        if title != node.title:
            changes["title"] = title

        # Status
        status_val = self.query_one("#field-status", Select).value
        if status_val and status_val != node.status.value:
            try:
                changes["status"] = Status(status_val)
            except ValueError:
                pass

        # Priority
        priority_val = self.query_one("#field-priority", Select).value
        if priority_val and priority_val != node.priority.value:
            try:
                changes["priority"] = Priority(priority_val)
            except ValueError:
                pass

        # Assignee
        assignee = self.query_one("#field-assignee", Input).value.strip()
        if assignee != node.assignee:
            changes["assignee"] = assignee

        # Duration
        duration = self.query_one("#field-duration", Input).value.strip()
        if duration != node.duration:
            changes["duration"] = duration

        # Start
        start_str = self.query_one("#field-start", Input).value.strip()
        old_start = node.start.isoformat() if node.start else ""
        if start_str != old_start:
            if not start_str:
                changes["start"] = None
            else:
                try:
                    changes["start"] = date_cls.fromisoformat(start_str)
                except ValueError:
                    self.notify("Invalid start date (use YYYY-MM-DD)", severity="error")
                    return None

        # End
        end_str = self.query_one("#field-end", Input).value.strip()
        old_end = node.end.isoformat() if node.end else ""
        if end_str != old_end:
            if not end_str:
                changes["end"] = None
            else:
                try:
                    changes["end"] = date_cls.fromisoformat(end_str)
                except ValueError:
                    self.notify("Invalid end date (use YYYY-MM-DD)", severity="error")
                    return None

        # Depends
        depends = self.query_one("#field-depends", Input).value.strip()
        if depends != node.depends:
            changes["depends"] = depends

        # Milestone
        milestone_val = self.query_one("#field-milestone", Select).value
        new_milestone = milestone_val == "true"
        if new_milestone != node.milestone:
            changes["milestone"] = new_milestone

        # Progress
        progress_str = self.query_one("#field-progress", Input).value.strip()
        old_progress_str = str(node.progress) if node.progress is not None else ""
        if progress_str != old_progress_str:
            if not progress_str:
                changes["progress"] = None
            else:
                try:
                    p = int(progress_str)
                    if not (0 <= p <= 100):
                        raise ValueError
                    changes["progress"] = p
                except ValueError:
                    self.notify("Progress must be 0-100", severity="error")
                    return None

        # Memo
        memo = self.query_one("#node-edit-memo", TextArea).text
        if memo != node.memo:
            changes["memo"] = memo

        # Custom fields
        new_custom = dict(node.custom_fields)
        custom_changed = False
        for col in self._custom_columns:
            try:
                widget = self.query_one(f"#field-custom-{col.id}")
                if isinstance(widget, Select):
                    val = widget.value or ""
                else:
                    val = widget.value.strip()
                old_val = node.custom_fields.get(col.id, "")
                if val != old_val:
                    new_custom[col.id] = val
                    custom_changed = True
            except Exception:
                pass
        if custom_changed:
            changes["custom_fields"] = new_custom

        return changes

    def action_cancel(self) -> None:
        self.dismiss(None)
