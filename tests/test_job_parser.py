from app.services.job_parser import (
    guess_posting_fields,
    guess_source_site,
    normalize_newlines,
    parse_job_posting,
)

SAMPLE = """
백엔드 개발자 채용

[자격요건]
- Python, FastAPI 기반 백엔드 개발 경험 3년 이상
- PostgreSQL 등 RDB 사용 경험
- Git을 이용한 협업 경험

[우대사항]
- Docker, Kubernetes 운영 경험
- AWS 클라우드 환경 경험
"""


def test_splits_required_and_preferred_sections():
    parsed = parse_job_posting(SAMPLE)
    assert "Python" in parsed.required_skills
    assert "FastAPI" in parsed.required_skills
    assert "PostgreSQL" in parsed.required_skills
    assert "Docker" in parsed.preferred_skills
    assert "AWS" in parsed.preferred_skills


def test_skill_not_duplicated_across_sections():
    parsed = parse_job_posting(SAMPLE)
    overlap = set(parsed.required_skills) & set(parsed.preferred_skills)
    assert overlap == set()


def test_fallback_when_no_headers_present():
    parsed = parse_job_posting("Python과 Docker를 다룰 수 있는 분을 찾습니다.")
    assert "Python" in parsed.required_skills
    assert "Docker" in parsed.required_skills
    assert parsed.preferred_skills == []


def test_guess_posting_fields_from_sample():
    guessed = guess_posting_fields(SAMPLE)
    assert guessed.title == "백엔드 개발자 채용"
    assert guessed.position == "백엔드 개발자"
    assert guessed.experience_level == "3년 이상"


def test_guess_company_from_bracket_prefix():
    guessed = guess_posting_fields("[잡핏테크] 프론트엔드 개발자 모집\n\n[자격요건]\n- React 3년 이상")
    assert guessed.title == "프론트엔드 개발자 모집"
    assert guessed.company == "잡핏테크"
    assert guessed.position == "프론트엔드 개발자"


def test_guess_position_data_engineer_english_title():
    guessed = guess_posting_fields("Data Engineer\n\n[자격요건]\n- Python, Airflow 경험 3년 이상")
    assert guessed.position == "데이터 엔지니어"


def test_guess_position_data_engineer_over_backend_mention():
    guessed = guess_posting_fields(
        "Data Engineer 채용\n\n[자격요건]\n- backend 팀과 협업하여 데이터 파이프라인 구축"
    )
    assert guessed.position == "데이터 엔지니어"


def test_guess_company_from_corporate_suffix():
    guessed = guess_posting_fields("데이터 엔지니어 채용\n(주)잡핏에서 함께할 동료를 찾습니다.")
    assert guessed.company == "(주)잡핏에서"


def test_guess_experience_level_entry_and_open():
    assert guess_posting_fields("신입 개발자를 채용합니다.").experience_level == "신입"
    assert guess_posting_fields("경력 무관, 누구나 지원 가능합니다.").experience_level == "무관"


def test_guess_source_site_known_domain():
    assert guess_source_site("https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1") == "사람인"
    assert guess_source_site("https://www.jobkorea.co.kr/Recruit/GI_Read/12345") == "잡코리아"
    assert guess_source_site("https://www.wanted.co.kr/wd/12345") == "원티드"


def test_guess_source_site_unknown_domain_falls_back_to_host():
    assert guess_source_site("https://careers.example.com/jobs/1") == "careers.example.com"


def test_guess_source_site_empty_url():
    assert guess_source_site("") == ""


def test_guess_source_site_without_scheme():
    # Pasted URLs often omit "https://" entirely, which used to leave the
    # whole string in urlparse().path (netloc empty) instead of being read
    # as a host.
    assert guess_source_site("www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=1") == "사람인"
    assert guess_source_site("wanted.co.kr/wd/12345") == "원티드"


def test_guess_experience_level_ignores_year_range_dates():
    # A 4-digit year range ("2020-2023년") shouldn't be misread as a
    # 1-2 digit experience-year range.
    guessed = guess_posting_fields("2020-2023년 사이 급성장한 스타트업입니다.\n\n[자격요건]\n- Python 경험")
    assert guessed.experience_level == ""


