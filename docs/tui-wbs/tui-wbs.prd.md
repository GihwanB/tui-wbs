# Document Info

| 항목 | 내용 |
|------|------|
| 문서명 | TUI WBS - Terminal UI Work Breakdown Structure Tool |
| 작성자 | Gihwan Kim |
| 작성일 | 2026-02-19 |

## 변경 이력

| 버전 | 수정일 | 수정자 | 변경 내용 |
|------|--------|--------|-----------|
| 1.0 | 2026-02-19 | Gihwan Kim | 최초 작성 |
| 1.1 | 2026-02-19 | Gihwan Kim | 리뷰 결과 반영: 데이터 안전성, depends 명세, 파싱 엣지케이스, UX 접근성 |
| 2.0 | 2026-02-20 | Gihwan Kim | 전면 개편: 폴더 기반 프로젝트, 뷰 시스템 (Table/Gantt/Kanban), 마일스톤, 칼럼 커스터마이징, 설정 화면, Deep 리뷰 P0/P1 보완 |

---

## Executive Summary

| 항목 | 내용 |
|------|------|
| **한 줄 요약** | 폴더 기반 Markdown WBS를 Table·Gantt·Kanban 뷰로 관리하는 TUI 프로젝트 관리 도구 |
| **핵심 기능** | 멀티 MD 파싱/저장, Table 뷰, Gantt 차트, Kanban 보드, 커스텀 뷰·필터·칼럼, 마일스톤, 설정 화면 |
| **영향 범위** | CLI Application (standalone) |
| **의존성** | Python 3.12+, Textual 8.x, Click 8.x, tomlkit, python-dateutil |
| **복잡도** | High |
| **우선순위** | P0 |

---

## Overview

프로젝트 관리에서 WBS(Work Breakdown Structure)를 Markdown 파일로 작성·관리하되, 터미널에서 Table·Gantt·Kanban 등 다양한 뷰로 시각화하고 직관적으로 편집할 수 있는 TUI 도구를 개발한다.

**현재 상태 (As-Is)**:
- 텍스트 에디터로 MD 파일을 수동 편집 → 구조적 시각화 불가
- GUI 도구 (Jira, Asana) → 터미널 워크플로우와 단절, 오버헤드
- 기존 TUI 도구 (beads_viewer, taskwarrior-tui) → Go/Rust 의존성, 별도 DB 필요, MD 호환 불가

**대상 사용자**: 터미널 환경에서 프로젝트 작업 분해 구조를 빠르게 관리하고 싶은 개발자/PM

**핵심 가치**:
- MD 파일을 사람이 읽기 좋은 형태로 유지하면서도 TUI에서 구조적으로 편집 가능
- 기존 MD 편집기/뷰어와 호환되는 포맷 (HTML 주석으로 메타데이터 저장)
- GitHub Projects 수준의 뷰 관리 (Table, Gantt, Kanban + 커스텀 뷰)
- vim-style 키바인딩으로 빠른 조작
- 폴더 기반 프로젝트로 대규모 WBS를 파일별로 분할 관리

---

## Core Features

### F1. 프로젝트 관리 (폴더 기반)
- 폴더 단위로 프로젝트 열기: `cd my-project && tui-wbs`
- 폴더 내 모든 `*.wbs.md` 파일 자동 탐지 및 로딩
- 파일별 분할 관리: 용도에 따라 여러 MD 파일로 WBS 분리
- 각 파일의 루트 노드(h1)들이 프로젝트 트리의 최상위 노드로 통합
- 파일 소속 추적: 노드가 어느 파일에 속하는지 내부 관리 → 저장 시 원본 파일로 복원
- 프로젝트 설정: `.tui-wbs/config.toml`에 뷰/필터/칼럼 설정 저장

### F2. Markdown 파싱 및 저장
- `#` 헤딩 레벨 = 트리 깊이 (h1=루트, h2=1depth, h3=2depth, ...)
- 복수 h1 헤딩 허용 (다중 루트 트리)
- HTML 주석(`<!-- -->`)으로 메타데이터 파싱/저장
- 헤딩 아래 본문 텍스트 = 메모
- round-trip 보장: 읽고 → 수정 없이 저장 시 원본과 동일 (공백, 빈 줄 포함)
- 메타데이터 미수정 노드: 원본 그대로 보존 (주석 자동 추가하지 않음)
- 메타데이터 수정된 노드: 변경된 필드 포함 주석 생성/갱신
- 저장 시 `.bak` 백업 자동 생성 + atomic write (temp 파일 → rename)
- 파싱 검증: 알 수 없는 필드/값은 경고 후 기본값 적용, 원본 보존
- 헤딩 레벨 건너뛰기 처리: h1 → h3 (h2 없이) 시 가장 가까운 상위 레벨의 자식으로 배치 + 파싱 경고
- 유효하지 않은 파일 감지: 바이너리 파일, 헤딩 없는 MD → 에러 메시지 표시

