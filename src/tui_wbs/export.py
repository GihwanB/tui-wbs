"""Export WBS data to JSON, CSV, Mermaid Gantt, and Markdown table formats."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from tui_wbs.models import Status, WBSNode, WBSProject


def _node_to_dict(node: WBSNode) -> dict:
    d = {
        "id": node.id,
        "title": node.title,
        "level": node.level,
        "status": node.status.value,
        "priority": node.priority.value,
        "assignee": node.assignee,
        "duration": node.duration,
        "depends": node.depends,
        "start": node.start.isoformat() if node.start else "",
        "end": node.end.isoformat() if node.end else "",
        "milestone": node.milestone,
        "progress": node.progress,
        "memo": node.memo,
        "source_file": node.source_file,
    }
    d.update(node.custom_fields)
    if node.children:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d


def export_json(project: WBSProject, output_path: Path) -> None:
    """Export project to JSON file."""
    data = {
        "project_dir": str(project.dir_path),
        "documents": [],
    }
    for doc in project.documents:
        doc_data = {
            "file": str(doc.file_path),
            "nodes": [_node_to_dict(n) for n in doc.root_nodes],
        }
        data["documents"].append(doc_data)

    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def export_csv(project: WBSProject, output_path: Path) -> None:
    """Export project to CSV file."""
    headers = [
        "title", "level", "status", "priority", "assignee",
        "duration", "depends", "start", "end", "milestone",
        "progress", "memo", "source_file",
    ]

    rows: list[dict[str, str]] = []
    for node in project.all_nodes():
        row = {
            "title": node.title,
            "level": str(node.level),
            "status": node.status.value,
            "priority": node.priority.value,
            "assignee": node.assignee,
            "duration": node.duration,
            "depends": node.depends,
            "start": node.start.isoformat() if node.start else "",
            "end": node.end.isoformat() if node.end else "",
            "milestone": str(node.milestone),
            "progress": str(node.progress) if node.progress is not None else "",
            "memo": node.memo.replace("\n", " "),
            "source_file": node.source_file,
        }
        rows.append(row)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _mermaid_status(node: WBSNode) -> str:
    """Convert node status to Mermaid Gantt task status tag."""
    if node.status == Status.DONE:
        return "done,"
    elif node.status == Status.IN_PROGRESS:
        return "active,"
    return ""


def _safe_mermaid_id(title: str) -> str:
    """Create a safe Mermaid task ID from title."""
    return title.replace(" ", "_").replace(":", "").replace("(", "").replace(")", "")[:30]


def export_mermaid(project: WBSProject, output_path: Path) -> None:
    """Export project to Mermaid Gantt chart (.mmd) file."""
    lines: list[str] = ["gantt"]
    lines.append("    dateFormat YYYY-MM-DD")
    lines.append("")

    current_section = ""
    for node in project.all_nodes():
        # Use level-1 nodes as sections
        if node.level <= 2:
            section_title = node.title
            if section_title != current_section:
                lines.append(f"    section {section_title}")
                current_section = section_title
            if node.level == 1:
                continue  # Section header only for level 1

        status_tag = _mermaid_status(node)
        task_id = _safe_mermaid_id(node.title)

        if node.start and node.end:
            start_str = node.start.isoformat()
            end_str = node.end.isoformat()
            lines.append(f"    {node.title} :{status_tag} {task_id}, {start_str}, {end_str}")
        elif node.start and node.duration:
            start_str = node.start.isoformat()
            lines.append(f"    {node.title} :{status_tag} {task_id}, {start_str}, {node.duration}")
        elif node.start:
            start_str = node.start.isoformat()
            lines.append(f"    {node.title} :{status_tag} {task_id}, {start_str}, 1d")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_markdown_table(project: WBSProject, output_path: Path) -> None:
    """Export project to Markdown table (.md) file."""
    headers = ["Title", "Status", "Priority", "Assignee", "Duration", "Start", "End", "Progress"]
    sep = ["-" * len(h) for h in headers]

    lines: list[str] = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    for node in project.all_nodes():
        indent = "  " * (node.level - 1)
        title = f"{indent}{node.title}"
        progress_str = f"{node.progress}%" if node.progress is not None else ""
        row = [
            title,
            node.status.value,
            node.priority.value,
            node.assignee,
            node.duration,
            node.start.isoformat() if node.start else "",
            node.end.isoformat() if node.end else "",
            progress_str,
        ]
        lines.append("| " + " | ".join(row) + " |")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
