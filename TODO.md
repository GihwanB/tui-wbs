# TUI WBS - TODO

> PRD: [docs/tui-wbs/tui-wbs.prd.md](docs/tui-wbs/tui-wbs.prd.md)

## Phase 1: MVP
- [x] mise + pyproject.toml 프로젝트 초기화
- [x] WBSNode(frozen dataclass, UUID id), WBSDocument(parse_warnings) 데이터 모델 구현
- [x] MD → WBSDocument 파서 구현 (다중 h1, 메타데이터 검증, 엣지케이스 처리)
- [x] WBSDocument → MD 라이터 구현 (백업 + atomic write)
- [x] round-trip 테스트 작성 (공백/빈줄 포함 byte-for-byte)
- [x] Textual App 기본 레이아웃 (Header + Tree + Detail + Footer)
- [x] WBS 트리 위젯 구현 (상태 아이콘 ○◐●, 우선순위 아이콘+색상 ◆▲●)
- [x] depends 의존성 표시 (미완료 시 🔒)
- [x] 상세 패널 위젯 구현
- [x] 파일 저장 기능 (Ctrl+S, [*] 변경 표시)
- [x] 도움말 모달 (`?` 키)
- [x] CLI 엔트리포인트 (click, --help, --no-color)
- [x] 마우스 클릭 선택 지원

## Phase 2: 편집
- [x] 노드 추가 (자식/형제)
- [x] 노드 삭제 (확인 대화상자)
- [x] 제목 인라인 편집
- [x] 메타데이터 필드 편집
- [x] 상태 빠른 변경 키바인딩
- [x] 파일 잠금 (.lock 파일)
- [x] 설정 파일 (.tui-wbs.toml)

## Phase 3: 고급
- [x] 노드 순서 이동 (위/아래)
- [x] 노드 레벨 변경 (들여쓰기/내어쓰기)
- [x] 검색 + 필터링 (상태/담당자/우선순위)
- [x] 종료 시 미저장 변경사항 확인
- [x] 메모 TextArea 편집
- [x] Undo/Redo (Command 패턴)
- [x] 진행률 자동 계산 (하위 DONE 비율)
- [x] 내보내기 (JSON, CSV)