### F3. 뷰 시스템 (GitHub Projects 스타일)
- **뷰 타입**: Table, Table + Gantt, Kanban Board
- **뷰 관리**: 뷰 추가/이름 변경/삭제/복제
- **뷰별 독립 설정**: 각 뷰마다 타입, 표시 칼럼, 필터, 정렬, 그룹핑 독립 저장
- **뷰 전환**: 탭 바 + 키바인딩으로 빠른 전환
- **영속성**: 모든 뷰 설정은 `.tui-wbs/config.toml`에 저장, 재실행 시 복원
- 기본 뷰: 최초 실행 시 "Table" 뷰 1개 자동 생성

### F4. Table 뷰
- Textual `DataTable` 위젯 기반
- 노드별 상태 아이콘: `○` TODO, `◐` IN_PROGRESS, `●` DONE
- 우선순위 아이콘+색상 (접근성 고려, 아이콘 중복 없음):
  - `◆` HIGH (빨강), `▲` MEDIUM (노랑), `▽` LOW (초록)
- 마일스톤 아이콘: `◇` (보라)
- 의존 노드 미완료 시 잠금 아이콘 `🔒` 표시
- 트리 들여쓰기로 계층 구조 표현
- 칼럼 정렬 (클릭 또는 키바인딩)
- 접기/펼치기

### F5. Gantt 차트
- Table + Gantt 병렬 레이아웃 (좌: Table, 우: Gantt 타임라인)
- **시간 축 스케일**: Day, Week, Month, Quarter, Year (키바인딩으로 전환)
- **WBS 레벨 필터링**: 표시할 깊이 선택 (Level 1 = h2까지, Level 2 = h3까지, ...)
- Gantt 바: 시작일~종료일 구간 표시 (Unicode 블록 문자 `█▓░`)
- 마일스톤: `◆` 다이아몬드로 특정 날짜에 표시
- 의존성 관계: 화살표(`→`) 또는 색상으로 시각적 연결
- 오늘 날짜 기준선 표시
- 진행률: Gantt 바 내부에 완료 비율 시각화
- 스크롤: 가로 스크롤로 타임라인 탐색
- 커스텀 Textual Widget으로 구현 (기존 TUI Gantt 라이브러리 없음)

### F6. Kanban 보드
- 상태별 칼럼 레이아웃: TODO | IN_PROGRESS | DONE
- 카드에 제목, 우선순위, 담당자 표시
- 카드 이동: 키바인딩으로 칼럼 간 이동 (상태 자동 변경)
- 카드 순서 변경
- WBS 레벨 필터링 지원
- 그룹핑 기준 변경 가능 (상태 외에 우선순위, 담당자 등)

### F7. 칼럼 커스터마이징
- **표시 칼럼 선택**: 뷰별로 어떤 칼럼을 보여줄지 토글
- **기본 칼럼 리스트**: 프로젝트별 기본 표시 칼럼 설정 (`.tui-wbs/config.toml`)
- **빌트인 칼럼**: title, status, assignee, duration, priority, start, end, progress, depends, milestone, memo, file
- **커스텀 칼럼**: 프로젝트별 추가 칼럼 정의 (예: team, risk, category)
- 칼럼 순서 변경
- 커스텀 칼럼은 MD 메타데이터 주석에 추가 필드로 저장

### F8. 필터 & 정렬
- **필터**: 칼럼별 조건 필터 (status = TODO, assignee = "Gihwan" 등)
- **복합 필터**: AND 조건으로 여러 필터 조합
- **정렬**: 칼럼 기준 오름차순/내림차순
- **저장**: 뷰별로 필터/정렬 설정 영속 저장
- **빠른 필터**: Footer 영역에서 상태/담당자/우선순위 빠른 토글

### F9. 마일스톤
- `milestone: true` 메타데이터 필드로 마일스톤 지정
- 마일스톤은 duration 없이 특정 날짜(`start` 필드)에 표시
- Gantt에서 `◆` 다이아몬드로 표시
- Table에서 `◇` 아이콘으로 구분
- Kanban에서 별도 색상 카드

### F10. 노드 CRUD 및 편집
- 자식 노드 추가 / 형제 노드 추가
- 노드 삭제 (하위 포함, 확인 대화상자)
- 노드 제목 인라인 편집
- 상세 패널: 필드별 편집
  - Enter → 편집 모드 진입 → Enter 확정 / Esc 취소
  - enum 필드 (status, priority): 선택 리스트
  - 텍스트 필드 (assignee, duration): 텍스트 입력
  - 날짜 필드 (start, end): 날짜 입력 (YYYY-MM-DD)
  - boolean 필드 (milestone): 토글
- 상태 빠른 변경 (1/2/3 키)
- 제목 변경 시 depends 참조 자동 갱신

### F11. 노드 이동
- 위/아래 순서 이동
- 들여쓰기/내어쓰기 (트리 깊이 변경)

