"""Settings modal screen."""

from __future__ import annotations

import uuid

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static
from textual.widgets.option_list import Option

from tui_wbs.models import ColumnDef, DATE_FORMAT_PRESETS, ProjectConfig, ViewConfig


class SettingsModal(ModalScreen[ProjectConfig | None]):
    """Settings modal for project configuration."""

    BINDINGS = [("escape", "cancel", "Close")]

    DEFAULT_CSS = """
    SettingsModal {
        align: center middle;
    }
    #settings-container {
        width: 75;
        max-height: 85%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #settings-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    .settings-section {
        margin-bottom: 1;
    }
    .settings-label {
        text-style: bold;
        color: $text-muted;
    }
    #settings-buttons {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    #settings-buttons Button {
        margin: 0 1;
    }
    .action-row {
        height: 3;
    }
    .action-row Button {
        margin: 0 0 0 1;
        min-width: 8;
    }
    #view-list {
        height: auto;
        max-height: 8;
    }
    #col-list {
        height: auto;
        max-height: 6;
    }
    """

    def __init__(self, config: ProjectConfig) -> None:
        super().__init__()
        self._config = config
        self._selected_view_idx: int = -1
        self._selected_col_idx: int = -1

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="settings-container"):
            yield Static("[bold]Settings[/bold]", id="settings-title")

            # --- Project ---
            yield Static("[bold]Project[/bold]", classes="settings-label")
            yield Label("Name:")
            yield Input(
                value=self._config.name,
                placeholder="Project name",
                id="project-name-input",
            )
            yield Label("Date Format:")
            yield Select(
                [(label, label) for label in DATE_FORMAT_PRESETS],
                value=self._config.date_format,
                id="date-format-select",
                allow_blank=False,
            )

            # --- Views ---
            yield Static("")
            yield Static("[bold]Views[/bold]", classes="settings-label")
            yield self._build_view_list()
            with Horizontal(classes="action-row"):
                yield Button("Add", id="view-add-btn", variant="primary")
                yield Button("Edit", id="view-edit-btn", variant="default")
                yield Button("Dup", id="view-dup-btn", variant="default")
                yield Button("Del", id="view-del-btn", variant="warning")

            # View edit fields (hidden initially)
            yield Static("", id="view-edit-section")

            # --- Default Columns ---
            yield Static("")
            yield Static("[bold]Default Columns[/bold]", classes="settings-label")
            yield Static(
                ", ".join(self._config.default_columns), id="columns-display"
            )

            # --- Custom Columns ---
            yield Static("")
            yield Static("[bold]Custom Columns[/bold]", classes="settings-label")
            yield self._build_col_list()
            with Horizontal(classes="action-row"):
                yield Button("Add", id="col-add-btn", variant="primary")
                yield Button("Edit", id="col-edit-btn", variant="default")
                yield Button("Del", id="col-del-btn", variant="warning")

            # Column edit fields
            yield Static("", id="col-edit-section")

            # --- Save/Close ---
            with Horizontal(id="settings-buttons"):
                yield Button("Save", variant="primary", id="save-btn")
                yield Button("Close", variant="default", id="close-btn")

    def _build_view_list(self) -> OptionList:
        ol = OptionList(id="view-list")
        for i, v in enumerate(self._config.views):
            ol.add_option(Option(f"  {v.name} ({v.type})", id=f"view-{i}"))
        return ol

    def _build_col_list(self) -> OptionList:
        ol = OptionList(id="col-list")
        for i, col in enumerate(self._config.custom_columns):
            vals = f" ({', '.join(col.values)})" if col.values else ""
            ol.add_option(Option(f"  {col.name} [{col.type}]{vals}", id=f"col-{i}"))
        return ol

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        opt_id = event.option.id or ""
        if opt_id.startswith("view-"):
            try:
                self._selected_view_idx = int(opt_id.split("-")[1])
            except (ValueError, IndexError):
                pass
        elif opt_id.startswith("col-"):
            try:
                self._selected_col_idx = int(opt_id.split("-")[1])
            except (ValueError, IndexError):
                pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button.id or ""

        if btn == "save-btn":
            self._apply_name()
            self.dismiss(self._config)
        elif btn == "close-btn":
            self.dismiss(None)
        # --- View actions ---
        elif btn == "view-add-btn":
            new_view = ViewConfig(name="New View", type="table")
            self._config.views.append(new_view)
            self._refresh_view_list()
        elif btn == "view-edit-btn":
            self._show_view_edit()
        elif btn == "view-dup-btn":
            if 0 <= self._selected_view_idx < len(self._config.views):
                orig = self._config.views[self._selected_view_idx]
                dup = ViewConfig(
                    id=str(uuid.uuid4()),
                    name=f"{orig.name} (copy)",
                    type=orig.type,
                    columns=list(orig.columns),
                    filters=list(orig.filters),
                    sort=orig.sort,
                    gantt_scale=orig.gantt_scale,
                    gantt_level=orig.gantt_level,
                    group_by=orig.group_by,
                )
                self._config.views.append(dup)
                self._refresh_view_list()
        elif btn == "view-del-btn":
            if 0 <= self._selected_view_idx < len(self._config.views) and len(self._config.views) > 1:
                self._config.views.pop(self._selected_view_idx)
                self._selected_view_idx = max(0, self._selected_view_idx - 1)
                self._refresh_view_list()
        elif btn == "view-save-edit-btn":
            self._apply_view_edit()
        # --- Column actions ---
        elif btn == "col-add-btn":
            new_col = ColumnDef(
                id=f"custom_{len(self._config.custom_columns) + 1}",
                name="New Column",
                type="text",
            )
            self._config.custom_columns.append(new_col)
            self._refresh_col_list()
        elif btn == "col-edit-btn":
            self._show_col_edit()
        elif btn == "col-del-btn":
            if 0 <= self._selected_col_idx < len(self._config.custom_columns):
                self._config.custom_columns.pop(self._selected_col_idx)
                self._selected_col_idx = max(0, self._selected_col_idx - 1)
                self._refresh_col_list()
        elif btn == "col-save-edit-btn":
            self._apply_col_edit()

    def _apply_name(self) -> None:
        try:
            name_input = self.query_one("#project-name-input", Input)
            self._config.name = name_input.value
        except Exception:
            pass
        try:
            fmt_select = self.query_one("#date-format-select", Select)
            if fmt_select.value and fmt_select.value != Select.BLANK:
                self._config.date_format = str(fmt_select.value)
        except Exception:
            pass

    def _refresh_view_list(self) -> None:
        try:
            old = self.query_one("#view-list", OptionList)
            old.clear_options()
            for i, v in enumerate(self._config.views):
                old.add_option(Option(f"  {v.name} ({v.type})", id=f"view-{i}"))
        except Exception:
            pass

    def _refresh_col_list(self) -> None:
        try:
            old = self.query_one("#col-list", OptionList)
            old.clear_options()
            for i, col in enumerate(self._config.custom_columns):
                vals = f" ({', '.join(col.values)})" if col.values else ""
                old.add_option(Option(f"  {col.name} [{col.type}]{vals}", id=f"col-{i}"))
        except Exception:
            pass

    def _show_view_edit(self) -> None:
        if not (0 <= self._selected_view_idx < len(self._config.views)):
            return
        view = self._config.views[self._selected_view_idx]
        try:
            section = self.query_one("#view-edit-section", Static)
            parent = section.parent
            if parent is None:
                return
            # Remove old edit widgets
            for w in self.query(".view-edit-widget"):
                w.remove()
            section.update("[bold]Edit View[/bold]")
            idx = parent._nodes.index(section)
            # Insert edit fields after section marker
            name_inp = Input(value=view.name, placeholder="View name", id="view-name-edit", classes="view-edit-widget")
            type_sel = Select(
                [("table", "table"), ("table+gantt", "table+gantt"), ("kanban", "kanban")],
                value=view.type,
                id="view-type-edit",
                allow_blank=False,
                classes="view-edit-widget",
            )
            save_btn = Button("Apply", id="view-save-edit-btn", variant="success", classes="view-edit-widget")
            parent.mount(name_inp, after=section)
            parent.mount(type_sel, after=name_inp)
            parent.mount(save_btn, after=type_sel)
        except Exception:
            pass

    def _apply_view_edit(self) -> None:
        if not (0 <= self._selected_view_idx < len(self._config.views)):
            return
        view = self._config.views[self._selected_view_idx]
        try:
            name_inp = self.query_one("#view-name-edit", Input)
            view.name = name_inp.value.strip() or view.name
        except Exception:
            pass
        try:
            type_sel = self.query_one("#view-type-edit", Select)
            if type_sel.value:
                view.type = str(type_sel.value)
        except Exception:
            pass
        self._refresh_view_list()
        # Clean up edit widgets
        for w in self.query(".view-edit-widget"):
            w.remove()
        try:
            self.query_one("#view-edit-section", Static).update("")
        except Exception:
            pass

    def _show_col_edit(self) -> None:
        if not (0 <= self._selected_col_idx < len(self._config.custom_columns)):
            return
        col = self._config.custom_columns[self._selected_col_idx]
        try:
            section = self.query_one("#col-edit-section", Static)
            parent = section.parent
            if parent is None:
                return
            for w in self.query(".col-edit-widget"):
                w.remove()
            section.update("[bold]Edit Column[/bold]")
            id_inp = Input(value=col.id, placeholder="Column ID", id="col-id-edit", classes="col-edit-widget")
            name_inp = Input(value=col.name, placeholder="Column Name", id="col-name-edit", classes="col-edit-widget")
            type_sel = Select(
                [("text", "text"), ("enum", "enum"), ("number", "number")],
                value=col.type,
                id="col-type-edit",
                allow_blank=False,
                classes="col-edit-widget",
            )
            vals_inp = Input(
                value=", ".join(col.values),
                placeholder="Values (comma separated, for enum)",
                id="col-values-edit",
                classes="col-edit-widget",
            )
            save_btn = Button("Apply", id="col-save-edit-btn", variant="success", classes="col-edit-widget")
            parent.mount(id_inp, after=section)
            parent.mount(name_inp, after=id_inp)
            parent.mount(type_sel, after=name_inp)
            parent.mount(vals_inp, after=type_sel)
            parent.mount(save_btn, after=vals_inp)
        except Exception:
            pass

    def _apply_col_edit(self) -> None:
        if not (0 <= self._selected_col_idx < len(self._config.custom_columns)):
            return
        col = self._config.custom_columns[self._selected_col_idx]
        try:
            col.id = self.query_one("#col-id-edit", Input).value.strip() or col.id
        except Exception:
            pass
        try:
            col.name = self.query_one("#col-name-edit", Input).value.strip() or col.name
        except Exception:
            pass
        try:
            type_sel = self.query_one("#col-type-edit", Select)
            if type_sel.value:
                col.type = str(type_sel.value)
        except Exception:
            pass
        try:
            vals_str = self.query_one("#col-values-edit", Input).value
            col.values = [v.strip() for v in vals_str.split(",") if v.strip()]
        except Exception:
            pass
        self._refresh_col_list()
        for w in self.query(".col-edit-widget"):
            w.remove()
        try:
            self.query_one("#col-edit-section", Static).update("")
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)
