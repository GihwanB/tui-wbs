"""Markdown parser for WBS files."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tui_wbs.models import (
    ParseWarning,
    Priority,
    Status,
    WBSDocument,
    WBSNode,
    WBSProject,
)

# Regex patterns
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
META_COMMENT_RE = re.compile(r"^<!--\s*(.+?)\s*-->$")


def _parse_date(value: str, file_path: str, line_num: int, warnings: list[ParseWarning]) -> date | None:
    """Parse a YYYY-MM-DD date string."""
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        warnings.append(ParseWarning(file_path, line_num, f"Invalid date format: '{value}'"))
        return None


def _parse_status(value: str, file_path: str, line_num: int, warnings: list[ParseWarning]) -> Status:
    """Parse a status string, returning default on invalid."""
    value = value.strip().upper()
    try:
        return Status(value)
    except ValueError:
        warnings.append(ParseWarning(file_path, line_num, f"Invalid status: '{value}', defaulting to TODO"))
        return Status.TODO


def _parse_priority(value: str, file_path: str, line_num: int, warnings: list[ParseWarning]) -> Priority:
    """Parse a priority string, returning default on invalid."""
    value = value.strip().upper()
    try:
        return Priority(value)
    except ValueError:
        warnings.append(ParseWarning(file_path, line_num, f"Invalid priority: '{value}', defaulting to MEDIUM"))
        return Priority.MEDIUM


def _parse_bool(value: str) -> bool:
    """Parse a boolean metadata value."""
    return value.strip().lower() in ("true", "yes", "1")


def _parse_metadata(
    meta_str: str,
    file_path: str,
    line_num: int,
    warnings: list[ParseWarning],
    known_custom_fields: set[str] | None = None,
) -> dict[str, str]:
    """Parse '<!-- key: value | key: value -->' content into a dict."""
    result: dict[str, str] = {}
    # Split by | delimiter
    parts = meta_str.split("|")
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Split on first colon only
        colon_idx = part.find(":")
        if colon_idx == -1:
            warnings.append(ParseWarning(file_path, line_num, f"Invalid metadata field (no colon): '{part}'"))
            continue
        key = part[:colon_idx].strip().lower()
        value = part[colon_idx + 1 :].strip()
        result[key] = value
    return result


def _build_node(
    title: str,
    level: int,
    heading_line: str,
    meta_line: str | None,
    meta_dict: dict[str, str],
    body_lines: list[str],
    file_path: str,
    line_num: int,
    warnings: list[ParseWarning],
    known_custom_fields: set[str] | None = None,
) -> WBSNode:
    """Build a WBSNode from parsed components."""
    builtin_fields = {
        "status", "assignee", "duration", "priority", "depends",
        "start", "end", "milestone", "progress",
    }

    status = _parse_status(meta_dict.get("status", "TODO"), file_path, line_num, warnings)
    priority = _parse_priority(meta_dict.get("priority", "MEDIUM"), file_path, line_num, warnings)
    start = _parse_date(meta_dict.get("start", ""), file_path, line_num, warnings)
    end = _parse_date(meta_dict.get("end", ""), file_path, line_num, warnings)
    milestone = _parse_bool(meta_dict.get("milestone", "false"))

    progress_str = meta_dict.get("progress", "").strip()
    progress: int | None = None
    if progress_str:
        try:
            progress = max(0, min(100, int(progress_str)))
        except ValueError:
            warnings.append(ParseWarning(file_path, line_num, f"Invalid progress: '{progress_str}'"))

    # Collect custom fields
    custom_fields: dict[str, str] = {}
    for key, value in meta_dict.items():
        if key not in builtin_fields:
            if known_custom_fields and key in known_custom_fields:
                custom_fields[key] = value
            elif known_custom_fields is not None:
                # Unknown field — preserve raw but warn
                custom_fields[key] = value
            else:
                custom_fields[key] = value

    # Memo: body text excluding empty leading/trailing lines that are structural
    memo = "\n".join(body_lines).strip()

    return WBSNode(
        title=title,
        level=level,
        status=status,
        assignee=meta_dict.get("assignee", "").strip(),
        duration=meta_dict.get("duration", "").strip(),
        priority=priority,
        depends=meta_dict.get("depends", "").strip(),
        start=start,
        end=end,
        milestone=milestone,
        progress=progress,
        memo=memo,
        custom_fields=custom_fields,
        source_file=file_path,
        _raw_heading_line=heading_line,
        _raw_meta_line=meta_line,
        _raw_body_lines=tuple(body_lines),
        _meta_modified=False,
    )


def parse_markdown(content: str, file_path: str, known_custom_fields: set[str] | None = None) -> WBSDocument:
    """Parse a markdown string into a WBSDocument."""
    warnings: list[ParseWarning] = []
    lines = content.split("\n")

    # Collect sections: each section starts with a heading
    sections: list[dict] = []  # {line_num, level, title, heading_line, meta_line, meta_dict, body_lines}
    current_section: dict | None = None

    for i, line in enumerate(lines):
        heading_match = HEADING_RE.match(line)
        if heading_match:
            # Save previous section
            if current_section is not None:
                sections.append(current_section)

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_section = {
                "line_num": i + 1,
                "level": level,
                "title": title,
                "heading_line": line,
                "meta_line": None,
                "meta_dict": {},
                "body_lines": [],
                "meta_found": False,
            }
        elif current_section is not None:
            # Check for metadata comment (only first one after heading)
            meta_match = META_COMMENT_RE.match(line.strip())
            if meta_match and not current_section["meta_found"]:
                current_section["meta_line"] = line
                current_section["meta_found"] = True
                current_section["meta_dict"] = _parse_metadata(
                    meta_match.group(1),
                    file_path,
                    i + 1,
                    warnings,
                    known_custom_fields,
                )
            else:
                current_section["body_lines"].append(line)

    # Don't forget last section
    if current_section is not None:
        sections.append(current_section)

    if not sections:
        warnings.append(ParseWarning(file_path, 0, "No headings found in file"))
        return WBSDocument(
            file_path=Path(file_path),
            root_nodes=[],
            raw_content=content,
            parse_warnings=warnings,
        )

    # Build nodes
    nodes: list[WBSNode] = []
    for sec in sections:
        node = _build_node(
            title=sec["title"],
            level=sec["level"],
            heading_line=sec["heading_line"],
            meta_line=sec["meta_line"],
            meta_dict=sec["meta_dict"],
            body_lines=sec["body_lines"],
            file_path=file_path,
            line_num=sec["line_num"],
            warnings=warnings,
            known_custom_fields=known_custom_fields,
        )
        nodes.append(node)

    # Build tree from flat list
    root_nodes = _build_tree(nodes, file_path, warnings)

    return WBSDocument(
        file_path=Path(file_path),
        root_nodes=root_nodes,
        raw_content=content,
        parse_warnings=warnings,
    )


def _build_tree(
    flat_nodes: list[WBSNode],
    file_path: str,
    warnings: list[ParseWarning],
) -> list[WBSNode]:
    """Build a tree structure from a flat list of nodes based on heading levels.

    Handles heading level skipping by attaching to the nearest ancestor.
    """
    if not flat_nodes:
        return []

    root_nodes: list[WBSNode] = []
    # Stack of (node, level) — tracks current ancestry path
    stack: list[tuple[WBSNode, int]] = []

    for node in flat_nodes:
        level = node.level

        # Find the right parent: pop stack until we find a node with level < current
        while stack and stack[-1][1] >= level:
            stack.pop()

        if not stack:
            # This is a root-level node
            root_nodes.append(node)
            stack.append((node, level))
        else:
            # Check for level skipping
            parent_node, parent_level = stack[-1]
            if level > parent_level + 1:
                warnings.append(ParseWarning(
                    file_path,
                    0,
                    f"Heading level skip: h{parent_level} -> h{level} for '{node.title}', "
                    f"attaching to '{parent_node.title}'",
                ))

            # Attach as child of the node at top of stack
            updated_parent = parent_node.with_child(node)

            # Update the parent in the stack
            stack[-1] = (updated_parent, parent_level)

            # Also update the parent reference in its own parent or root_nodes
            _propagate_update(stack, root_nodes, updated_parent, parent_node.id)

            # Push current node onto stack
            stack.append((node, level))

    return root_nodes


def _propagate_update(
    stack: list[tuple[WBSNode, int]],
    root_nodes: list[WBSNode],
    updated_node: WBSNode,
    old_id: str,
) -> None:
    """Propagate a node update through the ancestry chain."""
    current = updated_node
    current_id = old_id

    # Walk up the stack from second-to-last to first
    for i in range(len(stack) - 2, -1, -1):
        parent, parent_level = stack[i]
        updated_parent = parent.replace_child(current_id, current)
        stack[i] = (updated_parent, parent_level)
        current_id = parent.id
        current = updated_parent

    # Update root_nodes if the top of the chain is a root
    for i, root in enumerate(root_nodes):
        if root.id == current_id:
            root_nodes[i] = current
            break


def _is_binary(content: bytes) -> bool:
    """Check if content appears to be binary."""
    # Check for null bytes in first 8192 bytes
    return b"\x00" in content[:8192]


def parse_file(file_path: Path, known_custom_fields: set[str] | None = None) -> WBSDocument:
    """Parse a single .wbs.md file."""
    warnings: list[ParseWarning] = []
    str_path = str(file_path)

    try:
        raw_bytes = file_path.read_bytes()
    except OSError as e:
        warnings.append(ParseWarning(str_path, 0, f"Cannot read file: {e}"))
        return WBSDocument(file_path=file_path, parse_warnings=warnings)

    if _is_binary(raw_bytes):
        warnings.append(ParseWarning(str_path, 0, "File appears to be binary, skipping"))
        return WBSDocument(file_path=file_path, parse_warnings=warnings)

    try:
        content = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        warnings.append(ParseWarning(str_path, 0, "File is not valid UTF-8, skipping"))
        return WBSDocument(file_path=file_path, parse_warnings=warnings)

    return parse_markdown(content, str_path, known_custom_fields)


def parse_project(dir_path: Path, known_custom_fields: set[str] | None = None) -> WBSProject:
    """Parse all .wbs.md files in a directory into a WBSProject."""
    project = WBSProject(dir_path=dir_path)

    wbs_files = sorted(dir_path.glob("*.wbs.md"))
    if not wbs_files:
        project.parse_warnings.append(
            ParseWarning(str(dir_path), 0, "No .wbs.md files found in directory")
        )
        return project

    for file_path in wbs_files:
        doc = parse_file(file_path, known_custom_fields)
        project.documents.append(doc)
        project.parse_warnings.extend(doc.parse_warnings)

    # Validate depends references
    _validate_depends(project)

    return project


def _validate_depends(project: WBSProject) -> None:
    """Validate depends references and detect cycles."""
    all_nodes = project.all_nodes()
    title_set = {node.title for node in all_nodes}

    # Check for duplicate titles
    seen_titles: dict[str, int] = {}
    for node in all_nodes:
        if node.title in seen_titles:
            seen_titles[node.title] += 1
        else:
            seen_titles[node.title] = 1

    for title, count in seen_titles.items():
        if count > 1:
            project.parse_warnings.append(
                ParseWarning("", 0, f"Duplicate title '{title}' found {count} times, depends may be ambiguous")
            )

    # Check for invalid depends references
    for node in all_nodes:
        for dep_title in node.depends_list:
            if dep_title not in title_set:
                project.parse_warnings.append(
                    ParseWarning(
                        node.source_file,
                        0,
                        f"Node '{node.title}' depends on '{dep_title}' which does not exist",
                    )
                )

    # Check for circular dependencies (simple DFS)
    title_to_deps: dict[str, list[str]] = {}
    for node in all_nodes:
        title_to_deps[node.title] = node.depends_list

    visited: set[str] = set()
    rec_stack: set[str] = set()

    def has_cycle(title: str) -> bool:
        visited.add(title)
        rec_stack.add(title)
        for dep in title_to_deps.get(title, []):
            if dep not in visited:
                if has_cycle(dep):
                    return True
            elif dep in rec_stack:
                project.parse_warnings.append(
                    ParseWarning("", 0, f"Circular dependency detected involving '{title}' -> '{dep}'")
                )
                return True
        rec_stack.discard(title)
        return False

    for title in title_to_deps:
        if title not in visited:
            has_cycle(title)
