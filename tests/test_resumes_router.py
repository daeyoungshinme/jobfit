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


def test_list_resumes_returns_200(client, db_session):
    resume = Resume(label="테스트 이력서", source_type="form", raw_text="Python 백엔드 개발")
    db_session.add(resume)
    db_session.commit()

    response = client.get("/resumes")
    assert response.status_code == 200
    assert "테스트 이력서" in response.text


def test_delete_resume_success_redirects_with_flash(client, db_session):
    resume = Resume(label="삭제될 이력서", source_type="form", raw_text="내용")
    db_session.add(resume)
    db_session.commit()
    db_session.refresh(resume)

    response = client.post(f"/resumes/{resume.id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_deleted"
    assert db_session.get(Resume, resume.id) is None


def test_delete_resume_missing_redirects_with_not_found_flash(client):
    response = client.post("/resumes/99999/delete", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/resumes?msg=resume_not_found"
