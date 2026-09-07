# CLAUDE.md

JobFit — 채용공고/이력서 분석 도구 (FastAPI + SQLite, 서버사이드 렌더링). 사용자 대상 설명(왜 수동 입력인지, 복사 잠금 해제 도구, OCR 사전 설치 등)은 [README.md](README.md)를 참고하세요. 이 파일은 코드를 다룰 때 필요한 실무 정보에 집중합니다.

## 실행 / 테스트

```bash
python -m venv .venv && source .venv/Scripts/activate && pip install -r requirements-dev.txt   # 최초 1회 (런타임만: requirements.txt)
uvicorn app.main:app --reload --port 8100   # 또는 ./dev.sh (Git Bash, 포트 점유 프로세스 정리 후 재기동)
pytest                                       # 전체 (tests/). 설정은 pyproject.toml [tool.pytest.ini_options]
pytest tests/test_matcher.py -q              # 단일 파일 (또는 -k 키워드)
pytest --cov=app --cov-report=term-missing   # 커버리지 (기본 addopts엔 미포함)
```

`pyproject.toml`이 `filterwarnings = ["error"]`로 경고를 에러 취급합니다 — 새 경고가 나오면 무시하지 말고 원인을 고치거나, 서드파티 통제 불가 항목이면 좁은 `ignore` 규칙을 주석과 함께 추가하세요.

데이터는 프로젝트 루트의 `jobfit.db` (SQLite)에 저장됩니다. 외부 AI API는 사용하지 않으며, 스킬 추출/매칭은 전부 정규식·사전 기반 규칙 매칭입니다. OCR([app/services/ocr.py](app/services/ocr.py))만 예외적으로 로컬에 설치된 Tesseract-OCR 바이너리를 호출하지만, 이 역시 외부 서비스 호출이 아닙니다.

테스트는 `tests/conftest.py`의 `db_session`/`client` 픽스처가 in-memory SQLite로 `get_db`를 오버라이드해서 돕니다 — 실제 `jobfit.db`를 건드리지 않으므로, 라우터 테스트를 추가할 때는 이 픽스처를 그대로 재사용하세요.

## 아키텍처

요청 흐름: `routers` → `services` → `models`. 템플릿은 [app/templates.py](app/templates.py)의 단일 `Jinja2Templates` 인스턴스를 모든 라우터가 `from app.templates import templates`로 가져다 쓰는 공유 구조이며, 여기에 `bulleted` 커스텀 필터와 `flash_messages` 전역이 등록되어 있습니다.

