from types import SimpleNamespace

from app.schemas import SkillRank
from app.services.matcher import (
    MatchConfig,
    compute_match,
    experience_fit,
    position_fit,
    rank_matches,
    scarcity_weights,
    skill_ranking,
)


def test_compute_match_full_coverage_scores_100(make_job):
    job = make_job(1, "완전 매칭 공고", ["Python", "FastAPI"], ["Docker"])
    result = compute_match(["Python", "FastAPI", "Docker"], job)
    assert result.score == 100.0
    assert result.missing_required == []
    assert result.missing_preferred == []


def test_compute_match_partial_coverage(make_job):
    job = make_job(1, "부분 매칭 공고", ["Python", "FastAPI"], ["Docker"])
    result = compute_match(["Python"], job)
    assert result.missing_required == ["FastAPI"]
    assert result.missing_preferred == ["Docker"]
    assert 0 < result.score < 100


def test_compute_match_no_skill_data_scores_zero_and_is_flagged(make_job):
    job = make_job(1, "요건 없음", [], [])
    result = compute_match(["Python"], job)
    assert result.score == 0.0
    assert result.has_skill_data is False


def test_compute_match_preferred_only_scores_from_preferred_axis(make_job):
    job = make_job(1, "우대만 있는 공고", [], ["Docker", "AWS"])
    result = compute_match(["Docker"], job)
    assert result.has_skill_data is True
    assert result.score == 50.0


def test_rank_matches_sinks_jobs_without_skill_data(make_job):
    scored = make_job(1, "스킬 있음", ["Python"], [])
    blank = make_job(2, "스킬 없음", [], [])
    results = rank_matches(["Python"], [blank, scored])
    assert results[0].job_id == scored.id
    assert results[-1].job_id == blank.id


def test_rank_matches_orders_by_score_desc(make_job):
    strong = make_job(1, "강한 매칭", ["Python"], [])
    weak = make_job(2, "약한 매칭", ["Python", "Kubernetes", "AWS"], [])
    results = rank_matches(["Python"], [weak, strong])
    assert results[0].job_id == strong.id


def test_related_skill_gives_partial_credit(make_job):
    # 공고는 React 요구, 이력서엔 Vue — 사전상 대체 스킬이라 부분 점수.
    job = make_job(1, "프론트 공고", ["React"], [])
    exact = compute_match(["React"], job).score
    related = compute_match(["Vue"], job).score
    none = compute_match(["Python"], job).score
    assert none < related < exact
    # req 0.5 (Vue→대체) * 0.7 + pref 1.0(빈 축) * 0.3
    assert related == round((0.5 * 0.7 + 1.0 * 0.3) * 100, 1)


def test_related_skill_listed_in_related_required_but_still_missing(make_job):
    job = make_job(1, "공고", ["React", "Python"], [])
    r = compute_match(["Vue", "Python"], job)
    assert "React" in r.missing_required          # 정확 보유는 아니므로 여전히 missing
    assert r.related_required == ["React"]         # 대체 보유 표시
    assert "Python" in r.matched_required


def test_related_skill_gets_partial_credit_between_miss_and_exact(make_job):
    job = make_job(1, "공고", ["React"], [])
    exact = compute_match(["React"], job).score       # 정확 보유
    related = compute_match(["Vue"], job).score       # 대체 스킬만 보유
    none = compute_match(["Python"], job).score       # 무관
    assert none < related < exact                     # related 는 부분 점수


def test_scarcity_weights_penalize_rare_skills_more():
    ranking = [
        SkillRank(name="Python", required_count=10, preferred_count=0, total_count=10, percentage=100.0),
        SkillRank(name="Rust", required_count=1, preferred_count=0, total_count=1, percentage=10.0),
    ]
    weights = scarcity_weights(ranking)
    assert weights["Python"] == 1.0
    assert weights["Rust"] > weights["Python"]


