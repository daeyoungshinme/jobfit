import math
import re
from collections import Counter
from dataclasses import dataclass

from app.constants import MATCH_PREFERRED_WEIGHT, MATCH_REQUIRED_WEIGHT
from app.enums import EXPERIENCE_LEVEL
from app.models import JobPosting
from app.schemas import MatchResult, SkillRank
from app.services.skill_extractor import related_skill_map


@dataclass(frozen=True)
class MatchConfig:
    """매칭 점수 계산 파라미터. DEFAULT_CONFIG 가 현행 동작을 재현한다 —
    related_credit 만 예외로, 대체 스킬 보유에 부분 점수를 준다.

    experience_weight 는 기본 0 이라 경력축이 점수에 반영되지 않는다(투명 노출만).
    라우터가 `?axes=1` 등으로 명시적으로 켤 때만 최종 점수에 섞인다."""

    required_weight: float = MATCH_REQUIRED_WEIGHT
    preferred_weight: float = MATCH_PREFERRED_WEIGHT
    related_credit: float = 0.5  # 정확히 보유=1.0, 대체 스킬 보유=이 값, 없음=0
    experience_weight: float = 0.0  # 경력 적합도 축의 최종 점수 반영 비중 (0 = 스킬 점수만)


DEFAULT_CONFIG = MatchConfig()

# 희소성 가중치의 하한 빈도 — 이보다 드문 스킬도 가중치를 더 키우지 않는다.
SCARCITY_MIN_FRACTION = 0.05


def scarcity_weights(ranking: list[SkillRank]) -> dict[str, float]:
    """스킬 이름 → 희소성 가중치. 적게 요구되는 스킬일수록 큰 값이라, 그 스킬을
    보유하지 못했을 때 매칭 점수가 더 크게 깎인다(흔한 스킬 미보유는 덜 깎임).

    `SkillRank.percentage`(전체 공고 중 그 스킬을 언급한 비율) 의 제곱근 역수를
    쓴다 — 100%→1.0, 25%→2.0, 5% 이하→약 4.5 로 완만하게 증가한다. 표본이
    적을 때 한 스킬이 점수를 지배하지 않도록 상한을 둔 형태다.
    """
    weights: dict[str, float] = {}
    for rank in ranking:
        fraction = max(rank.percentage / 100.0, SCARCITY_MIN_FRACTION)
        weights[rank.name] = round(1.0 / math.sqrt(fraction), 3)
    return weights


def _score_axis(
    owned: set[str],
    needed: list[str],
    related_map,
    credit: float,
    weights: dict[str, float] | None = None,
):
    """Return (matched_exact, matched_related, missing, coverage).

    coverage 는 스킬별 점수(정확 1.0 / 대체 `credit` / 없음 0)의 (가중) 평균.
    `weights` 가 주어지면 스킬별 가중 평균 `Σ(w_i·hit_i)/Σw_i` — 희소 스킬
    미보유에 더 큰 감점을 주기 위해 라우터가 `scarcity_weights()` 를 넘긴다.
    missing 은 정확히 보유하지 않은 스킬 전체(대체 보유 포함) — 기존 의미 유지.
    matched_related 는 그 중 대체 스킬로 커버되는 부분집합(정보용).
    """
    if not needed:
        return [], [], [], 1.0
    needed_set = sorted(set(needed))
    exact, related, missing = [], [], []
    total = 0.0
    denom = 0.0
    for skill in needed_set:
        weight = weights.get(skill, 1.0) if weights else 1.0
        denom += weight
        if skill in owned:
            exact.append(skill)
            total += weight
        elif owned & related_map.get(skill, frozenset()):
            related.append(skill)
            missing.append(skill)
            total += weight * credit
        else:
            missing.append(skill)
    return exact, related, missing, (total / denom if denom else 1.0)


_EXPERIENCE_RANGE_RE = re.compile(r"(\d{1,2})\s*~\s*(\d{1,2})\s*년")
_EXPERIENCE_MIN_RE = re.compile(r"(\d{1,2})\s*년\s*(?:이상|~|\+)")


def _experience_bounds(job_experience: str) -> tuple[int, int | None] | None:
    """공고 경력 조건 → (min_years, max_years|None). 축이 적용되지 않으면 None
    ('무관'·미상·자유 텍스트). 표준 버킷 코드/라벨을 먼저 보고, 아니면
    '3~5년'·'5년 이상' 같은 자유 입력 문자열을 정규식으로 해석한다."""
    if not job_experience:
        return None
    member = EXPERIENCE_LEVEL.get(EXPERIENCE_LEVEL.normalize(job_experience))
    if member is not None:
        if member.meta.get("bucket") is None:  # "무관"
            return None
        return member.meta.get("min_years", 0), member.meta.get("max_years")
    range_match = _EXPERIENCE_RANGE_RE.search(job_experience)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return (lo, hi) if lo <= hi else (hi, lo)
    min_match = _EXPERIENCE_MIN_RE.search(job_experience)
    if min_match:
        return int(min_match.group(1)), None
    return None


def _describe_bounds(lo: int, hi: int | None) -> str:
    if hi is None:
        return f"{lo}년 이상"
    if lo == hi:
        return "신입" if lo == 0 else f"{lo}년"
    return f"{lo}~{hi}년"


def experience_fit(total_years: int, job_experience: str) -> tuple[float | None, str]:
    """(적합도 0~1, 설명 문자열). 축이 적용되지 않으면 (None, "")."""
    bounds = _experience_bounds(job_experience)
    if bounds is None:
        return None, ""
    lo, hi = bounds
    detail = f"보유 {total_years}년 · 요구 {_describe_bounds(lo, hi)}"
    if total_years < lo:
        gap = lo - total_years
    elif hi is not None and total_years > hi:
        gap = total_years - hi
    else:
        gap = 0
    if gap == 0:
        fit = 1.0
    elif gap <= 2:
        fit = 0.7
    else:
        fit = max(0.2, round(1.0 - gap * 0.15, 2))
    return fit, detail


def compute_match(
    resume_skills: list[str],
    job: JobPosting,
    *,
    config: MatchConfig = DEFAULT_CONFIG,
    skill_weights: dict[str, float] | None = None,
    resume=None,
) -> MatchResult:
    owned = set(resume_skills)
    required = job.required_skills or []
    preferred = job.preferred_skills or []
    has_skill_data = bool(required or preferred)
    related_map = related_skill_map()

    matched_req, related_req, missing_req, req_coverage = _score_axis(
        owned, required, related_map, config.related_credit, skill_weights
    )
    matched_pref, related_pref, missing_pref, pref_coverage = _score_axis(
        owned, preferred, related_map, config.related_credit, skill_weights
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

    exp_fit, exp_detail = (None, "")
    if resume is not None:
        exp_fit, exp_detail = experience_fit(
            getattr(resume, "total_years", 0) or 0, job.experience_level or ""
        )
    if has_skill_data and exp_fit is not None and config.experience_weight > 0:
        score = score * (1 - config.experience_weight) + exp_fit * 100 * config.experience_weight

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
        experience_fit=exp_fit,
        experience_detail=exp_detail,
    )


def rank_matches(
    resume_skills: list[str],
    jobs: list[JobPosting],
    *,
    config: MatchConfig = DEFAULT_CONFIG,
    skill_weights: dict[str, float] | None = None,
    resume=None,
) -> list[MatchResult]:
    results = [
        compute_match(
            resume_skills, job, config=config, skill_weights=skill_weights, resume=resume
        )
        for job in jobs
    ]
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
