from app.schemas import CoachingSuggestion
from app.services.resume_reviewer import _ACTION_VERBS, review_resume


def test_action_verbs_use_hangul_for_haegyeol():
    assert "해결" in _ACTION_VERBS
    assert "解決" not in _ACTION_VERBS
    assert "解결" not in _ACTION_VERBS


def test_review_resume_returns_coaching_suggestions():
    suggestions = review_resume("텍스트", extracted_skill_count=0)
    assert suggestions and all(isinstance(s, CoachingSuggestion) for s in suggestions)


def test_review_resume_counts_haegyeol_as_action_verb():
    text = "이 프로젝트에서 발생한 성능 문제를 해결하고 새 기능을 개발했으며 아키텍처 설계도 담당했습니다. " * 10
    suggestions = review_resume(text, extracted_skill_count=5)
    action_suggestion = next(s for s in suggestions if "액션 동사" in s.title)
    assert action_suggestion.status == "ok"


def test_short_resume_gets_length_warning():
    suggestions = review_resume("짧은 이력서", extracted_skill_count=0)
    length_suggestion = next(s for s in suggestions if "분량" in s.title)
    assert length_suggestion.status == "warning"


def test_long_resume_gets_length_ok():
    text = "충분히 긴 이력서 내용입니다. " * 30
    suggestions = review_resume(text, extracted_skill_count=0)
    length_suggestion = next(s for s in suggestions if "분량" in s.title)
    assert length_suggestion.status == "ok"


def test_missing_section_reports_warning():
    suggestions = review_resume("아무 키워드도 없는 짧은 텍스트", extracted_skill_count=0)
    career_suggestion = next(s for s in suggestions if "경력/경험" in s.title)
    assert career_suggestion.status == "warning"


def test_present_section_reports_ok():
    suggestions = review_resume("이 회사에서 3년간 근무하며 경력을 쌓았습니다.", extracted_skill_count=0)
    career_suggestion = next(s for s in suggestions if "경력/경험" in s.title)
    assert career_suggestion.status == "ok"


def test_insufficient_quant_expressions_gets_warning():
    suggestions = review_resume("특별한 수치 표현이 없는 문장입니다.", extracted_skill_count=0)
    quant_suggestion = next(s for s in suggestions if "정량적 성과" in s.title)
    assert quant_suggestion.status == "warning"


def test_sufficient_quant_expressions_gets_ok():
    text = "처리 시간을 30% 단축했고 트래픽을 20% 증가시켰으며 오류를 50% 감소시켰습니다."
    suggestions = review_resume(text, extracted_skill_count=0)
    quant_suggestion = next(s for s in suggestions if "정량적 성과" in s.title)
    assert quant_suggestion.status == "ok"


def test_zero_extracted_skills_gets_warning():
    suggestions = review_resume("텍스트", extracted_skill_count=0)
    skill_suggestion = next(s for s in suggestions if "기술 스킬" in s.title)
    assert skill_suggestion.status == "warning"


def test_nonzero_extracted_skills_gets_ok():
    suggestions = review_resume("텍스트", extracted_skill_count=3)
    skill_suggestion = next(s for s in suggestions if "기술 스킬" in s.title)
    assert skill_suggestion.status == "ok"
    assert "3개" in skill_suggestion.title


def test_warnings_are_sorted_before_ok_suggestions():
    # Mixed-status resume: length/career/project/quant/action-verbs pass,
    # but education/tech-stack sections and skill count don't — the warnings
    # among these should be moved ahead of the ok's in the final ordering.
    text = (
        "3년간 백엔드 개발자로 근무하며 다양한 프로젝트를 진행했습니다. " * 7
        + "처리 시간을 30% 단축했고 트래픽을 20% 증가시켰으며 오류를 50% 감소시켰습니다. "
        + "시스템을 설계하고 구축하며 운영을 주도했습니다."
    )
    suggestions = review_resume(text, extracted_skill_count=0)
    statuses = [s.status for s in suggestions]
    assert "warning" in statuses and "ok" in statuses
    first_ok_index = statuses.index("ok")
    assert all(status == "warning" for status in statuses[:first_ok_index])
