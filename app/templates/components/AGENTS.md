<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# components

## Purpose
재사용 가능한 Jinja2 UI 컴포넌트. `{% include %}` 방식으로 페이지에 삽입된다. 전체 페이지 렌더링 시 포함되며, HTMX partial 교체 대상이 아닌 정적 구조 요소.

## Key Files

| File | Description |
|------|-------------|
| `header.html` | 페이지 상단 헤더 — 타이틀, 파일 업로드 버튼 |
| `filter_toolbar.html` | 검색 입력, 파일 타입 필터, 날짜 범위 필터 드롭다운. HTMX로 파일 테이블 실시간 필터링 트리거 |

## For AI Agents

### Working In This Directory
- `index.html`에서 `{% include "components/..." %}`로 사용
- `filter_toolbar.html`: HTMX `hx-get="/api/partials/file-table"` + `hx-trigger="input changed delay:300ms"` 패턴
- 검색/필터는 글로벌 로딩 스피너에서 제외됨 (`base.html` JS 참조)

## Dependencies

### Internal
- `app/api/pages.py` — `/api/partials/file-table` 엔드포인트 (필터 요청 대상)

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
