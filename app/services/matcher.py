from collections import Counter
from dataclasses import dataclass

from app.constants import MATCH_PREFERRED_WEIGHT, MATCH_REQUIRED_WEIGHT
from app.models import JobPosting
from app.schemas import MatchResult, SkillRank
from app.services.skill_extractor import related_skill_map


@dataclass(frozen=True)
class MatchConfig:
    """매칭 점수 계산 파라미터. DEFAULT_CONFIG 가 현행 동작을 재현한다 —
    related_credit 만 예외로, 대체 스킬 보유에 부분 점수를 준다."""

    required_weight: float = MATCH_REQUIRED_WEIGHT
    preferred_weight: float = MATCH_PREFERRED_WEIGHT
    related_credit: float = 0.5  # 정확히 보유=1.0, 대체 스킬 보유=이 값, 없음=0


DEFAULT_CONFIG = MatchConfig()


def _score_axis(owned: set[str], needed: list[str], related_map, credit: float):
    """Return (matched_exact, matched_related, missing, coverage).

    coverage 는 스킬별 점수(정확 1.0 / 대체 `credit` / 없음 0)의 평균.
    missing 은 정확히 보유하지 않은 스킬 전체(대체 보유 포함) — 기존 의미 유지.
    matched_related 는 그 중 대체 스킬로 커버되는 부분집합(정보용).
    """
    if not needed:
        return [], [], [], 1.0
    needed_set = sorted(set(needed))
    exact, related, missing = [], [], []
    total = 0.0
    for skill in needed_set:
        if skill in owned:
            exact.append(skill)
            total += 1.0
        elif owned & related_map.get(skill, frozenset()):
            related.append(skill)
            missing.append(skill)
            total += credit
        else:
            missing.append(skill)
    return exact, related, missing, total / len(needed_set)


def compute_match(
    resume_skills: list[str], job: JobPosting, *, config: MatchConfig = DEFAULT_CONFIG
) -> MatchResult:
    owned = set(resume_skills)
    required = job.required_skills or []
    preferred = job.preferred_skills or []
    has_skill_data = bool(required or preferred)
    related_map = related_skill_map()

    matched_req, related_req, missing_req, req_coverage = _score_axis(
        owned, required, related_map, config.related_credit
    )
    matched_pref, related_pref, missing_pref, pref_coverage = _score_axis(
        owned, preferred, related_map, config.related_credit
    )

    if not has_skill_data:
        # A posting we couldn't extract any skill from carries no matching
        # signal — don't let the "empty means 100%" convention hand it a free
        # 70/30 and float it to the top of the ranking.
        score = 0.0
    elif not required:
        score = pref_coverage * 100
    else:
        score = (
            req_coverage * config.required_weight + pref_coverage * config.preferred_weight
        ) * 100
    return MatchResult(
        job_id=job.id,
        job_title=job.title,
        company=job.company,
        url=job.url or "",
        source_site=job.source_site or "",
        status=job.status or "",
        score=round(score, 1),
        has_skill_data=has_skill_data,
        matched_required=matched_req,
        missing_required=missing_req,
        matched_preferred=matched_pref,
        missing_preferred=missing_pref,
        related_required=related_req,
        related_preferred=related_pref,
    )


def rank_matches(resume_skills: list[str], jobs: list[JobPosting]) -> list[MatchResult]:
    results = [compute_match(resume_skills, job) for job in jobs]
    # Postings with no extractable skill data sink below every scored one.
    return sorted(results, key=lambda r: (r.has_skill_data, r.score), reverse=True)


def skill_ranking(jobs: list[JobPosting]) -> list[SkillRank]:
    """Aggregate how often each skill is asked for (required/preferred) across postings."""
    required_counter: Counter[str] = Counter()
    preferred_counter: Counter[str] = Counter()
    mention_counter: Counter[str] = Counter()  # distinct jobs that mention the skill at all
    for job in jobs:
        required = job.required_skills or []
        preferred = job.preferred_skills or []
        required_counter.update(required)
        preferred_counter.update(preferred)
        mention_counter.update(set(required) | set(preferred))

    all_skills = set(required_counter) | set(preferred_counter)
    total_jobs = len(jobs) or 1
    ranking = []
    for name in all_skills:
        required_count = required_counter.get(name, 0)
        preferred_count = preferred_counter.get(name, 0)
        ranking.append(SkillRank(
            name=name,
            required_count=required_count,
            preferred_count=preferred_count,
            total_count=required_count + preferred_count,
            percentage=round(mention_counter.get(name, 0) / total_jobs * 100, 1),
        ))
    return sorted(ranking, key=lambda r: r.total_count, reverse=True)
