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
    matched_req, missing_req, req_coverage = _coverage(owned, job.required_skills or [])
    matched_pref, missing_pref, pref_coverage = _coverage(owned, job.preferred_skills or [])

    score = (req_coverage * MATCH_REQUIRED_WEIGHT + pref_coverage * MATCH_PREFERRED_WEIGHT) * 100
    return MatchResult(
        job_id=job.id,
        job_title=job.title,
        company=job.company,
        url=job.url or "",
        source_site=job.source_site or "",
        score=round(score, 1),
        matched_required=matched_req,
        missing_required=missing_req,
        matched_preferred=matched_pref,
        missing_preferred=missing_pref,
    )


def rank_matches(resume_skills: list[str], jobs: list[JobPosting]) -> list[MatchResult]:
    results = [compute_match(resume_skills, job) for job in jobs]
    return sorted(results, key=lambda r: r.score, reverse=True)


def skill_ranking(jobs: list[JobPosting]) -> list[SkillRank]:
    """Aggregate how often each skill is asked for (required/preferred) across postings."""
    required_counter: Counter[str] = Counter()
    preferred_counter: Counter[str] = Counter()
    for job in jobs:
        required_counter.update(job.required_skills or [])
        preferred_counter.update(job.preferred_skills or [])

    all_skills = set(required_counter) | set(preferred_counter)
    total_jobs = len(jobs) or 1
    ranking = []
    for name in all_skills:
        required_count = required_counter.get(name, 0)
        preferred_count = preferred_counter.get(name, 0)
        total = required_count + preferred_count
        ranking.append(SkillRank(
            name=name,
            required_count=required_count,
            preferred_count=preferred_count,
            total_count=total,
            percentage=round(total / total_jobs * 100, 1),
        ))
    return sorted(ranking, key=lambda r: r.total_count, reverse=True)
