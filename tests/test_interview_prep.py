from app.models import JobPosting, Resume
from app.services.interview_prep import _CATEGORY_ORDER, build_interview_prep


def make_job(*, required=None, preferred=None, position="backend", main_tasks="", experience_level="y3_5"):
    job = JobPosting(
        title="테스트 공고",
        company="테스트회사",
        position=position,
        raw_text="",
        main_tasks=main_tasks,
        experience_level=experience_level,
        required_skills=required or [],
        preferred_skills=preferred or [],
    )
    job.id = 1
    return job


def make_resume(*, skills=None, projects="", career="Python 백엔드 3년", source_type="form", raw_text=None):
    structured = {"career": career, "projects": projects, "education": "", "skills_text": ", ".join(skills or [])}
    return Resume(
        label="테스트 이력서",
        source_type=source_type,
        raw_text=raw_text if raw_text is not None else f"[경력]\n{career}\n\n[프로젝트]\n{projects}\n\n[학력]\n\n[기술 스택]\n",
        structured=structured if source_type == "form" else {"original_filename": "r.pdf"},
        extracted_skills=skills or [],
    )


def _group(prep, category):
    return next((g for g in prep.groups if g.category == category), None)


def test_matched_skill_produces_tech_deep_question():
    job = make_job(required=["Kafka"])
    prep = build_interview_prep(make_resume(skills=["Kafka"]), job)
    tech = _group(prep, "기술 심화")
    assert tech is not None
    assert any("Kafka" in q.question for q in tech.questions)


def test_missing_required_produces_gap_question_and_study_topic():
    job = make_job(required=["Kafka"])
    prep = build_interview_prep(make_resume(skills=[]), job)

    gap = _group(prep, "갭 대응")
    assert gap is not None
    assert any("Kafka" in q.question for q in gap.questions)

    assert any(t.priority == "높음" and "Kafka" in t.title for t in prep.study_topics)


def test_main_tasks_bullets_become_role_fit_questions():
    job = make_job(required=["Python"], main_tasks="- 결제 시스템 개발\n- 정산 배치 운영")
    prep = build_interview_prep(make_resume(skills=["Python"]), job)
    role_fit = _group(prep, "직무 적합성")
    assert role_fit is not None
    assert any("결제 시스템 개발" in q.question for q in role_fit.questions)


def test_position_study_topics_from_guide():
    job = make_job(required=["Python"], position="backend")
    prep = build_interview_prep(make_resume(skills=["Python"]), job)
    assert any(t.source.startswith("직무 공통") for t in prep.study_topics)


def test_position_gita_and_skill_less_job_do_not_crash():
    job = make_job(required=[], preferred=[], position="other", main_tasks="")
    prep = build_interview_prep(make_resume(skills=[]), job)
    assert prep.groups  # 최소 한 그룹(인성·행동)은 존재
    assert prep.match is not None and prep.match.has_skill_data is False


def test_file_resume_project_section_is_scanned():
    resume = make_resume(
        source_type="file",
        raw_text="프로젝트\n결제 게이트웨이 구축 및 운영\n\n학력\nOO대 졸업",
        skills=["Python"],
    )
    prep = build_interview_prep(resume, make_job(required=["Python"]))
    projects = _group(prep, "프로젝트 심화")
    assert projects is not None
    assert any("결제 게이트웨이" in q.question for q in projects.questions)


def test_form_resume_uses_structured_projects():
    resume = make_resume(skills=["Python"], projects="추천 시스템 고도화")
    prep = build_interview_prep(resume, make_job(required=["Python"]))
    projects = _group(prep, "프로젝트 심화")
    assert projects is not None
    assert any("추천 시스템 고도화" in q.question for q in projects.questions)


def test_short_resume_yields_resume_signal_questions():
    resume = make_resume(skills=["Python"], career="개발 함", projects="")
    prep = build_interview_prep(resume, make_job(required=["Python"]))
    assert _group(prep, "이력서 보완") is not None


def test_resume_only_mode_skips_job_specific_groups():
    prep = build_interview_prep(make_resume(skills=["Python", "Kafka"], projects="결제 시스템"), None)
    assert prep.job_linked is False
    assert prep.match is None
    categories = {g.category for g in prep.groups}
    assert "갭 대응" not in categories
    assert "직무 적합성" not in categories
    assert "인성·행동" in categories
    assert "기술 심화" in categories
    assert prep.study_topics
    assert all(t.priority == "기본" for t in prep.study_topics)


def test_question_count_and_group_order_and_topic_sorting():
    job = make_job(required=["Python", "AWS"], preferred=["Redis"], main_tasks="- 결제 시스템 개발")
    prep = build_interview_prep(make_resume(skills=["Python"], projects="A\n\nB"), job)

    assert prep.question_count == sum(len(g.questions) for g in prep.groups)

    order = [c for c, _ in _CATEGORY_ORDER]
    seen = [g.category for g in prep.groups]
    assert seen == [c for c in order if c in seen]

    ranks = [{"높음": 0, "중간": 1, "기본": 2}[t.priority] for t in prep.study_topics]
    assert ranks == sorted(ranks)


def test_questions_are_deduped_within_group():
    job = make_job(required=["Python"], main_tasks="- 결제 시스템 개발\n- 결제 시스템 개발")
    prep = build_interview_prep(make_resume(skills=["Python"]), job)
    role_fit = _group(prep, "직무 적합성")
    texts = [q.question for q in role_fit.questions]
    assert len(texts) == len(set(texts))
