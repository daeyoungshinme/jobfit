from app.models import Resume


def test_resume_detail_404_when_missing(client):
    response = client.get("/resumes/99999")
    assert response.status_code == 404


def test_upload_resume_without_file_returns_422(client):
    response = client.post("/resumes/upload", data={"label": "테스트 이력서"})
    assert response.status_code == 422


def test_upload_resume_with_file_succeeds(client):
    response = client.post(
        "/resumes/upload",
        data={"label": "테스트 이력서"},
        files={"file": ("resume.txt", "[경력]\nPython 백엔드 개발 3년".encode("utf-8"), "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/resumes/")


def test_submit_resume_form_missing_label_returns_422(client):
    response = client.post("/resumes/form", data={"label": "", "career": "3년차 백엔드 개발자"})
    assert response.status_code == 422


def test_submit_resume_form_success_redirects_to_detail(client, db_session):
    response = client.post(
        "/resumes/form",
        data={
            "label": "테스트 이력서",
            "career": "3년차 백엔드 개발자, Python 사용",
            "projects": "사내 API 서버 구축",
            "education": "OO대학교 졸업",
            "skills_text": "Python, Docker",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/resumes/")

    resume = db_session.query(Resume).one()
    assert resume.label == "테스트 이력서"
    assert "Python" in resume.extracted_skills


def test_list_resumes_returns_200(client, resume_factory):
    resume_factory(raw_text="Python 백엔드 개발")

    response = client.get("/resumes")
    assert response.status_code == 200
    assert "테스트 이력서" in response.text


def test_delete_resume_success_redirects_with_flash(client, db_session, resume_factory):
    resume = resume_factory(label="삭제될 이력서", raw_text="내용")

    response = client.post(f"/resumes/{resume.id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_deleted"
    assert db_session.get(Resume, resume.id) is None


def test_delete_resume_missing_redirects_with_not_found_flash(client):
    response = client.post("/resumes/99999/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"


def test_edit_resume_form_404_when_missing(client):
    response = client.get("/resumes/99999/edit")
    assert response.status_code == 404


def test_update_resume_404_when_missing(client):
    response = client.post("/resumes/99999/edit", data={"label": "이름"})
    assert response.status_code == 404


def test_update_resume_missing_label_returns_422(client, resume_factory):
    resume = resume_factory(label="원래 이름")

    response = client.post(f"/resumes/{resume.id}/edit", data={"label": ""})
    assert response.status_code == 422


def test_update_resume_form_source_success_persists_changes(client, db_session, resume_factory):
    resume = resume_factory(label="원래 이름")

    response = client.post(
        f"/resumes/{resume.id}/edit",
        data={
            "label": "수정된 이름",
            "career": "Python, Docker 3년차 백엔드 개발",
            "projects": "사내 API 서버 구축",
            "education": "OO대학교 졸업",
            "skills_text": "Python, Docker",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/resumes/{resume.id}?msg=resume_updated"

    db_session.refresh(resume)
    assert resume.label == "수정된 이름"
    assert resume.structured["career"] == "Python, Docker 3년차 백엔드 개발"
    assert "Docker" in resume.extracted_skills


def test_update_resume_file_source_edits_raw_text(client, db_session, resume_factory):
    resume = resume_factory(
        label="파일 이력서",
        source_type="file",
        raw_text="Python 백엔드 개발",
        structured={"original_filename": "resume.pdf"},
    )

    response = client.post(
        f"/resumes/{resume.id}/edit",
        data={"label": "파일 이력서", "raw_text": "Python, Docker 백엔드 개발"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.refresh(resume)
    assert resume.raw_text == "Python, Docker 백엔드 개발"
    assert "Docker" in resume.extracted_skills
    assert resume.structured == {"original_filename": "resume.pdf"}


def test_update_resume_file_source_missing_raw_text_returns_422(client, resume_factory):
    resume = resume_factory(
        label="파일 이력서",
        source_type="file",
        raw_text="Python 백엔드 개발",
        structured={"original_filename": "resume.pdf"},
    )

    response = client.post(
        f"/resumes/{resume.id}/edit",
        data={"label": "파일 이력서", "raw_text": ""},
    )
    assert response.status_code == 422
