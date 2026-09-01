from collections import Counter

from app.constants import MATCH_PREFERRED_WEIGHT, MATCH_REQUIRED_WEIGHT
from app.models import JobPosting
from app.schemas import MatchResult, SkillRank


def _coverage(owned: set[str], needed: list[str]) -> tuple[list[str], list[str], float]:
    if not needed:
        return [], [], 1.0
    needed_set = set(needed)
    matched = sorted(owned & needed_set)
    missing = sorted(needed_set - owned)
    return matched, missing, len(matched) / len(needed_set)


def compute_match(resume_skills: list[str], job: JobPosting) -> MatchResult:
    owned = set(resume_skills)
    required = job.required_skills or []
    preferred = job.preferred_skills or []
    has_skill_data = bool(required or preferred)
    matched_req, missing_req, req_coverage = _coverage(owned, required)
    matched_pref, missing_pref, pref_coverage = _coverage(owned, preferred)

    if not has_skill_data:
        # A posting we couldn't extract any skill from carries no matching
        # signal — don't let _coverage()'s "empty means 100%" convention hand
        # it a free 70/30 and float it to the top of the ranking.
        score = 0.0
    elif not required:
        score = pref_coverage * 100
    else:
        score = (req_coverage * MATCH_REQUIRED_WEIGHT + pref_coverage * MATCH_PREFERRED_WEIGHT) * 100
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