### F12. 설정 화면
- 팝업 모달로 진입 (키바인딩 `,`)
- **프로젝트 설정**: 프로젝트명, 기본 뷰, 기본 칼럼 리스트
- **칼럼 관리**: 빌트인 칼럼 표시/숨김, 커스텀 칼럼 추가/수정/삭제
- **뷰 관리**: 뷰 목록, 뷰 타입/필터/칼럼 수정
- 설정 변경 즉시 반영 + 자동 저장

### F13. 도움말 & 접근성
- `?` 키: 전체 키바인딩 도움말 모달
- `--help` CLI 옵션
- `--no-color` CLI 옵션 (색상 없이 아이콘만 사용, 아이콘 중복 없도록 설계)
- 마우스 클릭으로 노드 선택 지원 (Textual 내장)
- 파싱 경고 표시: Footer에 경고 수 표시, `!` 키로 상세 경고 목록 모달

### F14. 검색 & 필터링
- `/` 키: 검색 바 표시 (Footer 위)
- 검색 대상: 제목, 메모, 담당자
- 매칭 노드 하이라이팅 + `n`/`N`으로 다음/이전 이동
- 필터링: 상태별, 담당자별, 우선순위별 (F8과 연동)

### F15. 파일 관리
- 저장 (Ctrl+S), 변경사항 있을 때 종료 시 확인
- Header에 `[*]` 표시로 미저장 변경사항 알림
- `.bak` 백업 + atomic write
- `.lock` 파일 기반 잠금 (PID + 타임스탬프)
  - stale lock 판단: PID 프로세스 존재 여부 확인 → 없으면 자동 제거 + 사용자 알림
  - 타임스탬프 기반 최대 잠금: 1시간 초과 시 stale 간주

---

## Markdown 파일 포맷 명세

```markdown
# 프로젝트명
<!-- status: IN_PROGRESS | assignee: Gihwan | duration: 30d | priority: HIGH | start: 2026-03-01 | end: 2026-04-01 -->

프로젝트 전체에 대한 메모

## Phase 1: 설계
<!-- status: TODO | assignee: Jane | duration: 5d | priority: HIGH | start: 2026-03-01 -->

설계 단계 메모

### Task 1.1: 요구사항 분석
<!-- status: DONE | assignee: Jane | duration: 2d | priority: HIGH | start: 2026-03-01 | end: 2026-03-03 | depends: -->

요구사항 분석 완료 메모

### Task 1.2: 기술 검토
<!-- status: IN_PROGRESS | assignee: John | duration: 3d | priority: MEDIUM | start: 2026-03-03 | depends: Task 1.1 -->

### Milestone: 설계 완료
<!-- milestone: true | start: 2026-03-06 | status: TODO | depends: Task 1.2 -->

## Phase 2: 구현
<!-- status: TODO | assignee: | duration: 20d | priority: HIGH | start: 2026-03-07 | depends: Phase 1 -->

### Task 2.1: 코어 개발
<!-- status: TODO | assignee: | duration: 10d | priority: HIGH | start: 2026-03-07 | team: Backend -->
```

### 메타데이터 필드 정의

#### 빌트인 필드

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `status` | enum | `TODO` | `TODO` \| `IN_PROGRESS` \| `DONE` |
| `assignee` | string | `""` | 담당자 이름 |
| `duration` | string | `""` | 예상 기간 (예: `5d`, `2w`, `1m`) |
| `priority` | enum | `MEDIUM` | `HIGH` \| `MEDIUM` \| `LOW` |
| `depends` | string | `""` | 의존 항목 - 노드 제목 기반 참조 (세미콜론 `;` 구분) |
| `start` | date | `""` | 시작일 (YYYY-MM-DD) |
| `end` | date | `""` | 종료일 (YYYY-MM-DD). 없으면 start + duration으로 자동 계산 |
| `milestone` | boolean | `false` | 마일스톤 여부. `true`이면 duration 무시, start 날짜에 점으로 표시 |
| `progress` | number | auto | 0-100. 자식 노드가 있으면 하위 DONE 비율로 자동 계산 |

#### 커스텀 필드

- 프로젝트 `.tui-wbs/config.toml`에서 정의
- MD 메타데이터 주석에 추가 `key: value`로 저장
- 예: `team: Backend`, `risk: High`, `sprint: 3`

### depends 필드 규칙

- **구분자**: 세미콜론(`;`) 사용 (제목에 세미콜론 포함 시 극히 드물어 충돌 최소화)
- **예시**: `depends: Task 1.1; Task 1.2`
- **중복 제목 처리**: 동일 제목 존재 시 파일 내 먼저 나오는 노드 매칭 + 파싱 경고
- **제목 변경 시**: Phase 2에서 depends 참조 자동 갱신 구현
- **순환 의존성**: 파싱 시 경고 표시하되 저장은 허용 (사용자 책임)
- **UI 표시**: 의존 노드가 미완료(TODO/IN_PROGRESS)일 때 트리에서 `🔒` 아이콘 표시
- **참조 검증**: 존재하지 않는 노드 제목 참조 시 파싱 경고

