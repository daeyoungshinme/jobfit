from app.models import Resume
from app.services.resume_editor import compose_form_raw_text
from app.services.resume_sections import (
    detect_sections,
    first_line_label,
    sections_for_resume,
    split_blocks,
    split_resume_sections,
)


def test_split_synthesized_form_text():
    raw = compose_form_raw_text(
        career="A사 백엔드 3년",
        projects="결제 시스템 구축\n\n추천 엔진 개선",
        education="OO대학교 컴퓨터공학",
        skills_text="Python, Kafka",
    )
    sections = split_resume_sections(raw)
    assert sections["career"] == "A사 백엔드 3년"
    assert "결제 시스템 구축" in sections["projects"]
    assert "추천 엔진 개선" in sections["projects"]
    assert "OO대학교" in sections["education"]
    assert "Kafka" in sections["skills"]


def test_split_freeform_with_project_heading():
    raw = "이름: 홍길동\n\n프로젝트\n- 사내 검색 엔진 구축\n- 로그 파이프라인 운영\n\n학력\nOO대 졸업"
    sections = split_resume_sections(raw)
    assert "사내 검색 엔진 구축" in sections["projects"]
    assert "로그 파이프라인 운영" in sections["projects"]
    assert "OO대 졸업" in sections["education"]


def test_no_headings_returns_empty_sections():
    sections = split_resume_sections("경험 많은 개발자입니다. 열정적으로 일합니다.")
    assert sections == {"career": "", "projects": "", "education": "", "skills": ""}


def test_split_blocks_by_blank_lines_and_bullets():
    assert split_blocks("A 프로젝트\n\nB 프로젝트") == ["A 프로젝트", "B 프로젝트"]
    assert split_blocks("- 첫째 항목\n- 둘째 항목") == ["첫째 항목", "둘째 항목"]
    assert split_blocks("   ") == []


def test_first_line_label_strips_bullet_and_truncates():
    assert first_line_label("- 결제 게이트웨이 구축") == "결제 게이트웨이 구축"
    assert first_line_label("x" * 80).endswith("…")


def test_sections_for_resume_prefers_structured_for_form():
    resume = Resume(
        label="r",
        source_type="form",
        raw_text="[경력]\n무시됨\n\n[프로젝트]\n무시됨\n\n[학력]\n\n[기술 스택]\n",
        structured={"career": "구조화된 경력", "projects": "구조화된 프로젝트", "education": "", "skills_text": "Python"},
        extracted_skills=["Python"],
    )
    sections = sections_for_resume(resume)
    assert sections["career"] == "구조화된 경력"
    assert sections["projects"] == "구조화된 프로젝트"
    assert sections["skills"] == "Python"


def test_sections_for_resume_scans_raw_text_for_file():
    resume = Resume(
        label="r",
        source_type="file",
        raw_text="프로젝트\n결제 게이트웨이 구축\n\n학력\nOO대 졸업",
        structured={"original_filename": "resume.pdf"},
        extracted_skills=[],
    )
    sections = sections_for_resume(resume)
    assert "결제 게이트웨이 구축" in sections["projects"]


def test_detect_sections_form_trusts_structured():
    resume = Resume(
        label="r", source_type="form",
        raw_text="무시됨",
        structured={"career": "A사 3년", "projects": "", "education": "OO대", "skills_text": ""},
        extracted_skills=[],
    )
    assert detect_sections(resume) == {
        "career": True, "projects": False, "education": True, "skills": False,
    }


def test_detect_sections_file_requires_headings_not_prose():
    prose = Resume(
        label="r", source_type="file",
        raw_text="이 회사에서 3년간 근무하며 OO대학교를 졸업했습니다.",
        structured={"original_filename": "r.pdf"}, extracted_skills=[],
    )
    assert detect_sections(prose) == {
        "career": False, "projects": False, "education": False, "skills": False,
    }

    headed = Resume(
        label="r", source_type="file",
        raw_text="경력\nA사 백엔드 2020-2023\n\n학력\nOO대 졸업",
        structured={"original_filename": "r.pdf"}, extracted_skills=[],
    )
    detected = detect_sections(headed)
    assert detected["career"] and detected["education"]
    assert not detected["projects"]