def test_guess_company_strips_trailing_punctuation():
    guessed = guess_posting_fields("데이터 엔지니어 채용\n(주)잡핏, 함께할 동료를 찾습니다.")
    assert guessed.company == "(주)잡핏"


def test_guess_returns_empty_when_no_match():
    guessed = guess_posting_fields("")
    assert guessed.title == ""
    assert guessed.company == ""
    assert guessed.position == ""
    assert guessed.experience_level == ""
    assert guessed.address == ""


SAMPLE_WITH_ALL_SECTIONS = """
[잡핏테크] 백엔드 개발자 채용

[주요업무]
- 백엔드 서비스 설계 및 개발
- API 서버 운영

[기술스택]
- Python, FastAPI, Docker

[자격요건]
- Python 3년 이상
- PostgreSQL 사용 경험

[우대사항]
- AWS 클라우드 경험

[복지 및 혜택]
- 자유로운 연차 사용
- 건강검진 지원

주소: 서울특별시 강남구 테헤란로 123
"""


def test_extracts_main_tasks_section():
    parsed = parse_job_posting(SAMPLE_WITH_ALL_SECTIONS)
    assert "백엔드 서비스 설계 및 개발" in parsed.main_tasks_text
    assert "백엔드 서비스 설계 및 개발" not in parsed.required_text


def test_tech_stack_section_folds_into_required_skills():
    parsed = parse_job_posting(SAMPLE_WITH_ALL_SECTIONS)
    assert "Docker" in parsed.required_skills
    assert "Docker" not in parsed.preferred_skills


def test_extracts_benefits_section():
    parsed = parse_job_posting(SAMPLE_WITH_ALL_SECTIONS)
    assert "건강검진" in parsed.benefits_text


def test_guess_address_from_label():
    guessed = guess_posting_fields(SAMPLE_WITH_ALL_SECTIONS)
    assert guessed.address == "서울특별시 강남구 테헤란로 123"


def test_guess_address_from_pattern_without_label():
    guessed = guess_posting_fields("서울특별시 강남구 테헤란로 123에 위치한 사무실로 출근합니다.")
    assert guessed.address == "서울특별시 강남구 테헤란로 123"


# Regression cases from a real Wanted-style posting where headers appear
# bare (no brackets) on their own line, mixed with prose that happens to
# contain header keywords as substrings or trailing words.
REAL_WORLD_STYLE_SAMPLE = """
아정네트웍스∙서울 강남구∙경력 5년 이상

[아정당] 데이터 엔지니어 (서울)

매출 1,000억 돌파! 매년 성장하는 복지 끝판왕 기업
주요업무
• 데이터 파이프라인 설계 및 운영 지원
자격요건
• Kafka 기반 Streaming 시스템 이해
[기술 스택]
• AWS, Docker, Kubernetes
우대사항
• Spark 활용 경험
혜택 및 복지
• 복지카드로 점심 식대를 지원!
• 건강검진 지원
채용 전형
• 회사 위치 : 서울특별시 강남구 테헤란로 124
• 서류전형 - 인터뷰 - 최종합격
"""


def test_header_word_inside_prose_is_not_mistaken_for_a_header():
    # "복지" appears mid-sentence ("복지 끝판왕 기업") before the real
    # "주요업무" header — it must not be treated as a benefits header, and
    # must not swallow the following 주요업무 section into "required".
    parsed = parse_job_posting(REAL_WORLD_STYLE_SAMPLE)
    assert "데이터 파이프라인 설계 및 운영 지원" in parsed.main_tasks_text


def test_header_does_not_bridge_across_a_line_break():
    # "...운영 지원" ends one line and "자격요건" starts the next — the old
    # "지원\s*자격" pattern could match across that newline and corrupt both
    # sections. Both must come through intact and undamaged.
    parsed = parse_job_posting(REAL_WORLD_STYLE_SAMPLE)
    assert parsed.main_tasks_text.endswith("데이터 파이프라인 설계 및 운영 지원")
    assert parsed.required_text.startswith("• Kafka 기반 Streaming 시스템 이해")


