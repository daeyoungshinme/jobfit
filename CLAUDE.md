# CLAUDE.md

JobFit — 채용공고/이력서 분석 도구 (FastAPI + SQLite, 서버사이드 렌더링). 사용자 대상 설명(왜 수동 입력인지, 복사 잠금 해제 도구, OCR 사전 설치 등)은 [README.md](README.md)를 참고하세요. 이 파일은 코드를 다룰 때 필요한 실무 정보에 집중합니다.

## 실행 / 테스트

```bash
uvicorn app.main:app --reload --port 8100   # 또는 ./dev.sh (Git Bash, 기존 서버 정리 후 재기동)
pytest                                       # tests/
```

데이터는 프로젝트 루트의 `jobfit.db` (SQLite)에 저장됩니다. 외부 AI API는 사용하지 않으며, 스킬 추출/매칭은 전부 정규식·사전 기반 규칙 매칭입니다. OCR([app/services/ocr.py](app/services/ocr.py))만 예외적으로 로컬에 설치된 Tesseract-OCR 바이너리를 호출하지만, 이 역시 외부 서비스 호출이 아닙니다.

테스트는 `tests/conftest.py`의 `db_session`/`client` 픽스처가 in-memory SQLite로 `get_db`를 오버라이드해서 돕니다 — 실제 `jobfit.db`를 건드리지 않으므로, 라우터 테스트를 추가할 때는 이 픽스처를 그대로 재사용하세요.

## 아키텍처

요청 흐름: `routers` → `services` → `models`. 템플릿은 [app/templates.py](app/templates.py)의 단일 `Jinja2Templates` 인스턴스를 모든 라우터가 `from app.templates import templates`로 가져다 쓰는 공유 구조이며, 여기에 `bulleted` 커스텀 필터와 `flash_messages` 전역이 등록되어 있습니다.

- [app/main.py](app/main.py) — FastAPI 앱 진입점, 라우터 등록, startup 시 `init_db()` 호출.
- [app/templates.py](app/templates.py) — 공유 `Jinja2Templates` 인스턴스, `bulleted` 필터·`flash_messages` 전역 등록.
- [app/routers/jobs.py](app/routers/jobs.py) — 채용공고 CRUD, 스킬 미리보기, OCR 업로드, 출처 사이트(source_site) 추측, 지원 상태(`status`) 빠른 변경(`POST /jobs/{id}/status`), 지원 기록 저장(`POST /jobs/{id}/application` — 상태+지원채널+지원일+사용 이력서+메모).
- [app/routers/resumes.py](app/routers/resumes.py) — 이력서 업로드(PDF/DOCX/TXT)/폼 등록/수정/삭제. 저장 로직은 [app/services/resume_editor.py](app/services/resume_editor.py)의 `apply_resume_content()`에 모여 있음(`analysis.py`의 맞춤 편집과 공유).
- [app/routers/analysis.py](app/routers/analysis.py) — 매칭 대시보드(스킬 수요 랭킹 포함), 이력서-공고 코칭(`/coach`), 공고 맞춤 이력서 편집 워크스페이스(`/tailor`, [tailor.html](app/templates/tailor.html)), 플랫폼 프로필 문구 생성(`/profile`, [profile.html](app/templates/profile.html)), 구직 활동 대시보드(`/activity`, [activity.html](app/templates/activity.html)).
- [app/services/job_parser.py](app/services/job_parser.py) — 정규식 기반 채용공고 섹션 분리(주요업무/자격요건/우대사항). 복지·혜택 헤더는 섹션 경계(stop marker)로만 쓰고 내용은 저장하지 않음.
- [app/services/skill_extractor.py](app/services/skill_extractor.py) — `app/data/skills_dictionary.json` 사전 기반 스킬 추출. `term_pattern()`이 스크립트별 단어 경계 규칙을 제공(아래 컨벤션 참고).
- [app/services/matcher.py](app/services/matcher.py) — 이력서-공고 매칭 점수 계산. 가중치(`MATCH_REQUIRED_WEIGHT=0.7`, `MATCH_PREFERRED_WEIGHT=0.3`)는 [app/constants.py](app/constants.py)에 정의.
- [app/services/job_fit_coach.py](app/services/job_fit_coach.py) — `matcher`의 매칭 결과를 바탕으로 부족 스킬을 카테고리별로 묶고(`skill_extractor.skill_category_map()` 사용) 공고 맞춤 제안을 만들며, `resume_reviewer.review_resume()` 결과를 `CoachingResult.general_review`로 함께 담음. `analysis.py`의 `/coach`·`/tailor`에서 사용.
- [app/services/resume_parser.py](app/services/resume_parser.py) / [resume_reviewer.py](app/services/resume_reviewer.py) / [resume_editor.py](app/services/resume_editor.py) — 이력서 파일 텍스트 추출 / 규칙 기반 범용 체크리스트(+ `extract_achievement_lines()`) / 편집 내용 저장·스킬 재추출 공용 헬퍼.
- [app/services/profile_exporter.py](app/services/profile_exporter.py) — 이력서를 LinkedIn/리멤버/원티드·잡코리아 프로필 문구로 규칙 기반 변환. `matcher.skill_ranking`으로 시장 수요 순 스킬 정렬, `resume_reviewer.extract_achievement_lines`로 성과 문장 추출. 자동 게시 없음.
- [app/services/activity_report.py](app/services/activity_report.py) — 채용공고 지원 기록(상태/채널/지원일/`is_inbound`)을 모아 상태별·채널별 현황, 무응답 경과(`STALE_AFTER_DAYS=14`), 인바운드 제안, 면접 진행 목록을 만듦. `analysis.py`의 `/activity`에서 사용.
- [app/services/ocr.py](app/services/ocr.py) — 캡처 이미지 OCR. `pytesseract` + 로컬 Tesseract-OCR 바이너리 호출, PATH에 없으면 Windows 기본 설치 경로를 자동 탐색하고 실패 시 한국어 안내 메시지로 `RuntimeError`를 던짐.
- [app/services/text_formatter.py](app/services/text_formatter.py) — 원문 텍스트를 글머리 기호/괄호 소제목 기준으로 escape된 HTML로 렌더링 (`bulleted` 필터의 구현체).
- [app/services/validation.py](app/services/validation.py) — `require_fields()`로 폼 필수값 검증. 라우터들이 공통으로 재사용.
- [app/models.py](app/models.py) — SQLAlchemy 모델 (`JobPosting`, `Resume`).
- [app/db.py](app/db.py) — SQLite 엔진/세션, 테이블 컬럼 마이그레이션(`_migrate_table_columns()`, 현재 `JobPosting`에 적용 중).
- [app/schemas.py](app/schemas.py) — Pydantic 응답 스키마.
- [app/constants.py](app/constants.py) — 직무/경력/지역/지원상태(`JOB_STATUSES`) 목록, 매칭 가중치, flash 메시지.
- [app/data/skills_dictionary.json](app/data/skills_dictionary.json) — 카테고리별 스킬명+동의어 사전 (커스터마이징 가능).
- [tools/copy_unlock/](tools/copy_unlock/) — 브라우저 전용 북마클릿/유저스크립트, 서버 코드와 무관.