### 메타데이터 파싱 규칙 (엣지케이스)

| 케이스 | 처리 방식 |
|--------|----------|
| 특수문자 포함 값 (`John O'Brien`) | 그대로 보존, 별도 이스케이프 없음 |
| 알 수 없는 필드 (`custom: value`) | 커스텀 칼럼 정의 있으면 인식, 없으면 무시하되 저장 시 원본 그대로 보존 |
| 잘못된 enum 값 (`status: PENDING`) | 경고 + 기본값(TODO) 적용, 저장 시 수정된 값 반영 |
| 메타데이터 주석 없는 헤딩 | 전체 필드 기본값 적용, 수정 전까지 주석 추가하지 않음 |
| 빈 값 (`assignee: `) | 빈 문자열(`""`)로 처리 |
| 메타데이터 주석이 헤딩 바로 다음 줄이 아닌 경우 | 헤딩과 다음 헤딩 사이의 첫 번째 메타데이터 주석만 인식 |
| 바이너리/비-MD 파일 | 에러 메시지 출력 후 건너뜀 |
| 헤딩 없는 MD 파일 | 경고 후 빈 트리로 표시 |
| 헤딩 레벨 건너뛰기 (h1→h3) | 가장 가까운 상위 레벨의 자식으로 배치 + 파싱 경고 |
| 잘못된 날짜 형식 | 경고 + 빈 값 처리 |

---

## 프로젝트 폴더 구조 (사용자)

```
my-project/
├── .tui-wbs/
│   └── config.toml           # 프로젝트 설정 (뷰, 필터, 칼럼, 정렬)
├── overview.wbs.md            # 전체 WBS 개요
├── phase1-design.wbs.md       # Phase 1 상세
├── phase2-implement.wbs.md    # Phase 2 상세
└── ...
```

### .tui-wbs/config.toml 구조

```toml
[project]
name = "My Project"
default_view = "overview"

# 기본 표시 칼럼 (모든 새 뷰의 초기값)
default_columns = ["title", "status", "assignee", "priority", "duration", "start", "end"]

# 커스텀 칼럼 정의
[[columns.custom]]
id = "team"
name = "Team"
type = "enum"
values = ["Frontend", "Backend", "QA", "Design"]

[[columns.custom]]
id = "risk"
name = "Risk"
type = "enum"
values = ["High", "Medium", "Low"]

# 뷰 설정
[[views]]
id = "overview"
name = "Overview"
type = "table"
columns = ["title", "status", "assignee", "priority", "duration"]
sort = { field = "priority", order = "desc" }

[[views]]
id = "gantt"
name = "Gantt"
type = "table+gantt"
columns = ["title", "status", "assignee", "start", "end"]
gantt_scale = "week"
gantt_level = 2

[[views]]
id = "board"
name = "Board"
type = "kanban"
group_by = "status"
columns = ["title", "priority", "assignee"]

  [[views.filters]]
  field = "assignee"
  operator = "eq"
  value = "Gihwan"
```

---

## Model Summary

| 엔티티 | 주요 필드 | 설명 |
|--------|----------|------|
| `WBSNode` | id(UUID), title, level, status, assignee, duration, priority, depends, start, end, milestone, progress, memo, custom_fields, children, source_file | WBS 트리의 단일 노드. `@dataclass(frozen=True)` |
| `WBSDocument` | file_path, root_nodes, raw_content, modified | 단일 MD 파일을 표현 |
| `WBSProject` | dir_path, documents, config, parse_warnings | 폴더 기반 프로젝트 전체 |
| `ViewConfig` | id, name, type, columns, filters, sort, gantt_scale, gantt_level, group_by | 뷰 설정 |
| `ColumnDef` | id, name, type, values, required | 칼럼 정의 (빌트인 + 커스텀) |
| `ProjectConfig` | name, default_view, default_columns, custom_columns, views | 프로젝트 설정 |

**frozen dataclass 편집 전략**:
- 노드 수정 시 `dataclasses.replace(node, status="DONE")` 으로 새 인스턴스 생성
- WBSDocument 레벨에서 변경된 노드를 포함한 트리 재구성
- Undo/Redo: 이전 상태의 불변 스냅샷을 스택에 보관 (Command 패턴)

---

## TUI 레이아웃

### Table 뷰