def test_skill_weights_make_rare_skill_gap_hurt_more(make_job):
    # 두 스킬 모두 요구, 하나만 보유. 희소 스킬(Rust)을 놓치면 흔한 스킬(Python)을
    # 놓칠 때보다 점수가 더 낮아야 한다.
    job = make_job(1, "공고", ["Python", "Rust"], [])
    weights = {"Python": 1.0, "Rust": 4.0}
    miss_rare = compute_match(["Python"], job, skill_weights=weights).score
    miss_common = compute_match(["Rust"], job, skill_weights=weights).score
    assert miss_rare < miss_common
    # weights=None 이면 둘이 같다 (현행).
    assert (
        compute_match(["Python"], job).score == compute_match(["Rust"], job).score
    )


def test_experience_fit_in_range_near_and_far():
    assert experience_fit(4, "y3_5")[0] == 1.0            # 범위 안
    assert experience_fit(2, "y3_5")[0] == 0.7            # 1년 부족 → 근접
    assert experience_fit(0, "y5_10")[0] < 0.7            # 5년 부족 → 멀다
    assert experience_fit(3, "무관") == (None, "")        # 축 제외
    assert experience_fit(3, "") == (None, "")            # 미상
    assert experience_fit(6, "2~8년")[0] == 1.0           # 자유 입력 범위 파싱(비표준)
    assert experience_fit(10, "5년 이상")[0] == 1.0       # 하한만 있는 조건
    assert experience_fit(12, "y3_5")[0] < 0.7            # 상한 초과(과경력)도 감점
    assert experience_fit(0, "entry") == (1.0, "보유 0년 · 요구 신입")
    assert experience_fit(3, "협의")[0] is None           # 해석 불가 자유 텍스트


def test_axes_weight_zero_keeps_score_unchanged(make_job):
    job = make_job(1, "공고", ["Python"], [])
    job.experience_level = "y5_10"
    resume = SimpleNamespace(total_years=1)
    r = compute_match(["Python"], job, resume=resume)
    assert r.score == 100.0                # weight 0 → 경력 미반영
    assert r.experience_fit is not None    # 투명 노출용으로는 채워짐
    assert "요구 5~10년" in r.experience_detail


def test_axes_weight_folds_experience_into_score(make_job):
    job = make_job(1, "공고", ["Python"], [])
    job.experience_level = "y5_10"
    resume = SimpleNamespace(total_years=1)
    cfg = MatchConfig(axes_weight=0.25)
    r = compute_match(["Python"], job, resume=resume, config=cfg)
    assert r.score < 100.0  # 경력 미달이 점수를 끌어내린다


def test_position_fit_exact_adjacent_and_far():
    assert position_fit("backend", "backend")[0] == 1.0
    assert position_fit("backend", "fullstack")[0] == 0.6   # 인접(POSITION meta)
    assert position_fit("fullstack", "backend")[0] == 0.6   # 양방향
    assert position_fit("backend", "frontend")[0] == 0.2    # 다른 직무
    assert position_fit("", "backend") == (None, "")        # 이력서 미설정
    assert position_fit("backend", "") == (None, "")        # 공고 미상
    assert position_fit("other", "backend") == (None, "")   # '기타'는 축 제외
    detail = position_fit("backend", "fullstack")[1]
    assert "인접 직무" in detail


def test_axes_weight_blends_experience_and_position_mean(make_job):
    job = make_job(1, "공고", ["Python"], [], position="frontend")
    job.experience_level = "y5_10"
    resume = SimpleNamespace(total_years=1, target_position="backend")  # 경력 미달 + 다른 직무

    transparent = compute_match(["Python"], job, resume=resume)
    assert transparent.score == 100.0
    assert transparent.position_fit == 0.2
    assert transparent.experience_fit is not None

    folded = compute_match(["Python"], job, resume=resume, config=MatchConfig(axes_weight=0.25))
    # score = 100*0.75 + mean(exp_fit, 0.2)*100*0.25 < 100
    assert folded.score < transparent.score


def test_skill_ranking_counts_and_percentage(make_job):
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


def test_skill_ranking_percentage_capped_when_skill_in_both_lists(make_job):
    # A skill listed as both required and preferred on the same job must count
    # as one job mention, so the percentage can never exceed 100%.
    jobs = [make_job(1, "A", ["Python"], ["Python"])]
    ranking = {r.name: r for r in skill_ranking(jobs)}
    assert ranking["Python"].total_count == 2
    assert ranking["Python"].percentage == 100.0
