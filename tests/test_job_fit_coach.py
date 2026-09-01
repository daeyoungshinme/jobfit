from app.models import JobPosting
from app.services.job_fit_coach import build_coaching


def make_job(id, required, preferred, position="백엔드 개발자"):
    job = JobPosting(
        title="테스트 공고",
        company="테스트",
        position=position,
        raw_text="",
        required_skills=required,
        preferred_skills=preferred,
    )
    job.id = id
    return job


def test_build_coaching_no_gaps_reports_ok():
    job = make_job(1, ["Python"], ["Docker"])
    result = build_coaching(["Python", "Docker"], job)
    assert result.category_gaps == []
    assert len(result.suggestions) == 1
    assert result.suggestions[0].status == "ok"


def test_build_coaching_groups_missing_skills_by_category():
    job = make_job(1, ["Python", "AWS"], ["Kubernetes"])
    result = build_coaching([], job)

    categories = {gap.category for gap in result.category_gaps}
    assert "언어" in categories
    assert "클라우드/인프라" in categories

    aws_gap = next(gap for gap in result.category_gaps if "AWS" in gap.required_missing)
    assert "Kubernetes" in aws_gap.preferred_missing


def test_build_coaching_mentions_owned_related_skill_in_same_category():
    job = make_job(1, ["Kubernetes"], [])
    result = build_coaching(["AWS"], job)

    infra_suggestion = next(s for s in result.suggestions if "Kubernetes" in s.title)
    assert "AWS" in infra_suggestion.detail


def test_build_coaching_suggestions_lead_with_summary_counts():
    job = make_job(1, ["Python", "FastAPI"], ["Docker"])
    result = build_coaching([], job)

    summary = result.suggestions[0]
    assert summary.status == "warning"
    assert "필수 스킬 2개" in summary.title
    assert "우대 스킬 1개" in summary.title


def test_build_coaching_includes_general_resume_review():
    job = make_job(1, ["Python"], [])
    result = build_coaching(["Python"], job, resume_text="너무 짧은 이력서")

    assert result.general_review
    assert any(s.status == "warning" for s in result.general_review)
