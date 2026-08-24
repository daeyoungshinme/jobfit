from app.models import JobPosting
from app.schemas import CategoryGap, CoachingResult, CoachingSuggestion
from app.services.matcher import compute_match
from app.services.skill_extractor import skill_category_map

_UNKNOWN_CATEGORY = "기타"


def _group_missing_by_category(missing_required: list[str], missing_preferred: list[str]) -> list[CategoryGap]:
    cat_map = skill_category_map()
    by_category: dict[str, CategoryGap] = {}

    for name in missing_required:
        category = cat_map.get(name, _UNKNOWN_CATEGORY)
        gap = by_category.setdefault(
            category, CategoryGap(category=category, required_missing=[], preferred_missing=[], count=0)
        )
        gap.required_missing.append(name)

    for name in missing_preferred:
        category = cat_map.get(name, _UNKNOWN_CATEGORY)
        gap = by_category.setdefault(
            category, CategoryGap(category=category, required_missing=[], preferred_missing=[], count=0)
        )
        gap.preferred_missing.append(name)

    for gap in by_category.values():
        gap.count = len(gap.required_missing) + len(gap.preferred_missing)

    return sorted(by_category.values(), key=lambda g: (-len(g.required_missing), -g.count))


def _owned_skills_by_category(resume_skills: list[str], categories: set[str]) -> dict[str, list[str]]:
    cat_map = skill_category_map()
    result: dict[str, list[str]] = {category: [] for category in categories}
    for name in resume_skills:
        category = cat_map.get(name)
        if category in result:
            result[category].append(name)
    return result


def _build_suggestions(gaps: list[CategoryGap], owned_by_category: dict[str, list[str]]) -> list[CoachingSuggestion]:
    if not gaps:
        return [
            CoachingSuggestion(
                status="ok",
                title="부족한 스킬이 없습니다",
                detail="이 공고가 요구하는 필수/우대 스킬을 이력서에서 모두 확인했습니다.",
            )
        ]

    total_required = sum(len(gap.required_missing) for gap in gaps)
    total_preferred = sum(len(gap.preferred_missing) for gap in gaps)
    top_gap = max(gaps, key=lambda g: (len(g.required_missing), g.count))

    suggestions = [
        CoachingSuggestion(
            status="warning" if total_required else "info",
            title=f"필수 스킬 {total_required}개, 우대 스킬 {total_preferred}개가 부족합니다",
            detail=f"'{top_gap.category}' 영역을 보완하면 매칭 점수가 가장 크게 오릅니다.",
        )
    ]

    for gap in gaps:
        owned = owned_by_category.get(gap.category, [])
        if gap.required_missing:
            names = ", ".join(gap.required_missing)
            if owned:
                detail = (
                    f"이력서에 같은 영역({', '.join(owned)}) 경험이 있습니다. {names}과(와) 관련된 프로젝트가 있다면 "
                    "'기술 스택'과 프로젝트 설명에 구체적으로 명시하세요."
                )
            else:
                detail = f"{names} 관련 경험이 이력서에서 확인되지 않습니다. 관련 프로젝트가 있다면 추가하고, 없다면 학습 우선순위로 고려하세요."
            suggestions.append(
                CoachingSuggestion(status="warning", title=f"[{gap.category}] 필수 스킬 보완 필요: {names}", detail=detail)
            )
        if gap.preferred_missing:
            names = ", ".join(gap.preferred_missing)
            suggestions.append(
                CoachingSuggestion(
                    status="info",
                    title=f"[{gap.category}] 우대 스킬: {names}",
                    detail=f"필수는 아니지만 {names} 경험이 있다면 이력서에 추가하면 가점 요소가 됩니다.",
                )
            )

    return suggestions


def build_coaching(resume_skills: list[str], job: JobPosting) -> CoachingResult:
    match = compute_match(resume_skills, job)
    gaps = _group_missing_by_category(match.missing_required, match.missing_preferred)
    owned_by_category = _owned_skills_by_category(resume_skills, {gap.category for gap in gaps})
    suggestions = _build_suggestions(gaps, owned_by_category)
    return CoachingResult(match=match, category_gaps=gaps, suggestions=suggestions)
