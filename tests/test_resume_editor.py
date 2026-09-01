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


def test_validate_resume_content_requires_raw_text_only_for_file_source():
    assert validate_resume_content("file", raw_text="") == {"raw_text": "이력서 원문을 입력해주세요."}
    assert validate_resume_content("file", raw_text="  ") != {}
    assert validate_resume_content("file", raw_text="내용 있음") == {}
    assert validate_resume_content("form", raw_text="") == {}


def test_new_resume_form_source_builds_structured_and_skills():
    resume = new_resume(label="폼 이력서", source_type="form", career="Python 3년", skills_text="FastAPI")
    assert resume.label == "폼 이력서"
    assert resume.source_type == "form"
    assert resume.structured["skills_text"] == "FastAPI"
    assert "Python" in resume.extracted_skills
    assert "FastAPI" in resume.extracted_skills


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
