"""Tests for Markdown parser."""

from datetime import date
from pathlib import Path

import pytest

from tui_wbs.models import Priority, Status
from tui_wbs.parser import parse_file, parse_markdown, parse_project


class TestBasicParsing:
    def test_single_heading(self):
        md = "# Project\n"
        doc = parse_markdown(md, "test.md")
        assert len(doc.root_nodes) == 1
        assert doc.root_nodes[0].title == "Project"
        assert doc.root_nodes[0].level == 1

    def test_multiple_h1(self):
        md = "# Project A\n\n# Project B\n"
        doc = parse_markdown(md, "test.md")
        assert len(doc.root_nodes) == 2
        assert doc.root_nodes[0].title == "Project A"
        assert doc.root_nodes[1].title == "Project B"

    def test_nested_headings(self):
        md = "# Root\n\n## Child 1\n\n## Child 2\n\n### Grandchild\n"
        doc = parse_markdown(md, "test.md")
        assert len(doc.root_nodes) == 1
        root = doc.root_nodes[0]
        assert len(root.children) == 2
        assert root.children[0].title == "Child 1"
        assert root.children[1].title == "Child 2"
        assert len(root.children[1].children) == 1
        assert root.children[1].children[0].title == "Grandchild"

    def test_deep_nesting(self):
        md = "# L1\n## L2\n### L3\n#### L4\n##### L5\n###### L6\n"
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        for i in range(5):
            assert len(node.children) == 1
            node = node.children[0]
        assert node.title == "L6"