```
┌─────────────────────────────────────────────────────────────────┐
│  TUI WBS - My Project                               [*Modified] │  ← Header
├─────────────────────────────────────────────────────────────────┤
│  [Overview] [Gantt] [Board] [+]                              │  ← View Tabs
├─────────────────────────────────────────────────────────────────┤
│  Title              │ Status │ Assignee │ Priority │ Duration   │
│─────────────────────┼────────┼──────────┼──────────┼────────────│
│  ▼ ◐ 프로젝트명     │ IN_PRG │ Gihwan   │ ◆ HIGH   │ 30d        │
│    ▼ ○ Phase 1      │ TODO   │ Jane     │ ◆ HIGH   │ 5d         │
│      ● Task 1.1     │ DONE   │ Jane     │ ◆ HIGH   │ 2d         │
│      ◐ Task 1.2     │ IN_PRG │ John     │ ▲ MED    │ 3d         │
│      ◇ 설계 완료     │ TODO   │          │          │            │
│    ▶ ○ Phase 2      │ TODO   │          │ ◆ HIGH   │ 20d        │
├─────────────────────────────────────────────────────────────────┤
│  Filter: status=TODO,IN_PROGRESS | Sort: priority DESC          │  ← Status Bar
├─────────────────────────────────────────────────────────────────┤
│  [a]dd [e]dit [d]el [/]search [,]settings [?]help [q]uit       │  ← Footer
└─────────────────────────────────────────────────────────────────┘
```

### Table + Gantt 뷰

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TUI WBS - My Project                                        [*Modified] │
├──────────────────────────────────────────────────────────────────────────┤
│  [Overview] [Gantt] [Board] [+]                                       │
├──────────────────────────┬───────────────────────────────────────────────┤
│  Title          │ Status │    Mar W1   Mar W2   Mar W3   Mar W4         │
│─────────────────┼────────┤    ┊        ┊  ▼today ┊        ┊             │
│  ▼ ◐ 프로젝트명  │ IN_PRG │    ████████████████████████████████          │
│    ▼ ○ Phase 1  │ TODO   │    █████████████████                         │
│      ● Task 1.1 │ DONE   │    ██████                                    │
│      ◐ Task 1.2 │ IN_PRG │          ░░░██████████                       │
│      ◇ 설계 완료 │ TODO   │                     ◆                        │
│    ▶ ○ Phase 2  │ TODO   │                       ████████████████████   │
├──────────────────────────┴───────────────────────────────────────────────┤
│  Scale: [D]ay [W]eek [M]onth [Q]uarter [Y]ear  Level: [<][2][>]        │
├──────────────────────────────────────────────────────────────────────────┤
│  [a]dd [e]dit [d]el [/]search [,]settings [?]help [q]uit                │
└──────────────────────────────────────────────────────────────────────────┘
```

### Kanban 뷰

```
┌──────────────────────────────────────────────────────────────────────────┐
│  TUI WBS - My Project                                        [*Modified] │
├──────────────────────────────────────────────────────────────────────────┤
│  [Overview] [Gantt] [Board] [+]                                       │
├──────────────────────┬──────────────────────┬────────────────────────────┤
│       TODO (2)       │   IN_PROGRESS (1)    │        DONE (1)            │
├──────────────────────┼──────────────────────┼────────────────────────────┤
│ ┌──────────────────┐ │ ┌──────────────────┐ │ ┌──────────────────────┐   │
│ │ Phase 2          │ │ │ Task 1.2         │ │ │ Task 1.1             │   │
│ │ ◆ HIGH  Gihwan   │ │ │ ▲ MED   John     │ │ │ ◆ HIGH  Jane         │   │
│ └──────────────────┘ │ └──────────────────┘ │ └──────────────────────┘   │
│ ┌──────────────────┐ │                      │                            │
│ │ ◇ 설계 완료      │ │                      │                            │
│ │   Milestone      │ │                      │                            │
│ └──────────────────┘ │                      │                            │
├──────────────────────┴──────────────────────┴────────────────────────────┤
│  Group by: [status] | Filter: level <= 2                                 │
├──────────────────────────────────────────────────────────────────────────┤
│  [a]dd [e]dit [d]el [h/l]move [/]search [,]settings [?]help [q]uit      │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 키바인딩

### 공통

| 키 | 동작 |
|----|------|
| `↑`/`k` | 이전 항목 |
| `↓`/`j` | 다음 항목 |
| `Enter` | 선택/편집 모드 진입 |
| `Esc` | 편집 취소/모달 닫기 |
| `a` | 자식 노드 추가 |
| `A` | 형제 노드 추가 |
| `e` | 선택 노드 제목 편집 |
| `d` | 선택 노드 삭제 (확인) |
| `1`-`3` | 상태 변경 (1=TODO, 2=IN_PROGRESS, 3=DONE) |
| `Tab` | 패널 간 포커스 전환 |
| `Ctrl+S` | 저장 |
| `/` | 검색 |
| `n`/`N` | 다음/이전 검색 결과 |
| `?` | 도움말 모달 |
| `,` | 설정 화면 |
| `!` | 파싱 경고 목록 |
| `q` | 종료 |

### Table/Tree 전용

| 키 | 동작 |
|----|------|
| `Space` | 접기/펼치기 토글 |
| `K` | 노드 위로 이동 |
| `J` | 노드 아래로 이동 |
| `H` | 노드 내어쓰기 (레벨 올림) |
| `L` | 노드 들여쓰기 (레벨 내림) |

### Gantt 전용

