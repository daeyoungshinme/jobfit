from app.models import Resume
from app.services.profile_exporter import build_platform_profiles


def _form_resume(**overrides):
    fields = {
        "label": "백엔드 지원용",
        "source_type": "form",
        "raw_text": (
            "[경력]\n결제 시스템을 개발하고 처리 시간을 30% 단축했습니다. 5년간 백엔드 개발자로 근무.\n\n"
            "[프로젝트]\n대용량 이벤트 파이프라인 구축\n\n[학력]\n한국대학교 졸업\n\n[기술 스택]\nPython, Kafka, AWS"
        ),
        "structured": {
            "career": "결제 시스템을 개발하고 처리 시간을 30% 단축했습니다. 5년간 백엔드 개발자로 근무.",
            "projects": "대용량 이벤트 파이프라인 구축",
            "education": "한국대학교 졸업",
            "skills_text": "Python, Kafka, AWS",
        },
        "extracted_skills": ["Python", "Kafka", "AWS"],
    }
    fields.update(overrides)
    return Resume(**fields)


def _sentence_count(text):
    return text.count(".") + text.count("다 ") + (1 if text and not text.endswith(".") else 0)


def test_form_resume_produces_three_platforms():
    bundle = build_platform_profiles(_form_resume())
    assert [p.key for p in bundle.profiles] == ["linkedin", "remember", "wanted_jobkorea"]
    assert bundle.warning == ""


def test_headline_has_role_years_and_top_skills():
    bundle = build_platform_profiles(_form_resume(), skill_demand=["Python", "Kafka", "AWS"])
    headline = bundle.profiles[0].sections[0].body
    assert "5년차" in headline
    assert "백엔드 개발자" in headline
    assert "Python" in headline


def test_skill_list_orders_by_demand():
    bundle = build_platform_profiles(_form_resume(), skill_demand=["Kafka", "Python"])
    skills_section = next(s for s in bundle.profiles[0].sections if s.label == "스킬")
    assert skills_section.body.startswith("Kafka, Python, AWS")


def test_linkedin_skill_list_caps_at_50():
    many = [f"스킬{i}" for i in range(60)]
    resume = _form_resume(extracted_skills=many)
    bundle = build_platform_profiles(resume)
    skills_section = next(s for s in bundle.profiles[0].sections if s.label == "스킬")
    assert len(skills_section.body.split(", ")) == 50


def test_summary_sentence_count_varies_by_platform():
    bundle = build_platform_profiles(_form_resume())
    linkedin_about = next(s for s in bundle.profiles[0].sections if s.label == "소개 (About)").body
    remember_summary = next(s for s in bundle.profiles[1].sections if s.label == "경력 요약").body
    assert _sentence_count(linkedin_about) > _sentence_count(remember_summary)


def test_file_resume_without_structured_still_renders():
    resume = Resume(
        label="이력서.pdf",
        source_type="file",
        raw_text="Python 백엔드 3년 경험. 결제 처리 시간을 30% 단축하고 시스템을 설계했습니다.",
        structured={"original_filename": "이력서.pdf"},
        extracted_skills=["Python"],
    )
    bundle = build_platform_profiles(resume)
    assert bundle.warning == ""
    bullets = next(s for s in bundle.profiles[0].sections if s.label == "경력 설명 (요점)").body
    assert "30%" in bullets


def test_low_signal_resume_sets_warning():
    resume = Resume(
        label="빈 이력서",
        source_type="file",
        raw_text="안녕하세요 잘 부탁드립니다",
        structured={"original_filename": "x.pdf"},
        extracted_skills=[],
    )
    bundle = build_platform_profiles(resume)
    assert bundle.warning != ""
    # 프로필 자체는 여전히 렌더된다 (문구를 직접 다듬을 수 있도록)
    assert len(bundle.profiles) == 3
