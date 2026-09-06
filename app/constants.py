POSITIONS = [
    "백엔드 개발자",
    "프론트엔드 개발자",
    "풀스택 개발자",
    "안드로이드 개발자",
    "iOS 개발자",
    "데이터 엔지니어",
    "데이터 사이언티스트/AI・ML 엔지니어",
    "DevOps/인프라 엔지니어",
    "QA 엔지니어",
    "기타",
]

EXPERIENCE_LEVELS = [
    "신입",
    "1~3년",
    "3~5년",
    "5~10년",
    "10년 이상",
    "무관",
]

JOB_STATUSES = [
    "관심",
    "지원예정",
    "지원완료",
    "서류합격",
    "면접",
    "최종합격",
    "불합격",
    "보류",
]
JOB_STATUS_DEFAULT = "관심"

# 지원 경로(어디를 통해 지원했는지). job_detail 의 "지원 기록" 폼에서 선택한다.
APPLY_CHANNELS = [
    "사람인",
    "잡코리아",
    "원티드",
    "잡플래닛",
    "LinkedIn",
    "리멤버",
    "회사 채용페이지",
    "헤드헌터",
    "지인 추천",
    "기타",
]

# source_site(소문자) 안에 포함되면 해당 지원 채널을 기본 선택으로 추천한다.
SOURCE_SITE_TO_CHANNEL = {
    "사람인": "사람인",
    "saramin": "사람인",
    "잡코리아": "잡코리아",
    "jobkorea": "잡코리아",
    "원티드": "원티드",
    "wanted": "원티드",
    "잡플래닛": "잡플래닛",
    "jobplanet": "잡플래닛",
    "linkedin": "LinkedIn",
    "링크드인": "LinkedIn",
    "리멤버": "리멤버",
    "remember": "리멤버",
}

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

RESUME_MIN_LENGTH = 300
RESUME_MIN_ACTION_VERB_HITS = 3
RESUME_MIN_QUANT_HITS = 3

REGIONS = [
    "서울",
    "부산",
    "대구",
    "인천",
    "광주",
    "대전",
    "울산",
    "세종",
    "경기",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
]
