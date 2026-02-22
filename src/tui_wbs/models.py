"""Data models for TUI WBS."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any


class Status(Enum):
    """WBS node status."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class Priority(Enum):
    """WBS node priority."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


STATUS_ICONS = {
    Status.TODO: "○",
    Status.IN_PROGRESS: "◐",
    Status.DONE: "●",
}

PRIORITY_ICONS = {
    Priority.HIGH: "◆",
    Priority.MEDIUM: "▲",
    Priority.LOW: "▽",
}

MILESTONE_ICON = "◇"
LOCK_ICON = "🔒"

DATE_FORMAT_PRESETS: dict[str, str] = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "MMM DD, YYYY": "%b %d, %Y",
    "MM-DD": "%m-%d",
}
DEFAULT_DATE_FORMAT = "MM-DD"


def format_date(d: date | None, date_format: str = DEFAULT_DATE_FORMAT) -> str:
    """Format a date for display. Returns empty string for None."""
    if d is None:
        return ""
    fmt = DATE_FORMAT_PRESETS.get(date_format)
    if fmt is None:
        return d.isoformat()
    return d.strftime(fmt)


@dataclass(frozen=True)
class WBSNode:
    """A single node in the WBS tree. Immutable — use dataclasses.replace() to edit."""

    title: str
    level: int  # heading level: 1 = h1, 2 = h2, ...
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: Status = Status.TODO
    assignee: str = ""
    duration: str = ""
    priority: Priority = Priority.MEDIUM
    depends: str = ""  # semicolon-separated titles
    start: date | None = None
    end: date | None = None
    milestone: bool = False
    progress: int | None = None  # 0-100, None = auto-calculate
    memo: str = ""
    custom_fields: dict[str, str] = field(default_factory=dict)
    children: tuple[WBSNode, ...] = ()
    source_file: str = ""

    # Raw content preservation for round-trip
    _raw_heading_line: str = ""
    _raw_meta_lines: tuple[str, ...] = ()
    _raw_body_lines: tuple[str, ...] = ()
    _meta_modified: bool = False

    def with_child(self, child: WBSNode) -> WBSNode:
        """Return a new node with an additional child."""
        return replace(self, children=(*self.children, child))

    def replace_child(self, old_id: str, new_child: WBSNode) -> WBSNode:
        """Return a new node with a specific child replaced."""
        new_children = tuple(
            new_child if c.id == old_id else c for c in self.children
        )
        return replace(self, children=new_children)

    def all_nodes(self) -> list[WBSNode]:
        """Return a flat list of this node and all descendants."""
        result = [self]
        for child in self.children:
            result.extend(child.all_nodes())
        return result

    @property
    def status_icon(self) -> str:
        return STATUS_ICONS[self.status]

    @property
    def priority_icon(self) -> str:
        return PRIORITY_ICONS[self.priority]

    @property
    def display_icon(self) -> str:
        """Primary display icon: milestone takes precedence."""
        if self.milestone:
            return MILESTONE_ICON
        return self.status_icon

    @property
    def computed_progress(self) -> int:
        """Calculate progress: explicit value or auto from children."""
        if self.progress is not None:
            return self.progress
        if not self.children:
            return 100 if self.status == Status.DONE else 0
        total = len(self.children)
        done = sum(1 for c in self.children if c.status == Status.DONE)
        return int(done / total * 100) if total > 0 else 0

    @property
    def depends_list(self) -> list[str]:
        """Parse depends string into a list of titles."""
        if not self.depends.strip():
            return []
        return [d.strip() for d in self.depends.split(";") if d.strip()]


import re

_DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([a-zA-Z]*)$")


def parse_duration(s: str) -> tuple[float, str] | None:
    """Parse a duration string like '5d' into (value, unit). Returns None on failure."""
    s = s.strip()
    if not s:
        return None
    m = _DURATION_RE.match(s)
    if not m:
        return None
    return float(m.group(1)), m.group(2) or "d"


def adjust_duration(duration: str, delta: int) -> str:
    """Adjust a duration string by delta. '5d' + 1 → '6d'. Empty + 1 → '1d'."""
    parsed = parse_duration(duration)
    if parsed is None:
        if not duration.strip() and delta > 0:
            return "1d"
        return duration
    value, unit = parsed
    new_value = value + delta
    if new_value < 0:
        new_value = 0
    if new_value == int(new_value):
        return f"{int(new_value)}{unit}"
    return f"{new_value}{unit}"


def duration_to_days(duration_str: str) -> int | None:
    """Convert a duration string to days. '5d'→5, '2w'→14, '8h'→1. Returns None on failure."""
    parsed = parse_duration(duration_str)
    if parsed is None:
        return None
    value, unit = parsed
    unit = unit.lower()
    if unit in ("d", "day", "days", ""):
        return max(1, int(value))
    elif unit in ("w", "week", "weeks"):
        return max(1, int(value * 7))
    elif unit in ("h", "hour", "hours"):
        return max(1, int(value / 8)) if value > 0 else 0
    elif unit in ("m", "month", "months"):
        return max(1, int(value * 30))
    return max(1, int(value))


def days_to_duration(days: int) -> str:
    """Convert days to a duration string. 5→'5d'."""
    if days <= 0:
        return "0d"
    return f"{days}d"


def has_incomplete_dependencies(node: WBSNode, title_map: dict[str, WBSNode]) -> bool:
    """Return True if any dependency of the node is not DONE."""
    for dep_title in node.depends_list:
        dep_node = title_map.get(dep_title)
        if dep_node is None or dep_node.status != Status.DONE:
            return True
    return False


@dataclass
class ParseWarning:
    """A warning generated during parsing."""

    file_path: str
    line_number: int
    message: str

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line_number}: {self.message}"


@dataclass
class WBSDocument:
    """Represents a single parsed .wbs.md file."""

    file_path: Path
    root_nodes: list[WBSNode] = field(default_factory=list)
    raw_content: str = ""
    modified: bool = False
    parse_warnings: list[ParseWarning] = field(default_factory=list)

    def all_nodes(self) -> list[WBSNode]:
        """Return a flat list of all nodes in this document."""
        result: list[WBSNode] = []
        for root in self.root_nodes:
            result.extend(root.all_nodes())
        return result


@dataclass
class FilterConfig:
    """A single filter condition."""

    field: str = ""
    operator: str = "eq"  # eq, neq, contains
    value: str = ""


@dataclass
class SortConfig:
    """Sort configuration."""

    field: str = "title"
    order: str = "asc"  # asc, desc


@dataclass
class ViewConfig:
    """Configuration for a single view."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Table"
    type: str = "table"  # table, table+gantt, kanban
    columns: list[str] = field(
        default_factory=lambda: ["title", "status", "priority", "assignee", "duration"]
    )
    filters: list[FilterConfig] = field(default_factory=list)
    sort: SortConfig = field(default_factory=SortConfig)
    column_widths: dict[str, int] = field(default_factory=dict)
    gantt_scale: str = "week"  # day, week, month, quarter, year
    gantt_level: int = 3
    group_by: str = "status"