| 키 | 동작 |
|----|------|
| `D` | Day 스케일 |
| `W` | Week 스케일 |
| `M` | Month 스케일 |
| `Q` | Quarter 스케일 |
| `Y` | Year 스케일 |
| `<`/`>` | WBS 레벨 감소/증가 |
| `←`/`→` | 타임라인 좌우 스크롤 |
| `t` | 오늘 날짜로 이동 |

### Kanban 전용

| 키 | 동작 |
|----|------|
| `h`/`l` | 카드를 이전/다음 칼럼으로 이동 (상태 변경) |
| `K`/`J` | 카드 순서 위/아래 |

### 뷰 전환

| 키 | 동작 |
|----|------|
| `g1`-`g9` | 1~9번째 뷰로 전환 |
| `gn` | 다음 뷰 |
| `gp` | 이전 뷰 |

---

## 사용 기술

| 기술 | 버전 | 용도 |
|------|------|------|
| Python | 3.12+ | 런타임 (mise 권장, 필수 아님) |
| Textual | 8.x | TUI 프레임워크 (DataTable, Tree, CSS 스타일링) |
| Click | 8.x | CLI 인자 파싱 |
| tomlkit | 0.14+ | 프로젝트 설정 파일 읽기/쓰기 (포맷 보존) |
| python-dateutil | 3.x | 날짜 파싱 및 계산 |
| re (stdlib) | - | 메타데이터 정규식 파싱 |
| tomllib (stdlib) | - | TOML 읽기 (fallback) |

### Gantt/Table/Kanban 구현 방식

| 컴포넌트 | 구현 | 근거 |
|----------|------|------|
| Table 뷰 | Textual `DataTable` 위젯 | 빌트인, 정렬·리사이즈 지원 |
| Gantt 차트 | 커스텀 Textual Widget | TUI용 Gantt 라이브러리 없음, Rich renderable + Unicode 블록 문자로 직접 구현 |
| Kanban 보드 | 커스텀 Textual Widget | Horizontal + VerticalScroll 컨테이너 조합, kanban-tui 구현 패턴 참고 |

---

## 코드 폴더 구조

```
tui-wbs/
├── pyproject.toml
├── README.md
├── LICENSE
├── .mise.toml                    # Python 버전 관리 (권장)
├── src/
│   └── tui_wbs/
│       ├── __init__.py
│       ├── __main__.py           # python -m tui_wbs 엔트리포인트
│       ├── app.py                # Textual App 메인 클래스
│       ├── models.py             # WBSNode, WBSDocument, WBSProject 데이터 모델
│       ├── parser.py             # MD → WBSDocument 파싱
│       ├── writer.py             # WBSDocument → MD 저장
│       ├── config.py             # ProjectConfig, ViewConfig 관리
│       ├── widgets/
│       │   ├── __init__.py
│       │   ├── wbs_table.py      # Table 뷰 위젯 (DataTable 기반)
│       │   ├── gantt_chart.py    # Gantt 차트 커스텀 위젯
│       │   ├── kanban_board.py   # Kanban 보드 커스텀 위젯
│       │   ├── detail_panel.py   # 상세 정보 패널 위젯
│       │   ├── view_tabs.py      # 뷰 탭 바 위젯
│       │   └── settings_modal.py # 설정 화면 모달
│       ├── screens/
│       │   ├── __init__.py
│       │   ├── help_screen.py    # 도움말 모달
│       │   ├── warning_screen.py # 파싱 경고 모달
│       │   └── confirm_screen.py # 확인 대화상자
│       └── cli.py                # Click CLI 엔트리포인트
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_writer.py
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_roundtrip.py         # round-trip 전용 테스트
│   ├── test_app.py               # Textual Pilot 기반 통합 테스트
│   └── test_gantt.py             # Gantt 렌더링 테스트
└── docs/
    └── tui-wbs/
        ├── tui-wbs.prd.md
        └── stakeholder-analysis.md
```

---

## Development Roadmap

### Phase 1: Core (MVP)
- 프로젝트 초기화 (mise, pyproject.toml, LICENSE)
- 데이터 모델 (WBSNode frozen dataclass + `dataclasses.replace()`, WBSDocument, WBSProject)
- MD 파서 구현 (멀티 파일, 메타데이터 검증, 엣지케이스, 날짜 필드, 마일스톤)
- MD 라이터 구현 (round-trip 보장, 백업 + atomic write, 미수정 노드 주석 미추가)
- 프로젝트 설정 로더 (`.tui-wbs/config.toml` 읽기/쓰기)
- Table 뷰 (DataTable, 상태/우선순위 아이콘, 트리 들여쓰기)
- 뷰 탭 바 (전환 기능)
- 칼럼 표시 선택
- 도움말 모달 (`?`), `--help`/`--no-color` CLI 옵션
- 파싱 경고 표시 (`!`)
- 마우스 클릭 선택
- round-trip 테스트 + Textual Pilot 통합 테스트

