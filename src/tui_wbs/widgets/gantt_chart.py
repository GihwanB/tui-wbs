"""Gantt chart custom widget."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from textual.app import ComposeResult
from textual.containers import Container
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.widget import Widget

from rich.segment import Segment
from rich.style import Style
from rich.text import Text

from tui_wbs.models import WBSNode, ViewConfig, Status
from tui_wbs import theme


COL_WIDTH = 6  # Default fallback

COL_WIDTH_MAP: dict[str, int] = {
    "day": 2,
    "week": 7,
    "week2": 8,
    "month": 6,
    "quarter": 6,
    "year": 6,
}

BAND_AMOUNT = 0.18  # darken 정도 (18%)


def _band_bg(char_col: int, band_style: Style, base_style: Style, col_width: int = COL_WIDTH) -> Style:
    """홀수 컬럼(col_width 단위)이면 band_style 반환, 짝수면 base_style."""
    if (char_col // col_width) % 2 == 1:
        return band_style
    return base_style


def _is_weekend_col(char_col: int, date_start: date, scale: str, col_width: int, days_per_col: int) -> bool:
    """Return True if the character column corresponds to a weekend day (Sat/Sun)."""
    if scale == "week" and col_width == 7:
        # Use actual date calculation instead of assuming date_start is Monday
        d = _col_to_date(char_col, date_start, scale, col_width, days_per_col)
        return d.weekday() >= 5  # 5=Sat, 6=Sun
    elif scale == "day" and col_width == 2:
        # Each 2-char block = 1 day
        col_index = char_col // col_width
        d = date_start + timedelta(days=col_index)
        return d.weekday() >= 5
    return False


def _col_to_date(char_col: int, date_start: date, scale: str, col_width: int, days_per_col: int) -> date:
    """Convert a character column position to the corresponding date."""
    if scale == "week" and col_width == 7:
        week_index = char_col // 7
        day_offset = char_col % 7
        return date_start + timedelta(days=week_index * 7 + day_offset)
    elif scale == "day" and col_width == 2:
        col_index = char_col // col_width
        return date_start + timedelta(days=col_index)
    else:
        col_index = char_col // col_width
        return date_start + timedelta(days=col_index * days_per_col)


def _is_holiday_col(char_col: int, date_start: date, scale: str, col_width: int, days_per_col: int, holidays: set[date]) -> bool:
    """Return True if the character column corresponds to a holiday."""
    if not holidays:
        return False
    if scale in ("week", "day"):
        d = _col_to_date(char_col, date_start, scale, col_width, days_per_col)
        return d in holidays
    return False


# Scale configurations: (label_format, column_width_days)
SCALE_CONFIG = {
    "day": 1,
    "week": 7,
    "week2": 7,
    "month": 30,
    "quarter": 91,
    "year": 365,
}

SCALE_KEYS = ["day", "week", "week2", "month", "quarter", "year"]
SCALE_LABELS = {"day": "D", "week": "W", "week2": "W2", "month": "M", "quarter": "Q", "year": "Y"}


class GanttToolbar(Widget):
    """1-line toolbar showing today's date and clickable scale buttons."""

    class ScaleChanged(Message):
        def __init__(self, scale: str) -> None:
            super().__init__()
            self.scale = scale

    DEFAULT_CSS = """
    GanttToolbar {
        height: 1;
        background: $background;
    }
    """

    def __init__(self, show_scale: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scale: str = "week"
        self._today: date = date.today()
        self._show_scale: bool = show_scale
        self._button_regions: list[tuple[int, int, str]] = []

    def update_toolbar(self, scale: str, today: date | None = None) -> None:
        self._scale = scale
        if today is not None:
            self._today = today
        self.refresh()

    @property
    def show_scale(self) -> bool:
        return self._show_scale

    @show_scale.setter
    def show_scale(self, value: bool) -> None:
        self._show_scale = value
        self.refresh()

    @property
    def _is_dark(self) -> bool:
        try:
            return self.app.dark
        except Exception:
            return True

    def render(self) -> Text:
        dark = self._is_dark
        text = Text()

        today_str = f"Today: {self._today.isoformat()}"
        text.append(today_str, Style(bold=True, color=theme.GANTT_TODAY_MARKER.resolve(dark)))

        self._button_regions = []
        if self._show_scale:
            text.append("  │ ", Style(dim=True))
            for i, scale_key in enumerate(SCALE_KEYS):
                label = SCALE_LABELS[scale_key]
                start = len(text)
                if scale_key == self._scale:
                    text.append(f" {label} ", Style(bold=True, reverse=True))
                else:
                    text.append(f" {label} ", Style(dim=True))
                end = len(text)
                self._button_regions.append((start, end, scale_key))
                if i < len(SCALE_KEYS) - 1:
                    text.append("│", Style(dim=True))

        return text

    def on_click(self, event) -> None:
        for start, end, scale in self._button_regions:
            if start <= event.x < end:
                if scale != self._scale:
                    self.post_message(self.ScaleChanged(scale))
                return


class GanttHeader(Widget):
    """Fixed header widget showing date labels and today marker."""

    DEFAULT_CSS = """
    GanttHeader {
        height: 3;
        background: $background;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._scale: str = "week"
        self._today: date = date.today()
        self._scroll_offset: int = 0
        self._date_start: date = date.today()
        self._date_end: date = date.today()
        self._days_per_col: int = 7
        self._chart_width: int = 60
        self._col_width: int = COL_WIDTH
        self.scroll_x_offset: int = 0
        self._holidays: set[date] = set()

    def set_holidays(self, holidays: set[date]) -> None:
        self._holidays = holidays

    def update_header(
        self,
        scale: str,
        today: date,
        scroll_offset: int,
        date_start: date,
        date_end: date,
        days_per_col: int,
        chart_width: int,
    ) -> None:
        self._scale = scale
        self._today = today
        self._scroll_offset = scroll_offset
        self._date_start = date_start
        self._date_end = date_end
        self._days_per_col = days_per_col
        self._chart_width = chart_width
        self._col_width = COL_WIDTH_MAP.get(scale, COL_WIDTH)
        self.refresh()

    @property
    def _is_dark(self) -> bool:
        try:
            return self.app.dark
        except Exception:
            return True

    @property
    def _band_style(self) -> Style:
        dark = self._is_dark
        try:
            _, bg = self.background_colors
            if bg.a < 0.1 or (dark and bg.brightness > 0.5) or (not dark and bg.brightness < 0.5):
                return Style(bgcolor=theme.GANTT_BAND_BG.resolve(dark))
            if dark:
                return Style(bgcolor=bg.lighten(BAND_AMOUNT).rich_color)
            else:
                return Style(bgcolor=bg.darken(BAND_AMOUNT).rich_color)
        except Exception:
            return Style(bgcolor=theme.GANTT_BAND_BG.resolve(dark))

    @property
    def _base_style(self) -> Style:
        dark = self._is_dark
        try:
            _, bg = self.background_colors
            if bg.a < 0.1 or (dark and bg.brightness > 0.5) or (not dark and bg.brightness < 0.5):
                return Style(bgcolor=theme.GANTT_BASE_BG.resolve(dark))
            return Style(bgcolor=bg.rich_color)
        except Exception:
            return Style(bgcolor=theme.GANTT_BASE_BG.resolve(dark))

    def render_line(self, y: int) -> Strip:
        width = max(self.size.width, self._chart_width)
        if y == 0:
            full = self._render_group_row(width)
        elif y == 1:
            full = self._render_detail_row(width)
        elif y == 2:
            full = self._render_today_line(width)
        else:
            return Strip.blank(self.size.width)
        return full.crop(self.scroll_x_offset, self.scroll_x_offset + self.size.width)

    def _render_group_row(self, width: int) -> Strip:
        """Row 0: month/year group labels with merged spans and alternating background."""
        band = self._band_style
        base = self._base_style
        cw = self._col_width
        if self._scale == "year":
            segments: list[Segment] = []
            for c in range(width):
                segments.append(Segment(" ", _band_bg(c, band, base, cw)))
            return Strip(segments)

        # 1) Collect group spans: list of (group_key, label, start_col, span_cols)
        spans: list[tuple[object, str, int, int]] = []
        cur = self._date_start
        col = 0
        prev_group = None
        while col < width and cur <= self._date_end:
            if self._scale in ("day", "week", "week2"):
                group = (cur.year, cur.month)
                label = cur.strftime("%b %y")
            else:  # month, quarter
                group = cur.year
                label = cur.strftime("%Y")

            if group != prev_group:
                spans.append((group, label, col, cw))
                prev_group = group
            else:
                # Extend the last span
                g, lbl, start, span_w = spans[-1]
                spans[-1] = (g, lbl, start, span_w + cw)

            col += cw
            cur += timedelta(days=self._days_per_col)

        # 2) Render merged spans with alternating background
        group_style_base = Style(bold=True, color=theme.GANTT_HEADER.resolve(self._is_dark))
        segments: list[Segment] = []
        for gi, (_, label, start, span_w) in enumerate(spans):
            bg = band if gi % 2 == 1 else base
            merged_label = label[:span_w].center(span_w)
            segments.append(Segment(merged_label, group_style_base + bg))

        rendered = sum(len(s.text) for s in segments)
        if rendered < width:
            last_gi = len(spans)
            for c in range(rendered, width):
                bg = band if last_gi % 2 == 1 else base
                segments.append(Segment(" ", bg))

        return Strip(segments)

    def _render_detail_row(self, width: int) -> Strip:
        """Row 1: detailed date labels (day/week number only, since group row shows month/year)."""
        segments: list[Segment] = []
        cur = self._date_start
        col = 0
        dark = self._is_dark
        header_style = Style(bold=True, color=theme.GANTT_HEADER.resolve(dark))
        weekend_header = Style(bold=True, color=theme.GANTT_HEADER.resolve(dark))
        weekend_bg = Style(bgcolor=theme.GANTT_WEEKEND_BG.resolve(dark))
        band = self._band_style
        base = self._base_style
        cw = self._col_width
        _DAY_ABBR = "MTWTFSS"  # Mon=0..Sun=6

        while col < width and cur <= self._date_end:
            if self._scale == "day":
                label = cur.strftime("%d")
                label = label[:cw].center(cw)
                if _is_weekend_col(col, self._date_start, self._scale, cw, self._days_per_col):
                    bg = weekend_bg
                else:
                    bg = _band_bg(col, band, base, cw)
                segments.append(Segment(label, header_style + bg))
            elif self._scale == "week":
                # 7 chars: week number label centered, with weekend bg on Sat/Sun positions
                label = f"W{cur.isocalendar()[1]}"
                padded = label.center(cw)
                for i, ch in enumerate(padded):
                    if _is_weekend_col(col + i, self._date_start, self._scale, cw, self._days_per_col):
                        bg = weekend_bg
                    else:
                        bg = _band_bg(col + i, band, base, cw)
                    segments.append(Segment(ch, header_style + bg))
            elif self._scale == "week2":
                label = f"W{cur.isocalendar()[1]}"
                label = label[:cw].center(cw)
                bg = _band_bg(col, band, base, cw)
                segments.append(Segment(label, header_style + bg))
            elif self._scale == "month":
                label = cur.strftime("%b")
                label = label[:cw].center(cw)
                bg = _band_bg(col, band, base, cw)
                segments.append(Segment(label, header_style + bg))
            elif self._scale == "quarter":
                q = (cur.month - 1) // 3 + 1
                label = f"Q{q}"
                label = label[:cw].center(cw)
                bg = _band_bg(col, band, base, cw)
                segments.append(Segment(label, header_style + bg))
            else:
                label = cur.strftime("%Y")
                label = label[:cw].center(cw)
                bg = _band_bg(col, band, base, cw)
                segments.append(Segment(label, header_style + bg))

            col += cw
            cur += timedelta(days=self._days_per_col)

        rendered = sum(len(s.text) for s in segments)
        if rendered < width:
            for c in range(rendered, width):
                segments.append(Segment(" ", _band_bg(c, band, base, cw)))

        return Strip(segments)

    def _render_today_line(self, width: int) -> Strip:
        today_col = self._date_to_col(self._today)
        segments: list[Segment] = []
        line_style = Style(color=theme.GANTT_TODAY_MARKER.resolve(self._is_dark))
        dim_style = Style(dim=True)
        band = self._band_style
        base = self._base_style
        cw = self._col_width

        for c in range(width):
            bg = _band_bg(c, band, base, cw)
            if c == today_col:
                segments.append(Segment("▼", line_style + bg))
            else:
                segments.append(Segment("┄", dim_style + bg))

        return Strip(segments)

    def _date_to_col(self, d: date) -> int:
        days = (d - self._date_start).days
        col_index = days // self._days_per_col
        base_col = col_index * self._col_width
        # Sub-column offset for week scale (1 day = 1 char within 7-char column)
        if self._scale == "week" and self._days_per_col == 7:
            day_offset = days % 7
            return max(0, base_col + day_offset)
        return max(0, base_col)


class GanttChart(Container):
    """Gantt chart widget showing Gantt bars for WBS nodes."""

    DEFAULT_CSS = """
    GanttChart {
        width: 1fr;
        height: 1fr;
    }
    GanttChart #gantt-header {
        height: 3;
    }
    GanttChart #gantt-view {
        height: 1fr;
    }
    """

    class NodeSelected(Message):
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    def __init__(self) -> None:
        super().__init__()
        self._flat_rows: list[tuple[WBSNode, int]] = []
        self._scale: str = "week"
        self._scroll_offset: int = 0
        self._today = date.today()
        self._pending_rebuild: bool = False
        self._holidays: set[date] = set()

    def set_holidays(self, holidays: list[date]) -> None:
        """Set the holidays list for rendering."""
        self._holidays = set(holidays)
        self._push_to_view()

    def compose(self) -> ComposeResult:
        yield GanttHeader(id="gantt-header")
        yield GanttView(id="gantt-view")

    def on_mount(self) -> None:
        """Push pending data after children are composed."""
        if self._flat_rows:
            self._push_to_view()

    def update_rows(self, flat_rows: list[tuple[WBSNode, int, str]]) -> None:
        """Accept flat rows from the table (node, depth, hier_id) → (node, depth)."""
        self._flat_rows = [(node, depth) for node, depth, _ in flat_rows]
        self._push_to_view()

    def update_config(self, view_config: ViewConfig) -> None:
        """Update scale from view config without rebuilding row list."""
        self._scale = view_config.gantt_scale
        self._push_to_view()

    def update_data(
        self, nodes: list[WBSNode], view_config: ViewConfig | None = None
    ) -> None:
        """Legacy API for standalone usage — flatten all nodes."""
        if view_config:
            self._scale = view_config.gantt_scale
        self._flat_rows = []
        for node in nodes:
            self._flatten_all(node, 0)
        self._push_to_view()

    def _flatten_all(self, node: WBSNode, depth: int) -> None:
        """Flatten all nodes regardless of level (for standalone/legacy usage)."""
        self._flat_rows.append((node, depth))
        for child in node.children:
            self._flatten_all(child, depth + 1)

    def set_scale(self, scale: str) -> None:
        if scale in SCALE_CONFIG:
            self._scale = scale
            self._push_to_view()

    def scroll_gantt(self, delta: int) -> None:
        self._scroll_offset += delta
        self._push_to_view()

    def go_to_today(self) -> None:
        self._scroll_offset = 0
        self._push_to_view()

    def on_gantt_view_scroll_x_changed(self, event: GanttView.ScrollXChanged) -> None:
        header = self.query_one("#gantt-header", GanttHeader)
        header.scroll_x_offset = int(event.scroll_x)
        header.refresh()

    def _push_to_view(self) -> None:
        """Push current flat_rows and scale config to the GanttView and GanttHeader."""
        try:
            view = self.query_one("#gantt-view", GanttView)
            header = self.query_one("#gantt-header", GanttHeader)
            view.set_holidays(self._holidays)
            view.update_gantt(
                self._flat_rows,
                self._scale,
                self._today,
                self._scroll_offset,
            )
            header.set_holidays(self._holidays)
            header.update_header(
                scale=self._scale,
                today=self._today,
                scroll_offset=self._scroll_offset,
                date_start=view._date_start,
                date_end=view._date_end,
                days_per_col=view._days_per_col,
                chart_width=view._chart_width,
            )
            self._pending_rebuild = False
        except Exception:
            if not self._pending_rebuild:
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    return
                self._pending_rebuild = True
                self.set_timer(0.01, self._push_to_view)


class GanttView(ScrollView):
    """Renders the Gantt bars (data rows only, no header)."""

    class ScrollXChanged(Message):
        """Emitted when horizontal scroll position changes."""

        def __init__(self, scroll_x: float) -> None:
            super().__init__()
            self.scroll_x = scroll_x

    class ScrollYChanged(Message):
        """Emitted when vertical scroll position changes."""

        def __init__(self, scroll_y: float) -> None:
            super().__init__()
            self.scroll_y = scroll_y

    DEFAULT_CSS = """
    GanttView {
        height: 1fr;
        background: $background;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._rows: list[tuple[WBSNode, int]] = []
        self._scale: str = "week"
        self._today: date = date.today()
        self._scroll_offset: int = 0
        self._chart_width: int = 60
        self._date_start: date = date.today()
        self._date_end: date = date.today()
        self._days_per_col: int = 7
        self._col_width: int = COL_WIDTH
        self._highlighted_row: int = -1
        self._holidays: set[date] = set()

    def set_holidays(self, holidays: set[date]) -> None:
        self._holidays = holidays

    def update_gantt(
        self,
        rows: list[tuple[WBSNode, int]],
        scale: str,
        today: date,
        scroll_offset: int,
    ) -> None:
        self._rows = rows
        self._scale = scale
        self._today = today
        self._scroll_offset = scroll_offset
        self._days_per_col = SCALE_CONFIG.get(scale, 7)
        self._col_width = COL_WIDTH_MAP.get(scale, COL_WIDTH)

        # Calculate date range from all nodes
        all_dates: list[date] = [today]
        for node, _ in rows:
            if node.start:
                all_dates.append(node.start)
            if node.end:
                all_dates.append(node.end)

        if all_dates:
            self._date_start = min(all_dates) - timedelta(days=self._days_per_col * 2)
            self._date_end = max(all_dates) + timedelta(days=self._days_per_col * 4)

            # week/week2 스케일: 블록이 ISO 주(월-일)와 일치하도록 월요일 정렬
            if self._scale in ("week", "week2"):
                days_since_monday = self._date_start.weekday()  # 0=Mon, 6=Sun
                if days_since_monday != 0:
                    self._date_start -= timedelta(days=days_since_monday)
        else:
            self._date_start = today - timedelta(days=30)
            self._date_end = today + timedelta(days=60)

        # Apply scroll offset
        offset_days = scroll_offset * self._days_per_col
        self._date_start += timedelta(days=offset_days)
        self._date_end += timedelta(days=offset_days)

        total_days = (self._date_end - self._date_start).days
        self._chart_width = max(40, total_days * self._col_width // max(1, self._days_per_col))

        # Data rows only (no header offset)
        # Use max of rows and visible height so empty area gets themed bg
        self.virtual_size = Size(self._chart_width + 2, max(len(rows), self.size.height))
        self.refresh()

    def watch_scroll_x(self, old: float, new: float) -> None:
        self.post_message(self.ScrollXChanged(new))

    def watch_scroll_y(self, old: float, new: float) -> None:
        self.post_message(self.ScrollYChanged(new))

    def render_line(self, y: int) -> Strip:
        scroll_w = self.virtual_size.width if self.virtual_size.width > 0 else self.size.width
        width = max(self.size.width, scroll_w)

        # Apply vertical scroll offset (ScrollView doesn't offset y automatically)
        virtual_y = y + int(self.scroll_y)

        if not self._rows:
            if y == 0:
                text = Text("  No Gantt data", style="dim")
                return Strip(text.render(self.app.console))
            return Strip.blank(width)

        chart_w = max(20, width)

        # virtual_y maps to the data row index
        if virtual_y < 0 or virtual_y >= len(self._rows):
            # Fill empty rows with banded background instead of blank
            band = self._band_style
            base = self._base_style
            cw = self._col_width
            segments = [Segment(" ", _band_bg(c, band, base, cw)) for c in range(width)]
            return Strip(segments)

        node, depth = self._rows[virtual_y]
        return self._render_bar(node, depth, chart_w, virtual_y)

    @property
    def _is_dark(self) -> bool:
        try:
            return self.app.dark
        except Exception:
            return True

    @property
    def _band_style(self) -> Style:
        dark = self._is_dark
        try:
            _, bg = self.background_colors
            if bg.a < 0.1 or (dark and bg.brightness > 0.5) or (not dark and bg.brightness < 0.5):
                return Style(bgcolor=theme.GANTT_BAND_BG.resolve(dark))
            if dark:
                return Style(bgcolor=bg.lighten(BAND_AMOUNT).rich_color)
            else:
                return Style(bgcolor=bg.darken(BAND_AMOUNT).rich_color)
        except Exception:
            return Style(bgcolor=theme.GANTT_BAND_BG.resolve(dark))

    @property
    def _base_style(self) -> Style:
        dark = self._is_dark
        try:
            _, bg = self.background_colors
            if bg.a < 0.1 or (dark and bg.brightness > 0.5) or (not dark and bg.brightness < 0.5):
                return Style(bgcolor=theme.GANTT_BASE_BG.resolve(dark))
            return Style(bgcolor=bg.rich_color)
        except Exception:
            return Style(bgcolor=theme.GANTT_BASE_BG.resolve(dark))

    def _resolve_bg(self, c: int, band: Style, base: Style, cw: int, weekend_style: Style | None) -> Style:
        """Resolve background style for a character column, with holiday/weekend overlay."""
        bg = _band_bg(c, band, base, cw)
        # Holiday takes priority over weekend
        if self._holidays and _is_holiday_col(c, self._date_start, self._scale, cw, self._days_per_col, self._holidays):
            dark = self._is_dark
            return Style(bgcolor=theme.GANTT_HOLIDAY_BG.resolve(dark))
        if weekend_style and _is_weekend_col(c, self._date_start, self._scale, cw, self._days_per_col):
            return weekend_style
        return bg

    def _render_bar(self, node: WBSNode, depth: int, width: int, row_y: int = 0) -> Strip:
        segments: list[Segment] = []
        dark = self._is_dark
        band = self._band_style
        base = self._base_style
        cw = self._col_width
        dep_style = Style(color=theme.GANTT_DEPENDENCY_ARROW.resolve(dark))
        today_col = self._date_to_col(self._today)
        today_style = Style(color=theme.GANTT_TODAY_MARKER.resolve(dark))
        weekend_style = Style(bgcolor=theme.GANTT_WEEKEND_BG.resolve(dark))

        # Row banding: odd rows get band, even rows get base (swap roles)
        row_band = (row_y % 2 == 1)
        if row_band:
            band, base = base, band

        # Highlight style for cursor row
        highlight = (row_y == self._highlighted_row)
        if highlight:
            hl_style = Style(bgcolor=theme.GANTT_HIGHLIGHT_BG.resolve(dark))
            band = hl_style
            base = hl_style
            weekend_style = None  # highlight takes priority

        if node.milestone and node.start:
            ms_col = self._date_to_col(node.start)
            ms_style = Style(color=theme.GANTT_MILESTONE.resolve(dark), bold=True)
            for c in range(width):
                bg = self._resolve_bg(c, band, base, cw, weekend_style)
                if c == ms_col:
                    segments.append(Segment("◆", ms_style + bg))
                elif c == today_col:
                    segments.append(Segment("│", today_style + bg))
                else:
                    segments.append(Segment(" ", bg))
            return Strip(segments)

        if not node.start:
            segments = []
            for c in range(width):
                bg = self._resolve_bg(c, band, base, cw, weekend_style)
                if c == today_col:
                    segments.append(Segment("│", today_style + bg))
                else:
                    segments.append(Segment(" ", bg))
            return Strip(segments)

        start_col = self._date_to_col(node.start)
        end_date = node.end or (node.start + timedelta(days=1))
        end_col = self._date_to_col(end_date)
        bar_len = max(1, end_col - start_col)

        # Color by status
        if node.status == Status.DONE:
            bar_style = Style(color=theme.GANTT_BAR_DONE.resolve(dark))
        elif node.status == Status.IN_PROGRESS:
            bar_style = Style(color=theme.GANTT_BAR_IN_PROGRESS.resolve(dark))
        else:
            bar_style = Style(color=theme.GANTT_BAR_TODO.resolve(dark), dim=True)

        # Progress fill
        progress = node.progress or 0
        filled = int(bar_len * progress / 100) if progress else 0

        # Dependency arrow: show → before bar start
        has_deps = bool(node.depends_list)

        for c in range(width):
            bg = self._resolve_bg(c, band, base, cw, weekend_style)
            if has_deps and c == start_col - 1 and start_col > 0:
                segments.append(Segment("→", dep_style + bg))
            elif start_col <= c < start_col + bar_len:
                pos = c - start_col
                if pos < filled:
                    segments.append(Segment("█", bar_style + bg))
                else:
                    segments.append(Segment("░", bar_style + bg))
            elif c == today_col:
                segments.append(Segment("│", today_style + bg))
            else:
                segments.append(Segment(" ", bg))

        return Strip(segments)

    def _date_to_col(self, d: date) -> int:
        days = (d - self._date_start).days
        col_index = days // self._days_per_col
        base_col = col_index * self._col_width
        # Sub-column offset for week scale (1 day = 1 char within 7-char column)
        if self._scale == "week" and self._days_per_col == 7:
            day_offset = days % 7
            return max(0, base_col + day_offset)
        return max(0, base_col)