@dataclass
class ColumnDef:
    """Definition for a custom column."""

    id: str = ""
    name: str = ""
    type: str = "text"  # text, enum, number
    values: list[str] = field(default_factory=list)


@dataclass
class ProjectConfig:
    """Project-level configuration stored in .tui-wbs/config.toml."""

    name: str = ""
    default_view: str = ""
    theme_name: str = "default_dark"
    date_format: str = "MM-DD"
    default_columns: list[str] = field(
        default_factory=lambda: [
            "id", "title", "status", "priority", "progress", "assignee", "start", "end", "duration",
            "module", "label",
        ]
    )
    custom_columns: list[ColumnDef] = field(default_factory=list)
    views: list[ViewConfig] = field(default_factory=list)

    def get_view(self, view_id: str) -> ViewConfig | None:
        """Find a view by ID."""
        for v in self.views:
            if v.id == view_id:
                return v
        return None

    def ensure_default_view(self) -> None:
        """Ensure at least one view of each type exists."""
        if not self.views:
            table_view = ViewConfig(
                id="default-table",
                name="Table",
                type="table",
                columns=["id", "title", "status", "priority", "progress", "assignee", "start", "end", "duration", "module", "label"],
            )
            gantt_view = ViewConfig(
                id="default-gantt",
                name="Gantt",
                type="table+gantt",
                columns=["id", "title", "status", "progress", "assignee", "start", "end"],
                gantt_scale="week",
                gantt_level=3,
                sort=SortConfig(field="id", order="asc"),
            )
            kanban_view = ViewConfig(
                id="default-kanban",
                name="Board",
                type="kanban",
                columns=["title", "priority", "assignee"],
                group_by="status",
            )
            self.views.extend([table_view, gantt_view, kanban_view])
            if not self.default_view:
                self.default_view = table_view.id
        # Ensure default custom columns exist
        if not self.custom_columns:
            self.custom_columns = [
                ColumnDef(id="label", name="Label", type="text"),
                ColumnDef(id="module", name="Module", type="text"),
            ]


@dataclass
class WBSProject:
    """Represents a folder-based WBS project."""

    dir_path: Path
    documents: list[WBSDocument] = field(default_factory=list)
    config: ProjectConfig = field(default_factory=ProjectConfig)
    parse_warnings: list[ParseWarning] = field(default_factory=list)

    def all_nodes(self) -> list[WBSNode]:
        """Return a flat list of all nodes across all documents."""
        result: list[WBSNode] = []
        for doc in self.documents:
            result.extend(doc.all_nodes())
        return result

    def all_root_nodes(self) -> list[WBSNode]:
        """Return all root nodes from all documents."""
        result: list[WBSNode] = []
        for doc in self.documents:
            result.extend(doc.root_nodes)
        return result

    def find_node_by_title(self, title: str) -> WBSNode | None:
        """Find the first node with the given title."""
        for node in self.all_nodes():
            if node.title == title:
                return node
        return None