class TestMetadataParsing:
    def test_basic_metadata(self):
        md = (
            "# Task\n"
            "| status | assignee | duration | priority |\n"
            "| --- | --- | --- | --- |\n"
            "| DONE | Jane | 5d | HIGH |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.status == Status.DONE
        assert node.assignee == "Jane"
        assert node.duration == "5d"
        assert node.priority == Priority.HIGH

    def test_date_fields(self):
        md = (
            "# Task\n"
            "| start | end |\n"
            "| --- | --- |\n"
            "| 2026-03-01 | 2026-03-15 |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.start == date(2026, 3, 1)
        assert node.end == date(2026, 3, 15)

    def test_milestone(self):
        md = (
            "# MS\n"
            "| milestone | start |\n"
            "| --- | --- |\n"
            "| true | 2026-04-01 |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.milestone is True
        assert node.start == date(2026, 4, 1)

    def test_depends_semicolon(self):
        md = (
            "# Task\n"
            "| depends |\n"
            "| --- |\n"
            "| Task A; Task B |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.depends == "Task A; Task B"
        assert node.depends_list == ["Task A", "Task B"]

    def test_progress(self):
        md = (
            "# Task\n"
            "| progress |\n"
            "| --- |\n"
            "| 75 |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].progress == 75

    def test_custom_fields(self):
        md = (
            "# Task\n"
            "| team | risk |\n"
            "| --- | --- |\n"
            "| Backend | High |\n"
        )
        doc = parse_markdown(md, "test.md", known_custom_fields={"team", "risk"})
        node = doc.root_nodes[0]
        assert node.custom_fields["team"] == "Backend"
        assert node.custom_fields["risk"] == "High"


class TestMemo:
    def test_memo_parsing(self):
        md = (
            "# Task\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
            "\n"
            "This is a memo\n"
            "Second line\n"
            "\n"
            "## Next\n"
        )
        doc = parse_markdown(md, "test.md")
        assert "This is a memo" in doc.root_nodes[0].memo
        assert "Second line" in doc.root_nodes[0].memo

    def test_no_memo(self):
        md = (
            "# Task\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
            "## Next\n"
        )
        doc = parse_markdown(md, "test.md")
        # Memo might have empty lines between heading and next heading
        assert doc.root_nodes[0].memo.strip() == ""


class TestEdgeCases:
    def test_no_metadata(self):
        md = "# Task\n\nSome text\n"
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.status == Status.TODO
        assert node.priority == Priority.MEDIUM
        assert node._raw_meta_lines == ()

    def test_invalid_status(self):
        md = (
            "# Task\n"
            "| status |\n"
            "| --- |\n"
            "| PENDING |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].status == Status.TODO
        assert any("Invalid status" in str(w) for w in doc.parse_warnings)

    def test_invalid_priority(self):
        md = (
            "# Task\n"
            "| priority |\n"
            "| --- |\n"
            "| CRITICAL |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].priority == Priority.MEDIUM
        assert any("Invalid priority" in str(w) for w in doc.parse_warnings)

    def test_invalid_date(self):
        md = (
            "# Task\n"
            "| start |\n"
            "| --- |\n"
            "| not-a-date |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].start is None
        assert any("Invalid date" in str(w) for w in doc.parse_warnings)

    def test_empty_assignee(self):
        md = (
            "# Task\n"
            "| assignee |\n"
            "| --- |\n"
            "|  |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].assignee == ""

    def test_special_chars_in_value(self):
        md = (
            "# Task\n"
            "| assignee |\n"
            "| --- |\n"
            "| John O'Brien |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].assignee == "John O'Brien"

    def test_heading_level_skip(self):
        md = "# Root\n### Skipped\n"
        doc = parse_markdown(md, "test.md")
        root = doc.root_nodes[0]
        assert len(root.children) == 1
        assert root.children[0].title == "Skipped"
        assert any("level skip" in str(w).lower() for w in doc.parse_warnings)

    def test_no_headings(self):
        md = "Just some text\nNo headings here\n"
        doc = parse_markdown(md, "test.md")
        assert len(doc.root_nodes) == 0
        assert any("No headings" in str(w) for w in doc.parse_warnings)

    def test_empty_file(self):
        md = ""
        doc = parse_markdown(md, "test.md")
        assert len(doc.root_nodes) == 0

    def test_only_metadata_after_heading(self):
        """Only the first metadata table is parsed."""
        md = (
            "# Task\n"
            "| status |\n"
            "| --- |\n"
            "| DONE |\n"
            "| priority |\n"
            "| --- |\n"
            "| HIGH |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.status == Status.DONE
        # Second table should not be parsed as metadata
        assert node.priority == Priority.MEDIUM  # default

    def test_metadata_with_blank_line_after_heading(self):
        """Table after blank line should still be parsed."""
        md = (
            "# Task\n"
            "\n"
            "| status |\n"
            "| --- |\n"
            "| DONE |\n"
        )
        doc = parse_markdown(md, "test.md")
        node = doc.root_nodes[0]
        assert node.status == Status.DONE

    def test_progress_clamped(self):
        md = (
            "# Task\n"
            "| progress |\n"
            "| --- |\n"
            "| 150 |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].progress == 100

    def test_progress_negative(self):
        md = (
            "# Task\n"
            "| progress |\n"
            "| --- |\n"
            "| -10 |\n"
        )
        doc = parse_markdown(md, "test.md")
        assert doc.root_nodes[0].progress == 0


class TestDependsValidation:
    def test_invalid_depends_reference(self):
        md = (
            "# Task A\n"
            "| depends |\n"
            "| --- |\n"
            "| NonExistent |\n"
            "# Task B\n"
        )
        doc = parse_markdown(md, "test.md")
        # We need to use parse_project for depends validation
        from tui_wbs.models import WBSProject
        project = WBSProject(dir_path=Path("."), documents=[doc])
        from tui_wbs.parser import _validate_depends
        _validate_depends(project)
        assert any("does not exist" in str(w) for w in project.parse_warnings)

    def test_duplicate_titles_warning(self):
        md = "# Same\n\n# Same\n"
        doc = parse_markdown(md, "test.md")
        from tui_wbs.models import WBSProject
        project = WBSProject(dir_path=Path("."), documents=[doc])
        from tui_wbs.parser import _validate_depends
        _validate_depends(project)
        assert any("Duplicate title" in str(w) for w in project.parse_warnings)

    def test_circular_dependency(self):
        md = (
            "# A\n"
            "| depends |\n"
            "| --- |\n"
            "| B |\n"
            "# B\n"
            "| depends |\n"
            "| --- |\n"
            "| A |\n"
        )
        doc = parse_markdown(md, "test.md")
        from tui_wbs.models import WBSProject
        project = WBSProject(dir_path=Path("."), documents=[doc])
        from tui_wbs.parser import _validate_depends
        _validate_depends(project)
        assert any("Circular" in str(w) for w in project.parse_warnings)


class TestBinaryFile:
    def test_binary_detection(self, tmp_path):
        binary_file = tmp_path / "test.wbs.md"
        binary_file.write_bytes(b"\x00\x01\x02binary content")
        doc = parse_file(binary_file)
        assert any("binary" in str(w).lower() for w in doc.parse_warnings)
        assert len(doc.root_nodes) == 0


class TestParseProject:
    def test_parse_empty_dir(self, tmp_path):
        project = parse_project(tmp_path)
        assert len(project.documents) == 0
        assert any("No .wbs.md files" in str(w) for w in project.parse_warnings)

    def test_parse_multiple_files(self, tmp_path):
        (tmp_path / "a.wbs.md").write_text("# File A\n", encoding="utf-8")
        (tmp_path / "b.wbs.md").write_text("# File B\n", encoding="utf-8")
        project = parse_project(tmp_path)
        assert len(project.documents) == 2
        titles = {doc.root_nodes[0].title for doc in project.documents}
        assert titles == {"File A", "File B"}

    def test_non_wbs_files_ignored(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Not WBS\n", encoding="utf-8")
        (tmp_path / "project.wbs.md").write_text("# WBS\n", encoding="utf-8")
        project = parse_project(tmp_path)
        assert len(project.documents) == 1
        assert project.documents[0].root_nodes[0].title == "WBS"
