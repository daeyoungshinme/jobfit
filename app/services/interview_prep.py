"""규칙 기반 면접 예상 질문 + 스터디 주제 생성.

`job_fit_coach` 와 같은 계층의 순수 서비스. 외부 AI 없이 매칭 결과, 공고 주요
업무, 이력서 섹션, 이력서 리뷰 신호, `app/data/interview_guide.json` 사전을
조합해 결과를 만든다. 공고(job)가 없으면(이력서 단독 모드) 갭·직무 적합성
질문을 빼고 보유 스킬·프로젝트·행동 질문만 생성한다.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

from app.enums import EXPERIENCE_LEVEL, POSITION
from app.models import JobPosting, Resume
from app.schemas import (
    InterviewPrep,
    InterviewQuestion,
    InterviewQuestionGroup,
    MatchResult,
    StudyTopic,
)
from app.services.matcher import compute_match
from app.services.resume_reviewer import review_resume
from app.services.resume_sections import (
    detect_sections,
    first_line_label,
    sections_for_resume,
    split_blocks,
)
from app.services.skill_extractor import skill_category_map
from app.services.text_utils import QUANT_PATTERN, UNKNOWN_CATEGORY, dedupe, strip_bullet, truncate

GUIDE_PATH = Path(__file__).resolve().parent.parent / "data" / "interview_guide.json"

_CAT_ROLE_FIT = "직무 적합성"
_CAT_TECH = "기술 심화"
_CAT_PROJECT = "프로젝트 심화"
_CAT_GAP = "갭 대응"
_CAT_RESUME = "이력서 보완"
_CAT_BEHAVIORAL = "인성·행동"

_CATEGORY_ORDER: list[tuple[str, str]] = [
    (_CAT_ROLE_FIT, "채용공고의 포지션·주요 업무에서 나올 법한 질문입니다."),
    (_CAT_TECH, "이력서에 적힌 기술의 깊이를 확인하는 질문입니다."),
    (_CAT_PROJECT, "이력서의 프로젝트·경력을 파고드는 질문입니다."),
    (_CAT_GAP, "공고가 요구하지만 이력서에서 확인되지 않은 스킬에 대한 질문입니다."),
    (_CAT_RESUME, "이력서 서술의 약점을 면접관이 짚을 법한 질문입니다."),
    (_CAT_BEHAVIORAL, "협업·성장·실패 경험을 묻는 공통 행동 질문입니다."),
]

_MAX_MAIN_TASK_Q = 3
_MAX_TECH_Q = 6
_MAX_PROJECT_BLOCKS = 4
_MAX_GAP_Q = 6
_MAX_BEHAVIORAL_COMMON = 4

_PRIORITY_RANK = {"높음": 0, "중간": 1, "기본": 2}

_GENERIC_TECH_TEMPLATE = "{skill} 관련 경험 중 기술적으로 가장 깊이 파고들었던 부분을 설명해주세요."


@lru_cache(maxsize=1)
def load_interview_guide() -> dict:
    return json.loads(GUIDE_PATH.read_text(encoding="utf-8"))


def _fmt(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def _q(category: str, question: str, rationale: str = "") -> InterviewQuestion:
    return InterviewQuestion(category=category, question=question, rationale=rationale)


def _role_fit_questions(job: JobPosting) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    out: list[InterviewQuestion] = []

    position_label = POSITION.label_of(job.position)
    position_guide = guide.get("positions", {}).get(position_label, {})
    for question in position_guide.get("fit_questions", []):
        out.append(_q(_CAT_ROLE_FIT, question, f"{position_label} 직무에 자주 나오는 질문입니다."))

    task_template = guide.get("main_task_question_template", '"{task}" 관련 경험을 설명해주세요.')
    tasks: list[str] = []
    for line in (job.main_tasks or "").splitlines():
        cleaned = strip_bullet(line).strip(" \t·-–—")
        if len(cleaned) > 6:
            tasks.append(cleaned)
    for task in dedupe(tasks)[:_MAX_MAIN_TASK_Q]:
        out.append(_q(_CAT_ROLE_FIT, _fmt(task_template, task=truncate(task)), "공고 주요 업무에서 도출한 질문입니다."))

    return out


def _tech_skill_order(owned: list[str], match: MatchResult | None) -> list[str]:
    if match is not None:
        return dedupe([*match.matched_required, *match.matched_preferred])
    return dedupe(owned)


def _tech_deep_questions(owned: list[str], match: MatchResult | None) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    cat_map = skill_category_map()
    skills_guide = guide.get("skills", {})
    categories_guide = guide.get("categories", {})

    rationale = (
        "이력서와 공고가 함께 요구하는 스킬이라 깊이 검증될 가능성이 높습니다."
        if match is not None
        else "이력서에서 인식된 스킬입니다."
    )

    out: list[InterviewQuestion] = []
    for skill in _tech_skill_order(owned, match)[:_MAX_TECH_Q]:
        templates = (
            skills_guide.get(skill, {}).get("question_templates")
            or categories_guide.get(cat_map.get(skill, UNKNOWN_CATEGORY), {}).get("question_templates")
            or [_GENERIC_TECH_TEMPLATE]
        )
        out.append(_q(_CAT_TECH, _fmt(templates[0], skill=skill), rationale))
    return out


def _project_questions(sections: dict[str, str]) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    project_template = guide.get("project_question_template", '"{project}" 에 대해 설명해주세요.')
    quant_followup = guide.get("project_quant_followup", '"{project}" 의 성과를 수치로 표현해주세요.')

    text = sections.get("projects") or sections.get("career") or ""
    out: list[InterviewQuestion] = []
    for block in split_blocks(text)[:_MAX_PROJECT_BLOCKS]:
        label = first_line_label(block)
        if not label:
            continue
        out.append(_q(_CAT_PROJECT, _fmt(project_template, project=label), "이력서에 기재된 프로젝트/경력입니다."))
        if not QUANT_PATTERN.search(block):
            out.append(_q(_CAT_PROJECT, _fmt(quant_followup, project=label), "이 항목에 정량적 성과 표현이 없어 나올 수 있는 후속 질문입니다."))
    return out


def _gap_questions(match: MatchResult) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    template = guide.get("gap", {}).get(
        "question_template", "이 포지션은 {skill} 경험을 요구합니다. 보완 계획을 설명해주세요."
    )
    return [
        _q(_CAT_GAP, _fmt(template, skill=name), "공고 필수 요건이지만 이력서에서 확인되지 않았습니다.")
        for name in match.missing_required[:_MAX_GAP_Q]
    ]


_SIGNAL_KEYWORDS = ["정량", "액션 동사", "분량", "섹션"]


def _resume_signal_questions(resume: Resume) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    signal_map = guide.get("resume_signal_questions", {})
    reviews = review_resume(
        resume.raw_text or "", len(resume.extracted_skills or []), sections=detect_sections(resume)
    )

    out: list[InterviewQuestion] = []
    used: set[str] = set()
    for review in reviews:
        if review.status != "warning":
            continue
        title = review.title
        for keyword in _SIGNAL_KEYWORDS:
            if keyword in title and keyword not in used and keyword in signal_map:
                used.add(keyword)
                out.append(_q(_CAT_RESUME, signal_map[keyword], "이력서 리뷰에서 확인된 개선 포인트입니다."))
                break
    return out


def _experience_bucket(experience_level: str) -> str | None:
    """경력 코드 또는 자유 입력 범위("2~8년") → 행동 질문 버킷("신입"/"경력"/None)."""
    member = EXPERIENCE_LEVEL.get(EXPERIENCE_LEVEL.normalize(experience_level))
    if member is not None:
        return member.meta.get("bucket")
    lead = re.match(r"\s*(\d+)", experience_level or "")
    if lead:
        return "신입" if int(lead.group(1)) == 0 else "경력"
    return None


def _behavioral_questions(job: JobPosting | None) -> list[InterviewQuestion]:
    guide = load_interview_guide()
    behavioral = guide.get("behavioral", {})

    out = [
        _q(_CAT_BEHAVIORAL, question, "직무·경력과 무관하게 자주 나오는 공통 질문입니다.")
        for question in behavioral.get("공통", [])[:_MAX_BEHAVIORAL_COMMON]
    ]
    bucket = _experience_bucket(job.experience_level or "") if job is not None else None
    if bucket:
        for question in behavioral.get(bucket, []):
            out.append(_q(_CAT_BEHAVIORAL, question, f"{bucket} 지원자에게 나올 법한 질문입니다."))
    return out


def _group_questions(questions: list[InterviewQuestion]) -> list[InterviewQuestionGroup]:
    groups: list[InterviewQuestionGroup] = []
    for category, description in _CATEGORY_ORDER:
        seen: set[str] = set()
        picked: list[InterviewQuestion] = []
        for question in questions:
            if question.category != category or question.question in seen:
                continue
            seen.add(question.question)
            picked.append(question)
        if picked:
            groups.append(InterviewQuestionGroup(category=category, description=description, questions=picked))
    return groups


def _study_point_for_skill(skill: str) -> str:
    guide = load_interview_guide()
    cat_map = skill_category_map()
    points = (
        guide.get("skills", {}).get(skill, {}).get("study_points")
        or guide.get("categories", {}).get(cat_map.get(skill, UNKNOWN_CATEGORY), {}).get("study_points")
        or [guide.get("gap", {}).get("study_point_template", "{skill}: 공식 문서로 기본기를 학습하세요.")]
    )
    return _fmt(points[0], skill=skill)


def _add_topic(
    topics: list[StudyTopic], seen: set[str], *, title: str, detail: str, priority: str, source: str
) -> None:
    key = title.strip().lower()
    if key in seen:
        return
    seen.add(key)
    topics.append(StudyTopic(title=title, detail=detail, priority=priority, source=source))


def _study_topics(owned: list[str], match: MatchResult | None, job: JobPosting | None) -> list[StudyTopic]:
    guide = load_interview_guide()
    cat_map = skill_category_map()
    topics: list[StudyTopic] = []
    seen: set[str] = set()

    if job is not None and match is not None:
        for name in match.missing_required:
            _add_topic(
                topics, seen,
                title=f"{name} 학습", detail=_study_point_for_skill(name),
                priority="높음", source=f"필수 스킬 갭: {name}",
            )
        for name in match.missing_preferred:
            _add_topic(
                topics, seen,
                title=f"{name} 학습", detail=_study_point_for_skill(name),
                priority="중간", source=f"우대 스킬 갭: {name}",
            )
        position_label = POSITION.label_of(job.position)
        for topic in guide.get("positions", {}).get(position_label, {}).get("study_topics", []):
            _add_topic(
                topics, seen,
                title=topic.get("title", ""), detail=topic.get("detail", ""),
                priority="기본", source=f"직무 공통: {position_label}",
            )
    else:
        by_category: dict[str, list[str]] = {}
        for name in dedupe(owned):
            by_category.setdefault(cat_map.get(name, UNKNOWN_CATEGORY), []).append(name)
        categories_guide = guide.get("categories", {})
        for category, names in by_category.items():
            points = categories_guide.get(category, {}).get("study_points")
            if not points:
                continue
            _add_topic(
                topics, seen,
                title=f"{category} 심화", detail=_fmt(points[0], skill=", ".join(names[:2])),
                priority="기본", source=f"보유 스킬 심화: {category}",
            )

    topics.sort(key=lambda t: (_PRIORITY_RANK.get(t.priority, 9), t.title))
    return topics


def build_interview_prep(resume: Resume, job: JobPosting | None) -> InterviewPrep:
    match = (
        compute_match(resume.extracted_skills or [], job, resume=resume)
        if job is not None
        else None
    )
    sections = sections_for_resume(resume)
    owned = list(resume.extracted_skills or [])

    questions: list[InterviewQuestion] = []
    if job is not None and match is not None:
        questions += _role_fit_questions(job)
        questions += _gap_questions(match)
    questions += _tech_deep_questions(owned, match)
    questions += _project_questions(sections)
    questions += _resume_signal_questions(resume)
    questions += _behavioral_questions(job)

    groups = _group_questions(questions)
    topics = _study_topics(owned, match, job)

    return InterviewPrep(
        match=match,
        job_linked=job is not None,
        groups=groups,
        study_topics=topics,
        question_count=sum(len(group.questions) for group in groups),
    )