## Backlog
- [x] Filter 위젯 추가 — GitHub처럼 현재 적용 중인 필터 조건이 표시되는 컴포넌트 (항상 표시되도록 수정)
- [x] 한글/영문 상관없이 단축키 입력 가능하게 수정 (IME 상태 무관하게 동작) — 이미 31개 자모 매핑 구현됨
- [x] 테이블뷰에서 칼럼 포커스 후 `e` 편집 시, 해당 칼럼의 input에 포커스가 가도록 수정
- [x] Keybindings 팝업 너비 늘리기 (60→80)
- [x] 리셋 기능 에러 수정 — `self.action()` → `self.run_action()` 수정
- [x] 데모 보기 기능이 `?` 도움말에도 표시되도록 수정
- [x] 테마(라이트/다크) 기능 추가 — `T` 키로 토글, Gantt 차트 테마 적응, config에 저장
- [x] 기본 저장 포맷 확장 — MD 표(table) 형식 + Gantt는 Mermaid 문법으로 내보내기 전용 구현 (.mmd, .md 확장자)
- [x] 계층형 ID 표시 — 1, 2, 3 순서 대신 1.1, 1.1.1 같은 계층 ID 표현
- [x] Filter/Sort UI 미표시 버그 — filter/sort 바와 gantt 단위 선택이 화면에 보이지 않는 문제
- [x] start/end ↔ duration 연동 — start/end 지정 시 duration 자동 계산, duration 지정 시 end 자동 수정
- [x] 하위→상위 일정 집계 — 하위 노드의 start/end가 지정되면 상위 노드도 자동 업데이트
- [x] progress 칼럼 기본 추가 — 테이블 뷰에 progress 칼럼을 기본 표시
- [x] 데모 데이터 label/module 채우기 — demo_data.py의 각 노드에 label, module 커스텀 필드 내용 추가
- [x] 칼럼 순서 변경 — duration을 start/end 다음에 배치, priority를 assignee 왼쪽에 배치
- [x] TODO 지연 경고 표시 — 현재 날짜 기준으로 start가 도래했는데 status가 TODO인 노드의 타이틀을 빨간 글씨로 표시
- [x] Gantt 차트 아래 빈 영역 흰색 표시 버그 — Gantt 차트 하단의 빈 공간이 테마 배경색 대신 흰색으로 렌더링되는 문제 수정 필요
- [x] Row banding 효과 추가 — 테이블·Gantt 차트에 짝수/홀수 행 배경색 교차 적용하여 가독성 향상
- [x] 커서 행 하이라이트 연동 — 테이블에서 커서가 위치한 행을 Gantt 차트까지 한 줄로 하이라이트 표시
- [x] View mode 버튼 글씨 안 보이는 버그 — view mode 전환 버튼의 텍스트가 표시되지 않는 문제 수정 필요
- [x] Gantt 날짜 텍스트 가운데 정렬 — Gantt 차트 상단 날짜 표시 텍스트를 중앙 정렬로 변경
- [x] 오늘 날짜·마일스톤 세로선 표시 — Gantt 차트에 오늘 날짜와 milestone을 얇은 vertical line으로 표시
- [x] View mode를 Textual Tab으로 변경 — 기존 버튼 방식 대신 Textual의 Tab 위젯을 사용하여 view mode 전환 구현
- [x] Option/Alt+Up/Down으로 날짜·숫자 값 증감 — date 타입 칼럼(start, end)에서 Alt+↑/↓로 날짜 변경, 숫자 칼럼도 동일하게 값 증감 지원
- [x] 칼럼 너비 조절 기능 — 각 칼럼의 너비를 사용자가 수정할 수 있도록 기능 추가
- [x] Date format 변경 기능 — 날짜 표시 형식을 변경하는 기능을 도움말(?) 또는 command palette에 추가
- [x] Enter 키로 셀 편집/순차 변경 — 포커스된 셀에서 Enter 입력 시 일반 칼럼은 `e`(편집)와 동일하게 동작, status·priority 칼럼은 값을 순차적으로 변경
- [x] Gantt 스케일별 칸 너비 설정 — COL_WIDTH_MAP 도입(day=2, week=4, month/quarter/year=6), 설정 YAML로 사용자 커스터마이징 가능하게 연동
- [x] 설정 파일 계층화 (기본 YAML + 프로젝트별 오버라이드) — default_settings.yaml + .tui-wbs/settings.yaml 오버라이드, holidays/gantt/date_format 등 설정 통합
- [x] Gantt week 단위 헤더에 주차(W1, W2…) 표시 — week 스케일일 때 ISO week number 표시, 요일 약자(MTWTFSS) 표시
- [x] Gantt 상단 월 헤더 병합 표시 — 같은 월 칸을 하나의 Segment로 병합, 그룹 인덱스 기반 교대 배경색
- [x] Gantt week 모드 일별 세분화 — col_width=7 (1주=7글자), _date_to_col에 일별 오프셋 적용
- [x] Gantt 주말 표시 — 토·일요일 칼럼에 GANTT_WEEKEND_BG 배경색 적용 (day/week 스케일)
- [x] Gantt 휴일(쉬는 날) 표시 — settings.yaml holidays 목록 → GANTT_HOLIDAY_BG 배경색 적용
- [x] Date format에 MM-DD 옵션 추가 — DATE_FORMAT_PRESETS에 "MM-DD": "%m-%d" 추가
- [x] Gantt 커서 하이라이트 추적 버그 수정 — 테이블 커서 이동 시 Gantt 하이라이트가 따라오지 않는 문제. 원인: RowHighlighted→CellHighlighted 교체 + 핸들러 이름 불일치(`on_wbs_table_*`→`on_wbstable_*`) 수정
- [x] Gantt 수평 스크롤 동작 안 함 — GanttView CSS에 overflow-x/y: auto 추가하여 수정
- [ ] Gantt 테이블 마우스 휠 Y스크롤 동기화 — 테이블 Y스크롤을 마우스 휠로 움직일 때 Gantt 차트 Y스크롤도 함께 이동
- [ ] Gantt 뷰 전환 시 포커스가 3번으로 가는 버그 수정 — view mode를 Gantt로 바꾸면 포커스가 3번 행으로 자동 이동하는 문제
- [ ] Gantt 테이블에 ID 컬럼 추가 및 ID 기본 정렬 — Gantt 테이블에도 ID 표시, 기본 sort는 ID로
- [ ] Table 컬럼 너비 조정 팝업 + Alt+←/→ 증감 — 포커스된 컬럼에서 단축키로 너비 수정 팝업, Alt+Left/Right로 증감
- [ ] View mode 버튼 높이 2칸→1칸으로 축소
- [ ] Gantt 비율 기반 너비 증감 기능 추가 및 w2 삭제 — 비율 증감에 따라 너비가 증감하는 기능 추가, w2 삭제
- [ ] Gantt 테이블에 progress 컬럼 추가
- [ ] Enter 키 status/priority 변경 제거, Alt+Up/Down으로 변경 — Enter로 status/priority 순차 변경 제거, Alt+Up/Down으로 수정
- [ ] 컬럼 너비 설정 영속 저장 — 너비 수정 데이터가 저장되어 재실행해도 유지되는지 확인, 없으면 구현
- [ ] 기본 날짜 표시 포맷을 MM-DD로 변경