## 주의할 컨벤션

- **DB 마이그레이션**: 전용 마이그레이션 도구가 없습니다. [app/db.py](app/db.py)의 `_migrate_table_columns(table_name, columns)`가 테이블 무관 범용 헬퍼입니다 — `JobPosting`에 컬럼을 추가할 때는 `_JOB_POSTING_NEW_COLUMNS`에 `(컬럼명, DDL타입, 기본값 리터럴)`을 추가하면 `init_db()`가 이를 `_migrate_table_columns("job_postings", _JOB_POSTING_NEW_COLUMNS)`로 호출해 누락된 컬럼만 `ALTER TABLE`로 추가합니다(멱등). 그 뒤 `_backfill_job_postings()`가 **매 startup마다** 실행되지만, 재파싱 대상 쿼리 자체가 멱등(`required_text == ""` 행만 건드림)이라 이미 채워진 행은 재차 건드리지 않고, 컬럼 추가 후 백필이 중간에 실패한 경우도 self-heal 합니다. `Resume` 마이그레이션 배선은 이미 존재하나(`_RESUME_NEW_COLUMNS`, 현재 빈 목록) 컬럼을 추가할 때 여기에 항목을 넣고, 기존 행을 채워야 하면 전용 백필 함수를 추가해 `init_db()`에서 호출하세요.
- **스크립트 인식 단어 경계**: 한글은 조사가 단어에 바로 붙기 때문에, `skill_extractor.py`의 `term_pattern()`이 한글/영문 스크립트별로 다른 경계 규칙을 쓰며 `job_parser.py`도 이를 공유합니다. 유사한 텍스트 매칭 로직을 추가할 때 이 패턴을 재사용하세요.
- **템플릿/필터 공유**: 새 라우터를 추가할 때 `Jinja2Templates`를 직접 생성하지 말고 `from app.templates import templates`를 사용하세요 — 그래야 `bulleted` 필터와 `flash_messages`·`JOB_STATUS_DEFAULT` 전역이 자동으로 딸려옵니다. 반복되는 마크업은 `_`로 시작하는 파셜의 `{% macro %}`로 뽑아 재사용합니다 — `_job_form.html`(공고 폼), `_resume_fields.html`(이력서 항목), `_filter_group.html`(체크박스 필터 그룹), `_coaching.html`(`score_card`/`category_gaps`/`suggestion_list`).
- **라우터 응답**: `templates.TemplateResponse(request, "name.html", {...})` 시그니처를 사용하세요(`request`가 첫 인자). 폼 검증은 `app/services/validation.py::require_fields`, 공고 폼은 `jobs.py::JobForm` 의존성 + `_persist_job()`, 이력서 쓰기는 `app/services/resume_editor.py`(`apply_resume_content`/`new_resume`/`validate_resume_content`)를 재사용합니다.
- **한국어 UI**: 상수, 템플릿, flash 메시지, 에러 문자열은 한국어로 작성되어 있습니다. 새 문자열도 이 관례를 따르세요 (`ocr.py`의 `RuntimeError` 메시지처럼 사용자에게 그대로 노출되는 예외 메시지도 포함).
- **`JobPosting.applied_resume_id`는 의도적으로 FK가 아닙니다** — `0`=없음, 소프트 참조입니다. 코드베이스에 FK가 하나도 없고 삭제 정책을 강제하지 않기 위함이며, 참조된 이력서가 삭제되면 [job_detail.html](app/templates/job_detail.html)이 안내 문구로 저하합니다. `applied_at`도 다른 폼 필드처럼 ISO 문자열(`'YYYY-MM-DD'`)로 저장하고 날짜 계산은 `activity_report._days_since()`가 `ValueError`를 삼켜 처리합니다.
