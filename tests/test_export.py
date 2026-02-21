"""Tests for export functionality (JSON and CSV)."""

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from tui_wbs.export import export_csv, export_json
from tui_wbs.models import Priority, Status, WBSDocument, WBSNode, WBSProject


@pytest.fixture
def sample_project(tmp_path):
    child = WBSNode(
        title="Task 1",
        level=2,
        status=Status.DONE,
        assignee="Alice",
        duration="3d",
        priority=Priority.HIGH,
        start=date(2026, 3, 1),
        end=date(2026, 3, 4),
        progress=100,
        memo="A memo",
        source_file="test.wbs.md",
    )
    root = WBSNode(
        title="Root",
        level=1,
        status=Status.IN_PROGRESS,
        priority=Priority.MEDIUM,
        source_file="test.wbs.md",
        children=(child,),
    )
    milestone = WBSNode(
        title="Milestone",
        level=2,
        milestone=True,
        start=date(2026, 4, 1),
        source_file="test.wbs.md",
    )
    doc = WBSDocument(
        file_path=tmp_path / "test.wbs.md",
        root_nodes=[root, milestone],
    )
    return WBSProject(dir_path=tmp_path, documents=[doc])


class TestExportJSON:
    def test_export_creates_file(self, sample_project, tmp_path):
        out = tmp_path / "out.json"
        export_json(sample_project, out)
        assert out.exists()

    def test_export_valid_json(self, sample_project, tmp_path):
        out = tmp_path / "out.json"
        export_json(sample_project, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "project_dir" in data
        assert "documents" in data
        assert len(data["documents"]) == 1

    def test_export_contains_nodes(self, sample_project, tmp_path):
        out = tmp_path / "out.json"
        export_json(sample_project, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        doc = data["documents"][0]
        assert len(doc["nodes"]) == 2  # root + milestone at root level
        root_node = doc["nodes"][0]
        assert root_node["title"] == "Root"
        assert root_node["status"] == "IN_PROGRESS"

    def test_export_children_nested(self, sample_project, tmp_path):
        out = tmp_path / "out.json"
        export_json(sample_project, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        root_node = data["documents"][0]["nodes"][0]
        assert "children" in root_node
        assert len(root_node["children"]) == 1
        child = root_node["children"][0]
        assert child["title"] == "Task 1"
        assert child["assignee"] == "Alice"
        assert child["start"] == "2026-03-01"
        assert child["end"] == "2026-03-04"
        assert child["progress"] == 100

    def test_export_milestone(self, sample_project, tmp_path):
        out = tmp_path / "out.json"
        export_json(sample_project, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        milestone = data["documents"][0]["nodes"][1]
        assert milestone["milestone"] is True
        assert milestone["start"] == "2026-04-01"


class TestExportCSV:
    def test_export_creates_file(self, sample_project, tmp_path):
        out = tmp_path / "out.csv"
        export_csv(sample_project, out)
        assert out.exists()

    def test_export_correct_headers(self, sample_project, tmp_path):
        out = tmp_path / "out.csv"
        export_csv(sample_project, out)
        with open(out, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
        expected = [
            "title", "level", "status", "priority", "assignee",
            "duration", "depends", "start", "end", "milestone",
            "progress", "memo", "source_file",
        ]
        assert headers == expected

    def test_export_correct_row_count(self, sample_project, tmp_path):
        out = tmp_path / "out.csv"
        export_csv(sample_project, out)
        with open(out, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        # Root + Task 1 + Milestone = 3 nodes
        assert len(rows) == 3

    def test_export_row_data(self, sample_project, tmp_path):
        out = tmp_path / "out.csv"
        export_csv(sample_project, out)
        with open(out, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        task_row = rows[1]  # Task 1 (child of Root)
        assert task_row["title"] == "Task 1"
        assert task_row["status"] == "DONE"
        assert task_row["assignee"] == "Alice"
        assert task_row["duration"] == "3d"
        assert task_row["start"] == "2026-03-01"
        assert task_row["end"] == "2026-03-04"

    def test_export_milestone_row(self, sample_project, tmp_path):
        out = tmp_path / "out.csv"
        export_csv(sample_project, out)
        with open(out, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        ms_row = rows[2]
        assert ms_row["milestone"] == "True"

    def test_export_memo_newlines_replaced(self, tmp_path):
        """Verify that newlines in memo are replaced with spaces."""
        node = WBSNode(
            title="Test",
            level=1,
            memo="Line 1\nLine 2\nLine 3",
            source_file="test.wbs.md",
        )
        doc = WBSDocument(file_path=tmp_path / "t.wbs.md", root_nodes=[node])
        project = WBSProject(dir_path=tmp_path, documents=[doc])
        out = tmp_path / "memo.csv"
        export_csv(project, out)
        with open(out, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            row = next(reader)
        assert "\n" not in row["memo"]
        assert "Line 1 Line 2 Line 3" == row["memo"]
