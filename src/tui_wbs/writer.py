"""Markdown writer for WBS files — round-trip preserving."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from tui_wbs.models import WBSDocument, WBSNode


def _build_meta_comment(node: WBSNode) -> str:
    """Build a metadata HTML comment string from a node."""
    parts: list[str] = []

    parts.append(f"status: {node.status.value}")

    if node.milestone:
        parts.append("milestone: true")

    if node.assignee:
        parts.append(f"assignee: {node.assignee}")

    if node.duration:
        parts.append(f"duration: {node.duration}")

    parts.append(f"priority: {node.priority.value}")

    if node.start:
        parts.append(f"start: {node.start.isoformat()}")

    if node.end:
        parts.append(f"end: {node.end.isoformat()}")

    if node.depends:
        parts.append(f"depends: {node.depends}")

    if node.progress is not None:
        parts.append(f"progress: {node.progress}")

    for key, value in sorted(node.custom_fields.items()):
        parts.append(f"{key}: {value}")

    return "<!-- " + " | ".join(parts) + " -->"


def _serialize_node(node: WBSNode, lines: list[str]) -> None:
    """Serialize a single node and its children to lines.

    Round-trip strategy:
    - If node is not modified (_meta_modified=False), use raw lines exactly as parsed.
    - If node is modified, regenerate the metadata comment.
    """
    if not node._meta_modified:
        # Round-trip: output raw lines exactly as they were
        lines.append(node._raw_heading_line)
        if node._raw_meta_line is not None:
            lines.append(node._raw_meta_line)
        for body_line in node._raw_body_lines:
            lines.append(body_line)
    else:
        # Modified node: regenerate heading and metadata
        heading_prefix = "#" * node.level
        lines.append(f"{heading_prefix} {node.title}")
        lines.append(_build_meta_comment(node))

        # Memo as body
        if node.memo:
            lines.append("")
            for memo_line in node.memo.split("\n"):
                lines.append(memo_line)
            lines.append("")
        else:
            lines.append("")

    # Recurse into children
    for child in node.children:
        _serialize_node(child, lines)


def serialize_document(doc: WBSDocument) -> str:
    """Serialize a WBSDocument back to markdown string.

    If no modifications were made, returns the original raw_content for byte-perfect
    round-trip.
    """
    if not doc.modified:
        return doc.raw_content

    lines: list[str] = []
    for root in doc.root_nodes:
        _serialize_node(root, lines)

    # Join with newline, preserve trailing newline if original had one
    result = "\n".join(lines)
    if doc.raw_content.endswith("\n") and not result.endswith("\n"):
        result += "\n"
    return result


def write_document(doc: WBSDocument, backup: bool = True) -> None:
    """Write a WBSDocument to its file path with backup and atomic write.

    1. Create .bak backup of current file (if it exists)
    2. Write to a temp file in the same directory
    3. Atomic rename (os.replace) temp -> target
    """
    target = doc.file_path
    content = serialize_document(doc)

    # Backup existing file
    if backup and target.exists():
        bak_path = target.with_suffix(target.suffix + ".bak")
        try:
            bak_path.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
        except OSError:
            pass  # Best effort backup

    # Atomic write: temp file → rename
    target_dir = target.parent
    target_dir.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp", prefix=".tui-wbs-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except BaseException:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    doc.modified = False


def write_project(project: "WBSProject", backup: bool = True) -> None:
    """Write all modified documents in a project."""
    from tui_wbs.models import WBSProject

    for doc in project.documents:
        if doc.modified:
            write_document(doc, backup=backup)