- [app/main.py](app/main.py) — FastAPI 앱 진입점, 라우터 등록, `lifespan`에서 `init_db()` 호출, `/static` 마운트, `/` → `/jobs` 리다이렉트.
- [app/templates.py](app/templates.py) — 공유 `Jinja2Templates` 인스턴스, `bulleted` 필터·`flash_messages` 전역 등록.
- [app/static/app.js](app/static/app.js) / [style.css](app/static/style.css) — 페이지 전역에서 로드되는 단일 JS/CSS. 서버사이드 렌더링을 점진적 향상(progressive enhancement)만 하는 계층 (아래 컨벤션 참고).
- [app/templates/base.html](app/templates/base.html) — 공통 레이아웃. `#toast`(flash), `#theme-toggle`, `#main-content` 마크업 계약을 `app.js`와 공유. 탭 UI는 `.tab-btn[data-tab]`/`.tab-panel`(현재 [resume_new.html](app/templates/resume_new.html)).
- [app/routers/jobs.py](app/routers/jobs.py) — 채용공고 CRUD, 스킬 미리보기, OCR 업로드, 출처 사이트(source_site) 추측, 지원 상태(`status`) 빠른 변경(`POST /jobs/{id}/status`), 지원 기록 저장(`POST /jobs/{id}/application` — 상태+지원채널+지원일+사용 이력서+메모).
- [app/routers/resumes.py](app/routers/resumes.py) — 이력서 업로드(PDF/DOCX/TXT)/폼 등록/수정/삭제. 저장 로직은 [app/services/resume_editor.py](app/services/resume_editor.py)의 `apply_resume_content()`에 모여 있음(`analysis.py`의 맞춤 편집과 공유).
- [app/routers/analysis.py](app/routers/analysis.py) — 매칭 대시보드(스킬 수요 랭킹 포함), 이력서-공고 코칭(`/coach`), 공고 맞춤 이력서 편집 워크스페이스(`/tailor`, [tailor.html](app/templates/tailor.html)), 면접 예상 질문(`/interview`, [interview.html](app/templates/interview.html) — 공고 없이 이력서 단독도 가능), 플랫폼 프로필 문구 생성(`/profile`, [profile.html](app/templates/profile.html)), 구직 활동 대시보드(`/activity`, [activity.html](app/templates/activity.html)).
- [app/services/job_parser.py](app/services/job_parser.py) — 정규식 기반 채용공고 섹션 분리(주요업무/자격요건/우대사항/복지/전형). 복지(`benefits_text`)·전형(`process_text`)도 섹션으로 저장(경계로도 작동). `근무조건`/`제출서류` 등만 순수 stop. `guess_posting_fields()`가 제목/회사/직무/경력/주소 + 고용형태/원격/마감일/연봉을 best-effort 추측(못 찾으면 빈 값).
- [app/services/skill_extractor.py](app/services/skill_extractor.py) — `app/data/skills_dictionary.json` 사전 기반 스킬 추출. `term_pattern()`이 스크립트별 단어 경계 규칙을 제공(아래 컨벤션 참고).
- [app/services/matcher.py](app/services/matcher.py) — 이력서-공고 매칭 점수 계산. 가중치(`MATCH_REQUIRED_WEIGHT=0.7`, `MATCH_PREFERRED_WEIGHT=0.3`)는 [app/constants.py](app/constants.py)에 정의. `MatchConfig`(related_credit·experience_weight 등) + `DEFAULT_CONFIG`가 현행 재현. `compute_match(..., *, config, skill_weights, resume)` — `skill_weights`(`scarcity_weights()`가 `skill_ranking` percentage 역수로 산출)는 희소 스킬 미보유에 더 큰 감점, `resume`+`experience_fit()`는 `total_years` vs 공고 `experience_level` 경력 적합도 축(`experience_weight=0` 기본이라 투명 노출만, dashboard `?axes=1`이면 점수 반영). dashboard 라우터가 `scarcity_weights` 항상 주입.
- [app/services/job_fit_coach.py](app/services/job_fit_coach.py) — `matcher`의 매칭 결과를 바탕으로 부족 스킬을 카테고리별로 묶고(`skill_extractor.skill_category_map()` 사용) 공고 맞춤 제안을 만들며, `resume_reviewer.review_resume()` 결과를 `CoachingResult.general_review`로 함께 담음. `analysis.py`의 `/coach`·`/tailor`에서 사용.
- [app/services/resume_parser.py](app/services/resume_parser.py) / [resume_reviewer.py](app/services/resume_reviewer.py) / [resume_editor.py](app/services/resume_editor.py) — 이력서 파일 텍스트 추출 / 규칙 기반 범용 체크리스트(+ `extract_achievement_lines()`) / 편집 내용 저장·스킬 재추출 공용 헬퍼.
- [app/services/resume_sections.py](app/services/resume_sections.py) — 이력서 원문을 섹션(경력/프로젝트/학력/스킬)·블록 단위로 잘라내는 공용 헬퍼. form 이력서는 `structured`를 신뢰하고 file 이력서는 헤딩 라인을 스캔. `interview_prep`이 프로젝트별 질문을 만들 때 사용.
- [app/services/interview_prep.py](app/services/interview_prep.py) — 규칙 기반 면접 예상 질문 + 스터디 주제 생성. `matcher.compute_match`·공고 주요 업무·`resume_sections`·`resume_reviewer.review_resume` 신호·`app/data/interview_guide.json` 사전을 조합. 공고 없으면 갭/직무적합성 질문을 빼고 보유 스킬·프로젝트·행동 질문만. `analysis.py`의 `/interview`에서 사용.
- [app/services/profile_exporter.py](app/services/profile_exporter.py) — 이력서를 LinkedIn/리멤버/원티드·잡코리아 프로필 문구로 규칙 기반 변환. `matcher.skill_ranking`으로 시장 수요 순 스킬 정렬, `resume_reviewer.extract_achievement_lines`로 성과 문장 추출. 자동 게시 없음.
- [app/services/activity_report.py](app/services/activity_report.py) — 채용공고 지원 기록(상태/채널/지원일/`is_inbound`) + `ApplicationEvent` 면접 이벤트를 모아 상태별·채널별 현황, 무응답 경과(`constants.STALE_AFTER_DAYS`), 인바운드 제안, 면접 진행/예정 목록을 만듦. `analysis.py`의 `/activity`에서 사용.
- [app/services/application_log.py](app/services/application_log.py) — `ApplicationEvent`(공고별 상태 전이 / 면접 일정) 기록·조회 헬퍼. `record_status_change`(실제 변경 시에만), `add_interview_event`, `delete_events_for_job`, `timeline()`. `jobs.py`의 상태 변경 라우트들과 `POST /jobs/{id}/interview`에서 사용.
- [app/services/ocr.py](app/services/ocr.py) — 캡처 이미지 OCR. `pytesseract` + 로컬 Tesseract-OCR 바이너리 호출, PATH에 없으면 Windows 기본 설치 경로를 자동 탐색하고 실패 시 한국어 안내 메시지로 `RuntimeError`를 던짐.
- [app/services/text_formatter.py](app/services/text_formatter.py) — 원문 텍스트를 글머리 기호/괄호 소제목 기준으로 escape된 HTML로 렌더링 (`bulleted` 필터의 구현체).
- [app/services/validation.py](app/services/validation.py) — `require_fields()`로 폼 필수값 검증. 라우터들이 공통으로 재사용.
- [app/models.py](app/models.py) — SQLAlchemy 모델 (`JobPosting`, `Resume`, `ApplicationEvent`). 타임스탬프는 네이티브 UTC(`_now()`). `ApplicationEvent.job_id` 는 소프트 참조(FK 아님). `Resume.total_years`/`target_position`(POSITION 코드)는 경력축 매칭용 — 업로드 시 추측, 이력서 폼(`_resume_fields.html::career_meta_fields`)에서 수정.
- [app/db.py](app/db.py) — SQLite 엔진/세션, 테이블 컬럼 마이그레이션(`_migrate_table_columns()`, `job_postings`·`resumes` 양쪽에 배선). 404는 `main.py`의 `StarletteHTTPException` 핸들러가 브라우저엔 `404.html`, API엔 JSON으로 응답.
- [app/schemas.py](app/schemas.py) — Pydantic 응답 스키마.
- [app/enums.py](app/enums.py) — 도메인 enum(`JOB_STATUS`/`EXPERIENCE_LEVEL`/`POSITION`/`REGION`/`APPLY_CHANNEL` + `EMPLOYMENT_TYPE`/`REMOTE_POLICY`). **코드값(ascii slug)이 DB 저장값, 한국어 라벨은 UI 노출용**. `EnumSet.normalize()`가 코드·(구)라벨을 모두 받아 코드로. 서비스 로직은 라벨 문자열 대신 `member.meta` 플래그로 분기(`JOB_STATUS.codes_where("advanced")` 등). 템플릿은 `*_CHOICES` 전역 + `enum_label(enum_name, code)` 필터 사용.
- [app/constants.py](app/constants.py) — 매칭 가중치, 업로드 한도, 리뷰 임계값, UI 문구, flash 메시지 (도메인 enum 은 `app/enums.py` 로 이관됨).
- [app/data/skills_dictionary.json](app/data/skills_dictionary.json) — 카테고리별 스킬명+동의어 사전 (커스터마이징 가능).
- [tools/copy_unlock/](tools/copy_unlock/) — 브라우저 전용 북마클릿/유저스크립트, 서버 코드와 무관.

