"""Selection screen using OptionList."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


class SelectScreen(ModalScreen[str | None]):
    """Modal for selecting one item from a list."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    SelectScreen {
        align: center middle;
    }
    #select-container {
        width: 50;
        max-height: 70%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #select-label {
        text-style: bold;
        margin-bottom: 1;
    }
    #select-list {
        height: auto;
        max-height: 100%;
    }
    #select-list > .option-list--option-highlighted {
        background: $accent;
        color: $text;
    }
    """

    def __init__(self, label: str, options: list[tuple[str, str]], initial_value: str = "") -> None:
        """Create a selection screen.

        Args:
            label: Title displayed above the list.
            options: List of (value, display_text) tuples.
            initial_value: Value to highlight initially.
        """
        super().__init__()
        self._label = label
        self._options = options
        self._initial_value = initial_value
        self._ready = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="select-container"):
            yield Static(self._label, id="select-label")
            ol = OptionList(id="select-list")
            for value, display in self._options:
                ol.add_option(Option(f"  {display}", id=value))
            yield ol

    def on_mount(self) -> None:
        self.set_timer(0.01, self._focus_list)

    def _focus_list(self) -> None:
        try:
            ol = self.query_one("#select-list", OptionList)
            if self._initial_value:
                for i, (value, _) in enumerate(self._options):
                    if value == self._initial_value:
                        ol.highlighted = i
                        break
            ol.focus()
        except Exception:
            pass
        self._ready = True

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if not self._ready:
            return
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)
