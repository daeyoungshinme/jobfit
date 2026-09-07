# 도메인 enum(직무/경력/지원상태/지원채널/지역)은 app/enums.py 로 이관됐다 —
# 코드값(DB 저장) ↔ 한국어 라벨(UI) 분리를 위해. 여기 남은 것은 매칭 가중치,
# 업로드 한도, 리뷰 임계값, UI 문구, flash 메시지다.

# 404 detail strings for GET routes. The redirect flows use the *_not_found
# FLASH_MESSAGES entries below; keep the wording of the two in sync.
JOB_NOT_FOUND_DETAIL = "존재하지 않는 채용공고입니다."
RESUME_NOT_FOUND_DETAIL = "존재하지 않는 이력서입니다."
JOB_STATUS_INVALID_DETAIL = "알 수 없는 지원 상태입니다."

# 빈 상태(empty state) 문구 — templates.py에서 Jinja 전역으로 등록해 템플릿이 공유.
# app/static/app.js의 MSG.noRequiredSkills / noPreferredSkills도 같은 문자열로 유지할 것.
EMPTY_SKILLS = "인식된 스킬 없음"
EMPTY_REQUIRED_SKILLS = "인식된 필수 스킬 없음"
EMPTY_PREFERRED_SKILLS = "인식된 우대 스킬 없음"
NO_SKILL_DATA = "스킬 정보 없음"  # 짧은 뱃지용 (표 셀 등)
NO_SKILL_DATA_REASON = "이 공고에서 인식된 스킬이 없어 점수를 계산할 수 없습니다."  # 한 줄 설명용
EMPTY_CATEGORY_GAPS = "부족한 스킬이 없습니다."

# select 안내 옵션 문구
SELECT_PLACEHOLDER = "선택하세요"
SELECT_RESUME_PLACEHOLDER = "이력서를 선택하세요"
SELECT_JOB_PLACEHOLDER = "공고를 선택하세요"

# 기능 명칭. 제목/설명에는 풀네임(FEATURE_*), 버튼·표 셀 링크에는 짧은 라벨(FEATURE_*_SHORT).
FEATURE_TAILOR = "맞춤 이력서 편집"
FEATURE_TAILOR_SHORT = "맞춤 편집"
FEATURE_COACH = "맞춤 이력서 코칭"
FEATURE_COACH_SHORT = "코칭"

FLASH_MESSAGES = {
    "job_created": ("채용공고가 등록되었습니다.", "success"),
    "job_updated": ("채용공고가 수정되었습니다.", "success"),
    "job_deleted": ("채용공고가 삭제되었습니다.", "success"),
    "job_status_updated": ("지원 상태가 변경되었습니다.", "success"),
    "job_status_invalid": (JOB_STATUS_INVALID_DETAIL, "error"),
    "job_application_saved": ("지원 기록이 저장되었습니다.", "success"),
    "job_application_invalid": ("입력한 지원 정보를 확인해주세요.", "error"),
    "resume_uploaded": ("이력서가 업로드되었습니다.", "success"),
    "resume_created": ("이력서가 등록되었습니다.", "success"),
    "resume_deleted": ("이력서가 삭제되었습니다.", "success"),
    "resume_updated": ("이력서가 수정되었습니다.", "success"),
    "job_not_found": (JOB_NOT_FOUND_DETAIL, "error"),
    "resume_not_found": (RESUME_NOT_FOUND_DETAIL, "error"),
}

MATCH_REQUIRED_WEIGHT = 0.7
MATCH_PREFERRED_WEIGHT = 0.3

# Upload cap for résumé files / OCR images. Local single-user tool, so this is a
# sanity bound against an accidental huge file, not a hardened limit.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_MESSAGE = "파일이 너무 큽니다 (최대 10MB)."
UPLOAD_NO_TEXT_MESSAGE = "파일에서 텍스트를 추출하지 못했습니다. 이미지로만 된 파일이면 OCR 기능을 이용해주세요."

# 붙여넣기/OCR 원문의 방어적 상한. 정규식 파서(job_parser)가 병리적 입력에서
# backtracking 하지 않도록 파싱 진입부에서 이 길이로 잘라낸다. 실제 채용공고
# 본문은 이보다 훨씬 짧다.
MAX_RAW_TEXT_CHARS = 50_000

RESUME_MIN_LENGTH = 300
RESUME_MIN_ACTION_VERB_HITS = 3
RESUME_MIN_QUANT_HITS = 3