def test_header_word_inside_another_word_is_not_split():
    # "복지카드" contains "복지" as a substring but is one word, not a header.
    parsed = parse_job_posting(REAL_WORLD_STYLE_SAMPLE)
    assert "복지카드로 점심 식대를 지원!" in parsed.benefits_text


def test_stop_header_ends_tracked_sections():
    # "채용 전형" (and what follows: address, application steps) is not one
    # of the tracked sections and must not leak into benefits_text.
    parsed = parse_job_posting(REAL_WORLD_STYLE_SAMPLE)
    assert "서류전형" not in parsed.benefits_text
    assert "테헤란로" not in parsed.benefits_text


def test_guess_title_skips_leading_metadata_line():
    # Wanted-style postings often lead with a "회사명∙지역∙경력" summary line
    # before the actual "[회사명] 직무명" line further down.
    guessed = guess_posting_fields(REAL_WORLD_STYLE_SAMPLE)
    assert guessed.title == "데이터 엔지니어 (서울)"
    assert guessed.company == "아정당"


NO_BRACKET_METADATA_SAMPLE = """
콘센트릭스서비스코리아∙서울 강남구∙경력 2-8년

데이터 엔지니어

포지션 상세
콘센트릭스는 글로벌 컨설팅 기업입니다.
"""


def test_guess_company_from_metadata_line_without_bracket():
    # Some Wanted postings never have a "[회사명] 직무명" bracket line at
    # all — the company must be pulled from the leading metadata line itself,
    # and the title must skip past that metadata line rather than using it.
    guessed = guess_posting_fields(NO_BRACKET_METADATA_SAMPLE)
    assert guessed.company == "콘센트릭스서비스코리아"
    assert guessed.title == "데이터 엔지니어"


def test_guess_experience_level_range_preserves_bounds():
    # The exact "lo~hi" range from the raw text is kept as-is rather than
    # collapsed into a coarse bucket, so users see the precise figure the
    # posting stated.
    assert guess_posting_fields("경력 2-8년").experience_level == "2~8년"
    assert guess_posting_fields("경력 1-2년").experience_level == "1~2년"
    assert guess_posting_fields("경력 8-12년").experience_level == "8~12년"


def test_numbered_header_is_recognized():
    # "2. 우대사항" — a common numbered-list style header. Digits/periods
    # aren't decoration characters, so this used to fail fullmatch and get
    # absorbed into the preceding (required) section instead.
    sample = """
자격요건
1. Python 3년 이상
2. 우대사항
- Docker, AWS 경험
"""
    parsed = parse_job_posting(sample)
    assert "Docker" in parsed.preferred_skills
    assert "AWS" in parsed.preferred_skills


def test_inline_header_with_colon_is_recognized():
    sample = """
자격요건
- Python 3년 이상
우대사항 : Docker, AWS 경험
"""
    parsed = parse_job_posting(sample)
    assert "Docker, AWS 경험" in parsed.preferred_text
    assert "Docker" in parsed.preferred_skills
    assert "AWS" in parsed.preferred_skills


def test_inline_header_with_dash_is_recognized():
    sample = """
자격요건
- Python 3년 이상
우대사항 - Docker, AWS 경험
"""
    parsed = parse_job_posting(sample)
    assert "Docker" in parsed.preferred_skills
    assert "AWS" in parsed.preferred_skills


def test_english_preferred_header_is_recognized():
    sample = """
Requirements
- 3+ years of Python experience

Preferred Qualifications
- Docker, AWS experience
"""
    parsed = parse_job_posting(sample)
    assert "Docker" in parsed.preferred_skills
    assert "AWS" in parsed.preferred_skills


def test_header_keyword_followed_by_particle_is_not_a_header():
    # "우대사항이 있으신 분은..." — no separator right after the header
    # keyword, so this is prose, not a header, and must not swallow the
    # section boundary.
    sample = """
자격요건
- Python 3년 이상
우대사항이 있으신 분은 자기소개서에 기재해 주세요.
"""
    parsed = parse_job_posting(sample)
    assert parsed.preferred_text == ""
    assert "우대사항이 있으신 분은 자기소개서에 기재해 주세요." in parsed.required_text


