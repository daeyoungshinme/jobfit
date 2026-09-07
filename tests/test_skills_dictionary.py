"""app/data/skills_dictionary.json 정합성 — test_interview_guide_data.py 스타일."""

from app.services.skill_extractor import load_skill_entries, related_skill_map


def test_related_names_reference_real_skills():
    names = {e.name for e in load_skill_entries()}
    for entry in load_skill_entries():
        for other in entry.related:
            assert other in names, f"{entry.name}.related -> 알 수 없는 스킬 {other!r}"
        assert entry.name not in entry.related, f"{entry.name} 이 자기 자신을 related 로 가리킴"


def test_related_map_is_symmetric():
    rel = related_skill_map()
    for name, others in rel.items():
        for other in others:
            assert name in rel.get(other, set()), f"{name}↔{other} 비대칭"


def test_skill_names_are_unique():
    names = [e.name for e in load_skill_entries()]
    assert len(names) == len(set(names))
