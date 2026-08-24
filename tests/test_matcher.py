from app.models import JobPosting
from app.services.matcher import compute_match, rank_matches, skill_ranking


def make_job(id, title, required, preferred, position="백엔드 개발자"):
    job = JobPosting(
        title=title,
        company="테스트",
        position=position,
        raw_text="",
        required_skills=required,
        preferred_skills=preferred,
    )
    job.id = id
    return job


def test_compute_match_full_coverage_scores_100():
    job = make_job(1, "완전 매칭 공고", ["Python", "FastAPI"], ["Docker"])
    result = compute_match(["Python", "FastAPI", "Docker"], job)
    assert result.score == 100.0
    assert result.missing_required == []
    assert result.missing_preferred == []


def test_compute_match_partial_coverage():
    job = make_job(1, "부분 매칭 공고", ["Python", "FastAPI"], ["Docker"])
    result = compute_match(["Python"], job)
    assert result.missing_required == ["FastAPI"]
    assert result.missing_preferred == ["Docker"]
    assert 0 < result.score < 100


def test_compute_match_no_requirements_scores_full_on_that_axis():
    job = make_job(1, "요건 없음", [], [])
    result = compute_match(["Python"], job)
    assert result.score == 100.0


def test_rank_matches_orders_by_score_desc():
    strong = make_job(1, "강한 매칭", ["Python"], [])
    weak = make_job(2, "약한 매칭", ["Python", "Kubernetes", "AWS"], [])
    results = rank_matches(["Python"], [weak, strong])
    assert results[0].job_id == strong.id


def test_skill_ranking_counts_and_percentage():
    jobs = [
        make_job(1, "A", ["Python"], []),
        make_job(2, "B", ["Python"], ["Docker"]),
        make_job(3, "C", [], ["Docker"]),
    ]
    ranking = {r.name: r for r in skill_ranking(jobs)}
    assert ranking["Python"].required_count == 2
    assert ranking["Python"].total_count == 2
    assert ranking["Docker"].preferred_count == 2
    assert ranking["Python"].percentage == round(2 / 3 * 100, 1)
