from pydantic import BaseModel


class MatchResult(BaseModel):
    job_id: int
    job_title: str
    company: str
    url: str
    source_site: str
    status: str = ""
    score: float
    has_skill_data: bool = True
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]
    # missing_* 중 대체/인접 스킬로 커버되는 부분집합 (예: React 요구 + Vue 보유)
    related_required: list[str] = []
    related_preferred: list[str] = []
    # 경력 적합도 축 (이력서 total_years vs 공고 experience_level). None = 해당 없음
    # (공고 경력 조건이 '무관'이거나 해석 불가). axes_weight 가 0 이면 점수엔
    # 반영되지 않고 투명 노출용으로만 채워진다.
    experience_fit: float | None = None
    experience_detail: str = ""
    # 직무 적합도 축 (이력서 target_position vs 공고 position). None = 해당 없음
    # (한쪽이라도 미설정이거나 '기타'). experience_fit 과 같은 게이팅.
    position_fit: float | None = None
    position_detail: str = ""


class SkillRank(BaseModel):
    name: str
    required_count: int
    preferred_count: int
    total_count: int
    percentage: float


class CategoryGap(BaseModel):
    category: str
    required_missing: list[str]
    preferred_missing: list[str]
    count: int


class CoachingSuggestion(BaseModel):
    status: str  # "warning" | "info" | "ok"
    title: str
    detail: str


class CoachingResult(BaseModel):
    match: MatchResult
    category_gaps: list[CategoryGap]
    suggestions: list[CoachingSuggestion]
    general_review: list[CoachingSuggestion] = []


class InterviewQuestion(BaseModel):
    category: str
    question: str
    rationale: str = ""


class InterviewQuestionGroup(BaseModel):
    category: str
    description: str
    questions: list[InterviewQuestion]


class StudyTopic(BaseModel):
    title: str
    detail: str
    priority: str  # "높음" | "중간" | "기본"
    source: str = ""


class InterviewPrep(BaseModel):
    match: MatchResult | None = None
    job_linked: bool = False
    groups: list[InterviewQuestionGroup]
    study_topics: list[StudyTopic]
    question_count: int = 0
