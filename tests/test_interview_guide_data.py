from app.enums import POSITION
from app.services.interview_prep import load_interview_guide
from app.services.skill_extractor import load_skill_entries


def test_guide_parses_and_has_required_top_level_keys():
    guide = load_interview_guide()
    for key in ("positions", "categories", "skills", "behavioral", "gap", "resume_signal_questions"):
        assert key in guide
    assert guide["behavioral"].get("공통")
    assert "{skill}" in guide["gap"]["question_template"]


def test_category_keys_are_a_subset_of_skill_dictionary_categories():
    dict_categories = {entry.category for entry in load_skill_entries()}
    assert set(load_interview_guide()["categories"]).issubset(dict_categories)


def test_position_keys_are_known_positions():
    # interview_guide.json 은 사람이 읽는 한국어 라벨로 키를 두고, interview_prep 가
    # POSITION.label_of(job.position) 로 조회한다.
    assert set(load_interview_guide()["positions"]).issubset(set(POSITION.labels()))


def test_resume_signal_keys_match_reviewer_warning_titles():
    # interview_prep._SIGNAL_KEYWORDS 와 어긋나면 신호 매핑이 조용히 죽는다.
    from app.services.interview_prep import _SIGNAL_KEYWORDS

    assert set(load_interview_guide()["resume_signal_questions"]) == set(_SIGNAL_KEYWORDS)
