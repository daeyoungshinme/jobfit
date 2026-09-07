from app.models import Resume
from app.services.resume_editor import (
    apply_resume_content,
    compose_form_raw_text,
    new_resume,
    validate_resume_content,
)


def test_compose_form_raw_text_layout():
    text = compose_form_raw_text("경력내용", "프로젝트내용", "학력내용", "Python, FastAPI")
    assert "[경력]\n경력내용" in text
    assert "[프로젝트]\n프로젝트내용" in text
    assert "[학력]\n학력내용" in text
    assert "[기술 스택]\nPython, FastAPI" in text


def test_apply_resume_content_form_source_recomposes_and_extracts():
    resume = Resume(label="r", source_type="form", raw_text="old", structured={})
    apply_resume_content(resume, career="Django, Python 백엔드", skills_text="Kafka")
    assert resume.structured["career"] == "Django, Python 백엔드"
    assert resume.structured["skills_text"] == "Kafka"
    assert "Python" in resume.extracted_skills
    assert "Kafka" in resume.extracted_skills


def test_apply_resume_content_file_source_only_touches_raw_text():
    resume = Resume(
        label="r",
        source_type="file",
        raw_text="old Python",
        structured={"original_filename": "cv.pdf"},
        extracted_skills=["Python"],
    )
    apply_resume_content(resume, raw_text="new Docker text", career="ignored")
    assert resume.raw_text == "new Docker text"
    assert resume.structured == {"original_filename": "cv.pdf"}
    assert "Docker" in resume.extracted_skills
    assert "Python" not in resume.extracted_skills


def test_validate_resume_content_requires_raw_text_for_file_source():
    assert validate_resume_content("file", raw_text="") == {"raw_text": "이력서 원문을 입력해주세요."}
    assert validate_resume_content("file", raw_text="  ") != {}
    assert validate_resume_content("file", raw_text="내용 있음") == {}


def test_validate_resume_content_requires_one_field_for_form_source():
    assert validate_resume_content("form") != {}
    assert validate_resume_content("form", career="", projects="   ", education="", skills_text="") != {}
    assert validate_resume_content("form", skills_text="Python") == {}
    assert validate_resume_content("form", career="3년차 백엔드") == {}


def test_new_resume_form_source_builds_structured_and_skills():
    resume = new_resume(label="폼 이력서", source_type="form", career="Python 3년", skills_text="FastAPI")
    assert resume.label == "폼 이력서"
    assert resume.source_type == "form"
    assert resume.structured["skills_text"] == "FastAPI"
    assert "Python" in resume.extracted_skills
    assert "FastAPI" in resume.extracted_skills


def test_apply_resume_content_sets_career_meta_on_both_sources():
    form = Resume(label="r", source_type="form", raw_text="old", structured={})
    apply_resume_content(form, career="Python 3년", total_years="5", target_position="backend")
    assert form.total_years == 5
    assert form.target_position == "backend"

    filed = Resume(label="r", source_type="file", raw_text="x", structured={}, total_years=0)
    apply_resume_content(filed, raw_text="Kotlin", total_years="8")
    assert filed.total_years == 8


def test_apply_resume_content_blank_total_years_keeps_stored_value():
    resume = Resume(label="r", source_type="form", raw_text="old", structured={}, total_years=7)
    apply_resume_content(resume, career="Python", total_years="")
    assert resume.total_years == 7  # 빈칸은 '변경 없음'


def test_apply_resume_content_clamps_out_of_range_years():
    resume = Resume(label="r", source_type="form", raw_text="old", structured={}, total_years=3)
    apply_resume_content(resume, career="Python", total_years="999")
    assert resume.total_years == 60
    apply_resume_content(resume, career="Python", total_years="abc")
    assert resume.total_years == 60  # 파싱 실패도 '변경 없음'


def test_new_resume_file_source_keeps_supplied_structured():
    resume = new_resume(
        label="파일 이력서",
        source_type="file",
        raw_text="Kotlin Android 개발",
        structured={"original_filename": "resume.docx"},
    )
    assert resume.raw_text == "Kotlin Android 개발"
    assert resume.structured == {"original_filename": "resume.docx"}
    assert "Kotlin" in resume.extracted_skills
