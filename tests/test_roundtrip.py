"""Round-trip tests: parse → serialize must produce identical output."""

import pytest

from tui_wbs.parser import parse_markdown
from tui_wbs.writer import serialize_document


# A collection of markdown documents that must survive round-trip perfectly.
ROUNDTRIP_CASES = [
    # Simple case
    "# Project\n",
    # With metadata
    "# Project\n<!-- status: TODO | priority: HIGH -->\n",
    # With memo
    "# Project\n<!-- status: TODO -->\n\nProject memo here\n",
    # Multiple roots
    "# A\n\n# B\n",
    # Nested
    "# Root\n\n## Child\n\n### Grandchild\n",
    # Complex document from PRD example
    (
        "# 프로젝트명\n"
        "<!-- status: IN_PROGRESS | assignee: Gihwan | duration: 30d | priority: HIGH | start: 2026-03-01 | end: 2026-04-01 -->\n"
        "\n"
        "프로젝트 전체에 대한 메모\n"
        "\n"
        "## Phase 1: 설계\n"
        "<!-- status: TODO | assignee: Jane | duration: 5d | priority: HIGH | start: 2026-03-01 -->\n"
        "\n"
        "설계 단계 메모\n"
        "\n"
        "### Task 1.1: 요구사항 분석\n"
        "<!-- status: DONE | assignee: Jane | duration: 2d | priority: HIGH | start: 2026-03-01 | end: 2026-03-03 | depends: -->\n"
        "\n"
        "요구사항 분석 완료 메모\n"
        "\n"
        "### Task 1.2: 기술 검토\n"
        "<!-- status: IN_PROGRESS | assignee: John | duration: 3d | priority: MEDIUM | start: 2026-03-03 | depends: Task 1.1 -->\n"
        "\n"
        "### Milestone: 설계 완료\n"
        "<!-- milestone: true | start: 2026-03-06 | status: TODO | depends: Task 1.2 -->\n"
        "\n"
        "## Phase 2: 구현\n"
        "<!-- status: TODO | assignee: | duration: 20d | priority: HIGH | start: 2026-03-07 | depends: Phase 1 -->\n"
        "\n"
        "### Task 2.1: 코어 개발\n"
        "<!-- status: TODO | assignee: | duration: 10d | priority: HIGH | start: 2026-03-07 | team: Backend -->\n"
    ),
    # Empty metadata fields
    "# Task\n<!-- status: TODO | assignee:  | duration:  -->\n",
    # Special characters in title
    "# Task: Special! (chars) & more\n",
    # Unicode content
    "# 한글 프로젝트\n<!-- status: DONE | assignee: 김기환 -->\n\n한글 메모입니다.\n",
    # Trailing whitespace preservation
    "# Task\n<!-- status: TODO -->\n\n",
    # Multiple blank lines
    "# A\n\n\n\n## B\n",
]


@pytest.mark.parametrize("md", ROUNDTRIP_CASES, ids=range(len(ROUNDTRIP_CASES)))
def test_roundtrip(md):
    """Parse then serialize must produce identical output."""
    doc = parse_markdown(md, "test.md")
    result = serialize_document(doc)
    assert result == md, f"Round-trip failed:\nOriginal:\n{md!r}\nResult:\n{result!r}"


class TestRoundtripWithFile:
    """Round-trip tests using actual file I/O."""

    def test_file_roundtrip(self, tmp_path):
        from tui_wbs.parser import parse_file
        from tui_wbs.writer import write_document

        md = (
            "# Project\n"
            "<!-- status: IN_PROGRESS | assignee: Test -->\n"
            "\n"
            "Memo text\n"
            "\n"
            "## Phase 1\n"
            "<!-- status: TODO | priority: HIGH -->\n"
        )
        file_path = tmp_path / "test.wbs.md"
        file_path.write_text(md, encoding="utf-8")

        # Parse
        doc = parse_file(file_path)
        assert len(doc.root_nodes) == 1

        # Write (no modifications)
        write_document(doc, backup=False)

        # Read back and compare
        result = file_path.read_text(encoding="utf-8")
        assert result == md
