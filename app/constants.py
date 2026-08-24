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

FLASH_MESSAGES = {
    "job_created": ("채용공고가 등록되었습니다.", "success"),
    "job_updated": ("채용공고가 수정되었습니다.", "success"),
    "job_deleted": ("채용공고가 삭제되었습니다.", "success"),
    "resume_uploaded": ("이력서가 업로드되었습니다.", "success"),
    "resume_created": ("이력서가 등록되었습니다.", "success"),
    "resume_deleted": ("이력서가 삭제되었습니다.", "success"),
    "resume_updated": ("이력서가 수정되었습니다.", "success"),
    "job_not_found": ("존재하지 않는 채용공고입니다.", "error"),
    "resume_not_found": ("존재하지 않는 이력서입니다.", "error"),
}

MATCH_REQUIRED_WEIGHT = 0.7
MATCH_PREFERRED_WEIGHT = 0.3

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