### Phase 2: 뷰 시스템 & 시각화
- Gantt 차트 커스텀 위젯 (시간 축 5종, 오늘 기준선)
- Gantt WBS 레벨 필터링
- Kanban 보드 커스텀 위젯
- 뷰 관리 (추가/수정/삭제/복제)
- 필터 & 정렬 (저장)
- 마일스톤 Gantt 표시 (◆)
- 기본 뷰 설정

### Phase 3: 편집 기능
- 노드 추가/삭제
- 제목 인라인 편집
- 상세 패널 필드별 편집 (Enter 진입, enum 선택, 텍스트 입력, 날짜 입력)
- 상태 빠른 변경 (1/2/3)
- 제목 변경 시 depends 자동 갱신
- Kanban 카드 이동 (상태 변경)
- 파일 잠금 (.lock, stale 감지)
- 설정 화면 모달 (`,` 키)
- 커스텀 칼럼 관리

### Phase 4: 고급 기능
- 노드 이동 (순서, 들여쓰기)
- 검색 + 하이라이팅 (n/N 네비게이션)
- 종료 시 미저장 확인
- 메모 TextArea 편집
- Undo/Redo (Command 패턴, frozen 스냅샷)
- 진행률 자동 계산 (하위 DONE 비율)
- Gantt 의존성 시각화 (화살표/색상)
- 내보내기 (JSON, CSV)

---

## 성능 목표

| 시나리오 | 목표 |
|---------|------|
| 1,000 노드 파일 로딩 | < 2초 |
| 5,000 노드 파일 로딩 | < 5초 |
| 트리 접기/펼치기 | < 100ms |
| Gantt 스케일 전환 | < 200ms |
| 파일 저장 | < 1초 |
| 뷰 전환 | < 300ms |

- 5,000 노드 이상은 성능 한계 문서화

---

## 데이터 안전성

| 항목 | 방식 | Phase |
|------|------|-------|
| **백업** | 저장 시 `.bak` 파일 자동 생성 | 1 |
| **Atomic write** | temp 파일 작성 → `os.replace()` rename | 1 |
| **파일 잠금** | `.lock` 파일 기반 (PID + 타임스탬프), stale 판단: PID 존재 확인 + 1시간 초과 | 3 |
| **Undo/Redo** | Command 패턴 (execute/undo 스택), frozen dataclass 스냅샷 | 4 |
| **파싱 복구** | 잘못된 메타데이터는 기본값 적용 + `parse_warnings` 수집, UI에서 경고 표시 | 1 |
| **.gitignore 안내** | 최초 실행 시 `.bak`, `.lock` 파일을 `.gitignore`에 추가 권장 메시지 | 1 |

---

## 테스트 전략

| 테스트 유형 | 도구 | 범위 |
|------------|------|------|
| 단위 테스트 | pytest | parser, writer, models, config |
| round-trip 테스트 | pytest | 다양한 MD 파일 읽기→저장→비교 (byte-for-byte) |
| TUI 통합 테스트 | Textual Pilot API | 앱 시작→노드 선택→상태 변경→저장→파일 확인 |
| Gantt 렌더링 테스트 | pytest + snapshot | 시간 축별 렌더링 결과 스냅샷 비교 |
| 성능 테스트 | pytest-benchmark | 1,000/5,000 노드 로딩 시간 |
| 엣지케이스 테스트 | pytest | 파싱 엣지케이스 표의 모든 케이스 |

---

## 배포

| 항목 | 방식 |
|------|------|
| 패키지 | PyPI 배포 (`pip install tui-wbs`) |
| 권장 설치 | `pipx install tui-wbs` (격리 환경) |
| 엔트리포인트 | `pyproject.toml` → `[project.scripts]` → `tui-wbs = "tui_wbs.cli:main"` |
| 라이선스 | MIT |

---

## Risks and Mitigations

| 위험 | 완화 방안 |
|------|----------|
| MD 파싱 시 원본 손실 | round-trip 테스트 필수, 파싱 안 되는 영역은 raw 보존 |
| 깊은 트리에서 UX 저하 | h1~h6 (6단계)까지만 지원, 접기/펼치기 + WBS 레벨 필터 활용 |
| Textual Tree/DataTable 커스터마이징 한계 | 위젯 서브클래싱으로 확장, 포커스 해제 시 선택 표시 CSS 커스터마이징 |
| Gantt 커스텀 위젯 개발 난이도 | 최소 기능(바 표시 + 스케일)부터 점진 구현 |
| 동시 편집 충돌 | Phase 3에서 `.lock` 파일 기반 잠금 + stale 감지 |
| 대용량 파일 성능 | 5,000 노드까지 테스트, 성능 한계 문서화 |
| 저장 중 크래시 | atomic write로 중간 상태 방지, `.bak`에서 복구 가능 |
| 멀티 파일 저장 일관성 | 파일별 독립 저장 + 전체 프로젝트 저장 모드 |
| depends 제목 참조 깨짐 | Phase 3에서 제목 변경 시 자동 갱신, 중복 제목 경고 |