DATA_ENGINEERING_STYLE_SAMPLE = """
주요업무
• BigQuery 기반 엔터프라이즈 데이터 웨어하우스(DW) 및 데이터 파이프라인 운영
• 온라인 커머스 도메인 데이터(주문/배송/상품) 및 외부 연동 데이터의 통합 관리/운영
자격요건
• 클라우드 환경(GCP, AWS, Azure 등) 기반 SQL 및 데이터 처리 실무 경험
• 대규모 데이터 처리 및 ETL/ELT 파이프라인 구축 경험
• Python 및 Airflow를 활용한 데이터 파이프라인(DAG) 개발 및 운영 경험
우대사항
• 데이터 모델링 경험이 있으며, 데이터 마트(DM) 생성 및 대시보드 구성 경험이 있으신 분
• Python 기반 크롤링/스크래핑 개발 경험(Selenium, Playwright, BeautifulSoup, Requests 등)
• RAG(검색 증강 생성) 파이프라인 구축 경험이 있으신 분 (문서 파싱, Chunking, Vector DB 구축 등)
• LLM 및 지식 그래프(Knowledge Graph) 관련 인프라 경험이 있으신 분 (Vertex AI Vector Search, Graph DB 등)
• Databricks 플랫폼 기반 개발 및 운영 경험이 있으신 분
혜택 및 복지
아래와 같은 혜택을 구성원들과 함께 나눈답니다 !
"""


def test_extracts_preferred_skills_from_data_engineering_posting():
    # Regression for a real posting where section splitting worked but the
    # skills dictionary was missing every data-engineering/LLM term it used,
    # leaving preferred_skills empty.
    parsed = parse_job_posting(DATA_ENGINEERING_STYLE_SAMPLE)
    assert "ETL" in parsed.required_skills
    assert "Airflow" in parsed.required_skills
    for skill in ("Selenium", "Playwright", "BeautifulSoup", "Requests", "RAG", "LLM", "Databricks"):
        assert skill in parsed.preferred_skills


PREFERRED_SECTION_WITH_TIP_BLOCK_SAMPLE = """
우대사항
• AWS 등 클라우드 환경에서 개발 및 운영 경험이 있으신 분
• Apache Spark(Batch/Structured Streaming) 활용한 대용량 데이터 처리 경험이 있으신 분
• Docker/Kubernetes와 같은 컨테이너 환경 경험이 있으신 분
• 데이터 거버넌스를 구축하고 운영해보신 분
• 새로운 기술을 도입하고 팀 역량을 강화해본 경험이 있으신 분
• 네트워크 및 인프라에 대한 기본적인 이해가 있으신 분

[지원서 작성 Tip - 반드시 작성해주세요!]
• 데이터 파이프라인 설계 및 운영 경험이 있다면 구체적으로 작성해주세요.
• 단순히 사용한 도구 나열이 아닌, 어떤 데이터 문제를 해결하기 위해 어떤 아키텍처를 설계했고,
데이터 품질·지연(latency)·확장성 측면에서 어떤 개선을 이뤘는지 중심으로 설명해주세요.
• 데이터 처리 환경에서 발생한 장애 또는 복잡한 문제를 해결한 경험이 있다면 작성해주세요.
• 장애의 원인 분석 과정(로그, 메트릭, 트레이싱 등)과 대응 전략, 재발 방지를 위한 아키텍처 개선
또는 운영 프로세스 변경까지 포함하여 설명해주세요.
"""


def test_extracts_all_preferred_skills_including_previously_missing_terms():
    parsed = parse_job_posting(PREFERRED_SECTION_WITH_TIP_BLOCK_SAMPLE)
    for skill in ("AWS", "Spark", "Docker", "Kubernetes", "데이터 거버넌스", "네트워크", "인프라"):
        assert skill in parsed.preferred_skills


