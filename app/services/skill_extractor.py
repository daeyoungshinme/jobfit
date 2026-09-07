import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "skills_dictionary.json"

_HAS_KOREAN = re.compile(r"[가-힣]")


@dataclass(frozen=True)
class SkillEntry:
    name: str
    category: str
    terms: tuple[str, ...]  # lowercased name + aliases, used for matching
    related: tuple[str, ...] = ()  # 대체/인접 스킬 이름 (매칭 부분 점수용)


@lru_cache(maxsize=1)
def load_skill_entries() -> tuple[SkillEntry, ...]:
    raw = json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))
    entries = []
    for category, skills in raw.items():
        for skill in skills:
            terms = tuple({skill["name"].lower(), *[a.lower() for a in skill.get("aliases", [])]})
            entries.append(SkillEntry(
                name=skill["name"], category=category, terms=terms,
                related=tuple(skill.get("related", [])),
            ))
    return tuple(entries)


@lru_cache(maxsize=1)
def related_skill_map() -> dict[str, frozenset[str]]:
    """스킬 이름 → 대체/인접 스킬 이름 집합. 사전의 `related` 를 대칭으로 보정한다
    (A 가 B 를 가리키면 B → A 도 성립하게)."""
    pairs: dict[str, set[str]] = {}
    for entry in load_skill_entries():
        for other in entry.related:
            pairs.setdefault(entry.name, set()).add(other)
            pairs.setdefault(other, set()).add(entry.name)
    return {name: frozenset(v - {name}) for name, v in pairs.items()}


# Common Korean case/topic particles (조사) that attach directly to a noun
# with no space ("인프라를", "거버넌스는"). Used to relax the right-side word
# boundary for Korean terms so a trailing particle doesn't hide an otherwise
# exact match, while still rejecting compound words like "복지카드" (카드 isn't
# a particle) or "인프라스트럭처" (스트럭처 isn't a particle) as a match.
_KOREAN_PARTICLES = (
    "이나|이며|이랑|이라도|으로|에서|에게|한테|부터|까지|처럼|만큼|보다|밖에|마저|조차|뿐"
    "|은|는|이|가|을|를|의|에|와|과|도|만|로|나|며|랑"
)


@lru_cache(maxsize=512)
def term_pattern(term: str) -> re.Pattern:
    # Korean grammar attaches particles (조사) directly to words (e.g. "Python은",
    # "인프라를"), so only guard against splitting *within* a same-script
    # token: an English term's boundary only cares about adjacent latin/digit
    # chars, while a Korean term's boundary only cares about adjacent Korean
    # chars — except a trailing particle, which is grammar, not a new word.
    #
    # Shared with app.services.job_parser for position-keyword matching, since
    # both need the same script-aware boundary behavior.
    # IGNORECASE is the single case-folding strategy — callers pass raw text
    # (job_parser passes untouched posting text; extract_skills no longer
    # pre-lowercases). Terms are still stored lowercased only so alias sets
    # like {"JS", "js"} dedupe to one.
    escaped = re.escape(term)
    if _HAS_KOREAN.search(term):
        left = r"(?<![가-힣])"
        right = rf"(?=[^가-힣]|$|(?:{_KOREAN_PARTICLES})(?![가-힣]))"
    else:
        left = r"(?<![a-z0-9])"
        right = r"(?![a-z0-9])"
    return re.compile(rf"{left}{escaped}{right}", re.IGNORECASE)


def extract_skills(text: str) -> list[dict]:
    """Return unique skill hits found in text as [{"name": ..., "category": ...}, ...]."""
    if not text:
        return []
    hits: list[dict] = []
    seen = set()
    for entry in load_skill_entries():
        if entry.name in seen:
            continue
        for term in entry.terms:
            if term_pattern(term).search(text):
                hits.append({"name": entry.name, "category": entry.category})
                seen.add(entry.name)
                break
    return hits


def extract_skill_names(text: str) -> list[str]:
    return [hit["name"] for hit in extract_skills(text)]


@lru_cache(maxsize=1)
def skill_category_map() -> dict[str, str]:
    """Skill name -> dictionary category, for grouping already-known skill names."""
    return {entry.name: entry.category for entry in load_skill_entries()}