---

## 벤치마킹 참고

| 도구 | 언어 | 참고할 점 |
|------|------|----------|
| [GitHub Projects](https://github.com/features/issues) | Web | 뷰 시스템 (Table/Board/Roadmap), 커스텀 필드, 필터 저장 |
| [beads_viewer](https://github.com/Dicklesworthstone/beads_viewer) | Go | WBS 특화, 의존성 DAG, 크리티컬 패스 |
| [taskwarrior-tui](https://github.com/kdheepak/taskwarrior-tui) | Rust | 필터 표현식, 다양한 내보내기 |
| [kanban-tui](https://github.com/Zaloog/kanban-tui) | Python/Textual | 같은 프레임워크, Kanban 위젯 구현 패턴 참고 |
| [vault-tasks](https://github.com/louis-thevenet/vault-tasks) | Python | Markdown 기반 태그/하위작업 |

---

## Term

| 용어 | 설명 |
|------|------|
| WBS | Work Breakdown Structure - 프로젝트 작업 분해 구조 |
| TUI | Terminal User Interface - 터미널 기반 사용자 인터페이스 |
| WP | Work Package - WBS의 최하위 작업 단위 |
| round-trip | 파일 읽기→수정 없이 저장 시 원본과 동일함을 보장하는 특성 |
| mise | 다국어 런타임 버전 관리 도구 (Python, Node 등) |
| Milestone | 프로젝트의 주요 체크포인트/마감점. duration 없이 특정 날짜에 표시 |
| Gantt Chart | 작업 일정을 시간 축 위의 수평 바로 표시하는 차트 |
| Kanban | 작업을 상태별 칼럼으로 분류하는 시각화 보드 |

---

## TODO

### Phase 1: Core (MVP)
- [x] mise + pyproject.toml + LICENSE 프로젝트 초기화
- [x] WBSNode(frozen, UUID, start/end/milestone), WBSDocument, WBSProject 데이터 모델
- [x] MD 파서 (멀티 파일, 메타데이터 검증, 날짜/마일스톤, 엣지케이스, 레벨 건너뛰기)
- [x] MD 라이터 (round-trip 보장, 미수정 노드 주석 미추가, 백업 + atomic write)
- [x] ProjectConfig 로더/세이버 (tomlkit, `.tui-wbs/config.toml`)
- [x] Textual App 기본 레이아웃 (Header + ViewTabs + Content + StatusBar + Footer)
- [x] Table 뷰 위젯 (DataTable, 상태 아이콘 ○◐●, 우선순위 아이콘 ◆▲▽, 마일스톤 ◇)
- [x] 뷰 탭 바 위젯 (전환 기능)
- [x] 칼럼 표시 선택 (뷰별)
- [x] 파일 저장 (Ctrl+S, [*] 변경 표시)
- [x] 파싱 경고 표시 (Footer 경고 수 + `!` 상세 모달)
- [x] 도움말 모달 (`?` 키)
- [x] CLI 엔트리포인트 (click, --help, --no-color)
- [x] 마우스 클릭 선택
- [x] round-trip 테스트 + Textual Pilot 통합 테스트

### Phase 2: 뷰 시스템 & 시각화
- [x] Gantt 차트 커스텀 위젯 (Unicode 바, 시간 축 5종)
- [x] Gantt WBS 레벨 필터링 (</>)
- [x] Gantt 오늘 기준선 + 스크롤
- [x] Gantt 마일스톤 표시 (◆)
- [x] Kanban 보드 커스텀 위젯 (상태별 칼럼, 카드)
- [x] 뷰 관리 (추가/수정/삭제/복제)
- [x] 필터 & 정렬 (뷰별 저장)
- [x] 기본 뷰 설정

### Phase 3: 편집 기능
- [x] 노드 추가 (자식/형제)
- [x] 노드 삭제 (확인 대화상자)
- [x] 제목 인라인 편집 + depends 자동 갱신
- [x] 상세 패널 필드별 편집 (Enter/Esc, enum 선택, 텍스트/날짜 입력)
- [x] 상태 빠른 변경 (1/2/3)
- [x] Kanban 카드 이동 (h/l로 상태 변경)
- [x] 파일 잠금 (.lock, PID 기반, stale 감지)
- [x] 설정 화면 모달 (`,` 키)
- [x] 커스텀 칼럼 관리 (추가/수정/삭제)

### Phase 4: 고급 기능
- [x] 노드 순서 이동 (위/아래)
- [x] 노드 레벨 변경 (들여쓰기/내어쓰기)
- [x] 검색 + 하이라이팅 (/, n/N)
- [x] 종료 시 미저장 확인
- [x] 메모 TextArea 편집
- [x] Undo/Redo (Command 패턴)
- [x] 진행률 자동 계산 (하위 DONE 비율)
- [x] Gantt 의존성 시각화 (→ 화살표 + 색상)
- [x] 내보내기 (JSON, CSV)
