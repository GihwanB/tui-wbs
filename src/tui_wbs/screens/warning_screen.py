"""Parse warnings modal screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from tui_wbs.models import ParseWarning
from tui_wbs import theme


class WarningScreen(ModalScreen[None]):
    """Modal screen showing parse warnings."""

    BINDINGS = [("escape", "dismiss", "Close")]

    DEFAULT_CSS = """
    WarningScreen {
        align: center middle;
    }
    #warning-container {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $warning;
        padding: 1 2;
    }
    #warning-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    .warning-item {
        margin-bottom: 0;
    }
    """

    def __init__(self, warnings: list[ParseWarning]) -> None:
        super().__init__()
        self.warnings = warnings

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="warning-container"):
            count = len(self.warnings)
            yield Static(
                f"[bold]Parse Warnings ({count})[/bold]",
                id="warning-title",
            )
            if not self.warnings:
                yield Static("No warnings.")
            else:
                for w in self.warnings:
                    yield Static(f"[{theme.WARNING_ICON.dark}]⚠[/{theme.WARNING_ICON.dark}] {w}", classes="warning-item")
