"""Tests for Markdown writer."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from tui_wbs.models import Priority, Status, WBSDocument, WBSNode
from tui_wbs.parser import parse_markdown
from tui_wbs.writer import serialize_document, write_document


class TestSerializeUnmodified:
    """Test that unmodified documents are serialized identically (round-trip)."""

    def test_no_change(self):
        md = (
            "# Project\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
            "\n"
            "Some memo\n"
        )
        doc = parse_markdown(md, "test.md")
        assert serialize_document(doc) == md

    def test_preserves_whitespace(self):
        md = (
            "# Project\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
            "\n"
            "\n"
            "Double blank\n"
        )
        doc = parse_markdown(md, "test.md")
        assert serialize_document(doc) == md

    def test_complex_document(self):
        md = (
            "# Root\n"
            "| status | assignee | priority |\n"
            "| --- | --- | --- |\n"
            "| IN_PROGRESS | Gihwan | HIGH |\n"
            "\n"
            "Root memo\n"
            "\n"
            "## Child 1\n"
            "| status | assignee |\n"
            "| --- | --- |\n"
            "| DONE | Jane |\n"
            "\n"
            "Child memo\n"
            "\n"
            "### Grandchild\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
            "\n"
            "## Child 2\n"
        )
        doc = parse_markdown(md, "test.md")
        assert serialize_document(doc) == md


class TestSerializeModified:
    def test_modified_node_generates_meta(self):
        md = "# Task\n"
        doc = parse_markdown(md, "test.md")
        doc.modified = True

        # Modify the node
        node = doc.root_nodes[0]
        updated = replace(node, status=Status.DONE, _meta_modified=True)
        doc.root_nodes[0] = updated

        result = serialize_document(doc)
        assert "| status |" in result
        assert "| DONE |" in result
        assert "# Task" in result

    def test_modified_preserves_custom_fields(self):
        md = (
            "# Task\n"
            "| team |\n"
            "| --- |\n"
            "| Backend |\n"
        )
        doc = parse_markdown(md, "test.md")
        doc.modified = True

        node = doc.root_nodes[0]
        updated = replace(
            node,
            status=Status.IN_PROGRESS,
            custom_fields={"team": "Backend"},
            _meta_modified=True,
        )
        doc.root_nodes[0] = updated

        result = serialize_document(doc)
        assert "team" in result
        assert "Backend" in result
        assert "IN_PROGRESS" in result


class TestWriteDocument:
    def test_write_creates_file(self, tmp_path):
        md = (
            "# Test\n"
            "| status |\n"
            "| --- |\n"
            "| TODO |\n"
        )
        doc = parse_markdown(md, str(tmp_path / "test.wbs.md"))
        doc.file_path = tmp_path / "test.wbs.md"
        doc.modified = False  # No actual changes

        write_document(doc, backup=False)
        assert (tmp_path / "test.wbs.md").exists()
        assert (tmp_path / "test.wbs.md").read_text(encoding="utf-8") == md

    def test_write_creates_backup(self, tmp_path):
        target = tmp_path / "test.wbs.md"
        target.write_text("original", encoding="utf-8")

        doc = WBSDocument(file_path=target, raw_content="updated")
        write_document(doc, backup=True)

        assert target.read_text(encoding="utf-8") == "updated"
        bak = tmp_path / "test.wbs.md.bak"
        assert bak.exists()
        assert bak.read_text(encoding="utf-8") == "original"

    def test_atomic_write(self, tmp_path):
        """Test that write is atomic (no partial writes)."""
        target = tmp_path / "test.wbs.md"
        target.write_text("original", encoding="utf-8")

        doc = WBSDocument(file_path=target, raw_content="new content")
        write_document(doc, backup=False)

        assert target.read_text(encoding="utf-8") == "new content"
        # No temp files should remain
        tmp_files = list(tmp_path.glob(".tui-wbs-*"))
        assert len(tmp_files) == 0
