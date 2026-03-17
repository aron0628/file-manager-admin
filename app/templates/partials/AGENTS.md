<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# partials

## Purpose
HTMX partial 응답용 HTML 조각. API 라우터에서 `HX-Request` 헤더 감지 시 이 템플릿들을 반환하여 DOM의 특정 부분만 교체한다.

## Key Files

| File | Description |
|------|-------------|
| `file_table.html` | 파일 목록 테이블 전체 — 테이블 헤더, 파일 행 반복, 페이지네이션 포함. 업로드/삭제/필터 후 교체 대상 |
| `file_row.html` | 단일 파일 행 `<tr>` — 파일명, 카테고리, 크기, 날짜, 파싱 상태, 액션 버튼. 수정 후 행 단위 교체 |
| `pagination.html` | 페이지네이션 UI — 이전/다음, 페이지 번호 버튼. HTMX로 페이지 전환 |
| `parse_status.html` | 파싱 상태 뱃지 — 상태별 색상/텍스트, HTMX 폴링(`hx-trigger="every 3s"`), 완료 시 다운로드 버튼 OOB swap |
| `upload_modal.html` | 파일 업로드 모달 — 드래그앤드롭, 카테고리 선택, HTMX 업로드 |
| `edit_modal.html` | 파일 편집 모달 — 파일명/카테고리 수정, HTMX PUT 요청 |
| `empty_state.html` | 파일 없음 상태 표시 |

## For AI Agents

### Working In This Directory
- `file_table.html`은 가장 빈번하게 교체되는 partial — 업로드, 삭제, 필터, 페이지 전환 시 사용
- `file_row.html`은 수정 시에만 단일 행 교체 (`hx-swap="outerHTML"`)
- `parse_status.html`은 HTMX 폴링으로 3초마다 자동 갱신. 완료 시 OOB swap으로 다운로드 버튼 표시
- 모달은 `base.html`에서 `{% include %}`로 항상 포함. JavaScript로 열고 닫음
- 템플릿 변수: `files`, `file`, `parse_job`, `total`, `page`, `page_size`, `total_pages`, `offset`, `search`, `file_type`, `date_range`

### Common Patterns
- HTMX OOB (Out-of-Band) swap: `hx-swap-oob="true"` — 메인 응답 외 추가 DOM 교체
- 상태별 조건부 렌더링: `{% if parse_job.status == "completed" %}` 등
- Tailwind 뱃지 패턴: 상태별 `bg-*-100 text-*-800` 색상 클래스

## Dependencies

### Internal
- `app/api/files.py` — 파일 CRUD 후 partial 반환
- `app/api/parse.py` — 파싱 상태/결과 partial 반환
- `app/api/pages.py` — 필터/페이지네이션 partial 반환

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
