<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-03-17 | Updated: 2026-03-17 -->

# templates

## Purpose
Jinja2 HTML 템플릿. Tailwind CSS 3 (CDN) + HTMX 1.9.x (CDN) 기반. 서버 사이드 렌더링으로 SPA 프레임워크 없이 동적 UI를 제공한다.

## Key Files

| File | Description |
|------|-------------|
| `base.html` | 레이아웃 베이스 — Tailwind CDN, HTMX CDN, Inter 폰트, 글로벌 로딩 오버레이, 에러 토스트, 업로드/편집 모달 include |
| `index.html` | 메인 페이지 — header + filter_toolbar + file_table 조합. `base.html` 상속 |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `components/` | 재사용 가능 UI 컴포넌트 — 헤더, 필터 툴바 (see `components/AGENTS.md`) |
| `partials/` | HTMX partial 응답용 HTML 조각 — 파일 테이블, 행, 페이지네이션, 모달 등 (see `partials/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Tailwind CSS: CDN 사용, 빌드 프로세스 없음. 클래스명 직접 사용
- HTMX: `hx-get`, `hx-post`, `hx-target`, `hx-swap` 속성으로 서버와 통신
- 한글 UI: 모든 사용자 표시 텍스트 한글
- `base.html`의 JS에서 글로벌 HTMX 이벤트 처리 (로딩 오버레이, 에러 토스트)
- 검색/필터 입력은 글로벌 스피너 제외, 파싱 폴링도 제외

### Common Patterns
- `{% extends "base.html" %}` + `{% block content %}` 패턴
- `{% include "partials/..." %}` / `{% include "components/..." %}`로 조합
- HTMX partial 교체: 서버에서 HTML 조각 반환 → 특정 DOM 요소 교체
- 에러 처리: `htmx:responseError` 이벤트에서 상태 코드별 한글 메시지 표시

## Dependencies

### External
- Tailwind CSS 3.x (CDN: `cdn.tailwindcss.com`)
- HTMX 1.9.10 (CDN: `unpkg.com/htmx.org`)
- HTMX json-enc extension
- Google Fonts: Inter

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
