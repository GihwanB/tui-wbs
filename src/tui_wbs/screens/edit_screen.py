"""Edit screen for inline text editing."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, TextArea


class EditScreen(ModalScreen[str | None]):
    """Modal for editing a single text value."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    EditScreen {
        align: center middle;
    }
    #edit-container {
        width: 60;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #edit-label {
        margin-bottom: 1;
        text-style: bold;
    }
    #edit-input {
        margin-bottom: 1;
    }
    #edit-textarea {
        height: 8;
        margin-bottom: 1;
    }
    #edit-buttons {
        align: center middle;
        height: 3;
    }
    #edit-buttons Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        label: str,
        initial_value: str = "",
        placeholder: str = "",
        multiline: bool = False,
    ) -> None:
        super().__init__()
        self._label = label
        self._initial_value = initial_value
        self._placeholder = placeholder
        self._multiline = multiline

    def compose(self) -> ComposeResult:
        with Static(id="edit-container"):
            yield Static(self._label, id="edit-label")
            if self._multiline:
                yield TextArea(self._initial_value, id="edit-textarea")
            else:
                yield Input(
                    value=self._initial_value,
                    placeholder=self._placeholder,
                    id="edit-input",
                )
            with Horizontal(id="edit-buttons"):
                yield Button("OK", variant="primary", id="ok-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    def on_mount(self) -> None:
        try:
            if self._multiline:
                self.query_one("#edit-textarea", TextArea).focus()
            else:
                self.query_one("#edit-input", Input).focus()
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ok-btn":
            self._submit()
        else:
            self.dismiss(None)

    def _submit(self) -> None:
        try:
            if self._multiline:
                val = self.query_one("#edit-textarea", TextArea).text
            else:
                val = self.query_one("#edit-input", Input).value
            self.dismiss(val)
        except Exception:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
