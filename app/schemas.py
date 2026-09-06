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
