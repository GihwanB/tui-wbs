"""Round-trip tests: parse → serialize must produce identical output."""

import pytest

from tui_wbs.parser import parse_markdown
from tui_wbs.writer import serialize_document


# A collection of markdown documents that must survive round-trip perfectly.
ROUNDTRIP_CASES = [
    # Simple case
    "# Project\n",
    # With metadata
    (
        "# Project\n"
        "| status | priority |\n"
        "| --- | --- |\n"
        "| TODO | HIGH |\n"
    ),
    # With memo
    (
        "# Project\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n"
        "\n"
        "Project memo here\n"
    ),
    # Multiple roots
    "# A\n\n# B\n",
    # Nested
    "# Root\n\n## Child\n\n### Grandchild\n",
    # Complex document from PRD example
    (
        "# 프로젝트명\n"
        "| status | assignee | duration | priority | start | end |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| IN_PROGRESS | Gihwan | 30d | HIGH | 2026-03-01 | 2026-04-01 |\n"
        "\n"
        "프로젝트 전체에 대한 메모\n"
        "\n"
        "## Phase 1: 설계\n"
        "| status | assignee | duration | priority | start |\n"
        "| --- | --- | --- | --- | --- |\n"
        "| TODO | Jane | 5d | HIGH | 2026-03-01 |\n"
        "\n"
        "설계 단계 메모\n"
        "\n"
        "### Task 1.1: 요구사항 분석\n"
        "| status | assignee | duration | priority | start | end | depends |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n"
        "| DONE | Jane | 2d | HIGH | 2026-03-01 | 2026-03-03 |  |\n"
        "\n"
        "요구사항 분석 완료 메모\n"
        "\n"
        "### Task 1.2: 기술 검토\n"
        "| status | assignee | duration | priority | start | depends |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| IN_PROGRESS | John | 3d | MEDIUM | 2026-03-03 | Task 1.1 |\n"
        "\n"
        "### Milestone: 설계 완료\n"
        "| milestone | start | status | depends |\n"
        "| --- | --- | --- | --- |\n"
        "| true | 2026-03-06 | TODO | Task 1.2 |\n"
        "\n"
        "## Phase 2: 구현\n"
        "| status | assignee | duration | priority | start | depends |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| TODO |  | 20d | HIGH | 2026-03-07 | Phase 1 |\n"
        "\n"
        "### Task 2.1: 코어 개발\n"
        "| status | assignee | duration | priority | start | team |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| TODO |  | 10d | HIGH | 2026-03-07 | Backend |\n"
    ),
    # Empty metadata fields
    (
        "# Task\n"
        "| status | assignee | duration |\n"
        "| --- | --- | --- |\n"
        "| TODO |  |  |\n"
    ),
    # Special characters in title
    "# Task: Special! (chars) & more\n",
    # Unicode content
    (
        "# 한글 프로젝트\n"
        "| status | assignee |\n"
        "| --- | --- |\n"
        "| DONE | 김기환 |\n"
        "\n"
        "한글 메모입니다.\n"
    ),
    # Trailing whitespace preservation
    (
        "# Task\n"
        "| status |\n"
        "| --- |\n"
        "| TODO |\n"
        "\n"
    ),
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
            "| status | assignee |\n"
            "| --- | --- |\n"
            "| IN_PROGRESS | Test |\n"
            "\n"
            "Memo text\n"
            "\n"
            "## Phase 1\n"
            "| status | priority |\n"
            "| --- | --- |\n"
            "| TODO | HIGH |\n"
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