def test_bracket_tip_block_does_not_bleed_into_preferred_section():
    # "[지원서 작성 Tip - ...]" isn't a recognized section header, so without
    # treating bracket-wrapped lines as an implicit stop marker, the whole
    # Tip block used to get silently absorbed into the preceding 우대사항
    # section body.
    parsed = parse_job_posting(PREFERRED_SECTION_WITH_TIP_BLOCK_SAMPLE)
    assert "지원서 작성 Tip" not in parsed.preferred_text
    assert "장애의 원인 분석 과정" not in parsed.preferred_text
    assert "네트워크 및 인프라에 대한 기본적인 이해가 있으신 분" in parsed.preferred_text


BENEFITS_SECTION_WITH_CATEGORY_SUBHEADINGS_SAMPLE = """
혜택 및 복지
[아낌없는 보상과 복지 혜택 제공]
• 점심식사를 제공합니다. 든든하게 일하세요!
• 분기별로 복지몰 포인트를 지급드립니다. (연간 80만원 상당)
• 스톡옵션 지급을 통해 회사의 성장과 함께합니다.
• 장기 근속자분들을 위한 포상을 지급합니다.
• 업무에 필요한 도서를 무제한 지원하고 있습니다.
• 지인추천 포상금제도로 좋은 분은 언제든지 추천해주세요.
• 야근 시 저녁 식대와 택시비를 지원합니다.
• 경조금과 경조휴가를 지원합니다.

[업무에 몰입할 수 있는 환경]
• 근무시간 10:00~ 19:00
• 금요일은 가족과 함께! 1시간 빨리 퇴근합니다.
• 자유로운 연차 사용 가능합니다.
• 최신형 윈도우/맥북 장비를 제공합니다.
• 언제든 편안한 휴식이 가능한 안마의자가 있습니다.
• 커피머신 이용과 함께 스낵, 음료가 무제한으로 제공됩니다.

[함께 일하는 환경]
• 팀원과 함께 할 수 있는 회식비를 지원합니다.
• 사내 동아리 활동비를 지원합니다.
채용 전형
• 서류전형 - 1차면접(실무진) - 2차면접(임원진) - 입사
"""


def test_benefits_section_with_bracket_category_subheadings_is_not_dropped():
    # Regression: "[아낌없는 보상과 복지 혜택 제공]" etc. are category
    # sub-headings *within* the 혜택 및 복지 section (text_formatter renders
    # them as <h4>), not boilerplate notes. They used to be misread as an
    # implicit stop marker, closing the section immediately and silently
    # dropping every bullet that followed.
    parsed = parse_job_posting(BENEFITS_SECTION_WITH_CATEGORY_SUBHEADINGS_SAMPLE)
    assert "점심식사를 제공합니다" in parsed.benefits_text
    assert "스톡옵션 지급을 통해" in parsed.benefits_text
    assert "안마의자가 있습니다" in parsed.benefits_text
    assert "사내 동아리 활동비를 지원합니다" in parsed.benefits_text
    # The sub-heading text itself should survive too, since text_formatter
    # renders it as a heading rather than dropping it.
    assert "아낌없는 보상과 복지 혜택 제공" in parsed.benefits_text
    assert "업무에 몰입할 수 있는 환경" in parsed.benefits_text
    # The real 채용 전형 stop header still ends the section as before.
    assert "서류전형" not in parsed.benefits_text


def test_normalize_newlines_collapses_crlf_and_cr():
    assert normalize_newlines("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_split_sections_survives_crlf_line_endings():
    # Native <textarea> form submissions can round-trip "\n" into "\r\n" on
    # save (e.g. every time a job posting is re-submitted from the edit
    # form), which used to make every section header line fail to match and
    # collapse the whole posting into a single undifferentiated block.
    crlf_sample = REAL_WORLD_STYLE_SAMPLE.replace("\n", "\r\n")
    parsed = parse_job_posting(crlf_sample)
    assert "데이터 파이프라인 설계 및 운영 지원" in parsed.main_tasks_text
    assert parsed.required_text.startswith("• Kafka 기반 Streaming 시스템 이해")
    assert "Spark 활용 경험" in parsed.preferred_text
    assert "복지카드로 점심 식대를 지원!" in parsed.benefits_text
