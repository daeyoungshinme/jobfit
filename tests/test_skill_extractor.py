from app.services.skill_extractor import extract_skill_names, extract_skills


def test_extracts_known_skill_by_name():
    assert "Python" in extract_skill_names("Python 개발 경험 3년 이상")


def test_extracts_known_skill_by_alias():
    assert "Python" in extract_skill_names("파이썬 능숙자 우대")


def test_avoids_partial_word_match():
    # "Java" should not match inside "JavaScript"
    names = extract_skill_names("JavaScript 개발자를 채용합니다")
    assert "JavaScript" in names
    assert "Java" not in names


def test_no_false_positive_on_unrelated_text():
    assert extract_skills("커피와 산책을 좋아합니다") == []


def test_deduplicates_repeated_mentions():
    names = extract_skill_names("Python Python 파이썬 개발자, Python 경험 필수")
    assert names.count("Python") == 1


def test_extracts_data_and_ai_platform_skills():
    names = extract_skill_names(
        "RAG(검색 증강 생성) 파이프라인 구축 경험, LLM 및 지식 그래프(Knowledge Graph) 관련 "
        "인프라 경험, Vertex AI Vector Search, Databricks 플랫폼 기반 개발 및 운영 경험"
    )
    assert "RAG" in names
    assert "LLM" in names
    assert "Knowledge Graph" in names
    assert "Vertex AI" in names
    assert "Databricks" in names


def test_extracts_korean_term_with_particle_attached_directly():
    # "인프라에" — no space between the term and the trailing 조사 (particle),
    # which is normal Korean grammar, not a different word.
    names = extract_skill_names("네트워크 및 인프라에 대한 기본적인 이해가 있으신 분")
    assert "네트워크" in names
    assert "인프라" in names


def test_korean_term_inside_compound_word_is_not_matched():
    # "인프라팀" contains "인프라" but "팀" isn't a particle, so this must not
    # be mistaken for the "인프라" skill term.
    assert extract_skill_names("인프라팀 소속으로 근무합니다") == []


def test_extracts_lakehouse_and_observability_skills():
    names = extract_skill_names(
        "• AWS 기반 데이터 파이프라인 개발 및 운영 경험이 있으신 분\n"
        "• Kubernetes 기반 서비스 배포 및 운영 경험이 있으신 분\n"
        "• Apache Iceberg, Hudi, Delta Lake 등의 Lakehouse 기반 오픈 테이블 포맷 실무 경험이 있으신 분\n"
        "• Grafana, DataDog, Prometheus 등의 옵저빌리티 시스템 설계 및 운영 경험이 있으신 분\n"
        "• Kafka, Flink, Spark Streaming 기반의 스트리밍 데이터 처리 경험이 있으신 분\n"
        "• DataHub, OpenMetadata 등 데이터 카탈로그 구축 및 운영 경험이 있으신 분"
    )
    assert "AWS" in names
    assert "Kubernetes" in names
    assert "Apache Iceberg" in names
    assert "Apache Hudi" in names
    assert "Delta Lake" in names
    assert "Lakehouse" in names
    assert "Grafana" in names
    assert "Datadog" in names
    assert "Prometheus" in names
    assert "Observability" in names
    assert "Kafka" in names
    assert "Flink" in names
    assert "Spark" in names
    assert "DataHub" in names
    assert "OpenMetadata" in names
    assert "데이터 카탈로그" in names


def test_extracts_crawling_libraries():
    names = extract_skill_names(
        "Python 기반 크롤링/스크래핑 개발 경험(Selenium, Playwright, BeautifulSoup, Requests 등)"
    )
    assert "Selenium" in names
    assert "Playwright" in names
    assert "BeautifulSoup" in names
    assert "Requests" in names
