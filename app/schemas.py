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