## 주의할 컨벤션

- **DB 마이그레이션**: 전용 마이그레이션 도구가 없습니다. [app/db.py](app/db.py)의 `_migrate_table_columns(table_name, columns)`가 테이블 무관 범용 헬퍼입니다 — `JobPosting`에 컬럼을 추가할 때는 `_JOB_POSTING_NEW_COLUMNS`에 `(컬럼명, DDL타입, 기본값 리터럴)`을 추가하면 `init_db()`가 이를 `_migrate_table_columns("job_postings", _JOB_POSTING_NEW_COLUMNS)`로 호출해 누락된 컬럼만 `ALTER TABLE`로 추가합니다(멱등). 1회성 데이터 마이그레이션은 `_run_data_migrations()`가 `schema_meta` 테이블의 완료 플래그로 가드해 **DB당 정확히 한 번**만 실행합니다(`_migrate_enum_codes` 라벨→코드 변환, `_backfill_job_postings` 섹션 재파싱). 새 데이터 마이그레이션은 여기에 `if _get_meta("...") != "done": ...; _set_meta(...)` 스텝으로 추가하고 `SCHEMA_VERSION`을 올리세요. `_backfill_job_postings()`는 행 단위 commit + try/except 로 격리돼 있어 불량 `raw_text` 한 행이 startup 을 막지 못합니다. `Resume` 마이그레이션도 같은 패턴(`_RESUME_NEW_COLUMNS` — 현재 `total_years`/`target_position`, 백필은 `_backfill_resume_career()`가 `resume_career_backfilled` 플래그로 가드). 컬럼을 추가할 때 여기에 항목을 넣고, 기존 행을 채워야 하면 전용 백필 함수를 추가해 `_run_data_migrations()`에 스텝으로 넣으세요.
- **스크립트 인식 단어 경계**: 한글은 조사가 단어에 바로 붙기 때문에, `skill_extractor.py`의 `term_pattern()`이 한글/영문 스크립트별로 다른 경계 규칙을 쓰며 `job_parser.py`도 이를 공유합니다. 유사한 텍스트 매칭 로직을 추가할 때 이 패턴을 재사용하세요.
- **템플릿/필터 공유**: 새 라우터를 추가할 때 `Jinja2Templates`를 직접 생성하지 말고 `from app.templates import templates`를 사용하세요 — 그래야 `bulleted` 필터와 `flash_messages`·`JOB_STATUS_DEFAULT`·`EMPTY_*`/`SELECT_*`/`FEATURE_*`/`NO_SKILL_DATA*` 전역이 자동으로 딸려옵니다. 반복되는 마크업은 `_`로 시작하는 파셜의 `{% macro %}`로 뽑아 재사용합니다 — `_job_form.html`(공고 폼), `_resume_fields.html`(이력서 항목), `_filter_group.html`(체크박스 필터 그룹), `_coaching.html`(`score_bar`/`score_card`/`category_gaps`/`suggestion_list`), `_forms.html`(`text_field`/`error_banner`/`delete_form`/`raw_text_editor`), `_pick_target.html`(`pick_target`), `_interview.html`(`question_groups`/`study_topics`).
- **라우터 응답**: `templates.TemplateResponse(request, "name.html", {...})` 시그니처를 사용하세요(`request`가 첫 인자, 컨텍스트에 `"request"`를 다시 넣지 않음). 폼 검증은 `app/services/validation.py::require_fields`, 공고 폼은 `jobs.py::JobForm` 의존성 + `_persist_job()`, 이력서 폼은 `routers/_common.py::ResumeContentForm` + `app/services/resume_editor.py`(`apply_resume_content`/`new_resume`/`validate_resume_content`), 상세 조회는 `routers/_common.py::get_or_404`를 재사용합니다.
- **한국어 UI**: 상수, 템플릿, flash 메시지, 에러 문자열은 한국어로 작성되어 있습니다. 새 문자열도 이 관례를 따르세요 (`ocr.py`의 `RuntimeError` 메시지처럼 사용자에게 그대로 노출되는 예외 메시지도 포함). `app.js`의 사용자 노출 문자열은 상단 `MSG` 객체에 모읍니다.
- **프론트엔드는 점진적 향상만**: 모든 기능은 JS 없이 동작해야 합니다(폼 submit 버튼은 마크업에 남겨두고 `data-autosubmit`으로 change 시 자동 제출, 삭제 확인은 `form[data-confirm]`). `app.js`의 각 `initX()`는 자기 DOM 훅이 없으면 조용히 반환하므로 한 파일이 전 페이지를 커버합니다 — 새 기능도 이 패턴으로 추가하세요. POST 요청은 `postForm(url, params)` 헬퍼(JSON 파싱 + `res.ok` 검사 + `data.detail` 에러 메시지)를 쓰고, 클라이언트 오류 배너는 `showError()`로 띄웁니다(서버 flash와 동일한 `.toast` 마크업). 편의성 실패(출처 사이트 추측 등)는 배너 없이 삼킵니다.
- **`JobPosting.applied_resume_id`는 의도적으로 FK가 아닙니다** — `0`=없음, 소프트 참조입니다. 코드베이스에 FK가 하나도 없고 삭제 정책을 강제하지 않기 위함이며, 참조된 이력서가 삭제되면 [job_detail.html](app/templates/job_detail.html)이 안내 문구로 저하합니다. `applied_at`도 다른 폼 필드처럼 ISO 문자열(`'YYYY-MM-DD'`)로 저장하고 날짜 계산은 `activity_report._days_since()`가 `ValueError`를 삼켜 처리합니다.
