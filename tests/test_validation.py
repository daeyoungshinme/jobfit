from app.services.validation import require_fields


def test_missing_field_reports_configured_message():
    errors = require_fields({"title": ""}, {"title": "제목을 입력해주세요."})
    assert errors == {"title": "제목을 입력해주세요."}


def test_blank_after_strip_counts_as_missing():
    errors = require_fields({"title": "   "}, {"title": "제목을 입력해주세요."})
    assert errors == {"title": "제목을 입력해주세요."}


def test_absent_key_counts_as_missing():
    errors = require_fields({}, {"title": "제목을 입력해주세요."})
    assert errors == {"title": "제목을 입력해주세요."}


def test_non_blank_field_passes():
    errors = require_fields({"title": "백엔드 개발자"}, {"title": "제목을 입력해주세요."})
    assert errors == {}


def test_only_failing_fields_are_reported():
    errors = require_fields(
        {"title": "백엔드 개발자", "position": ""},
        {"title": "제목을 입력해주세요.", "position": "직무를 선택해주세요."},
    )
    assert errors == {"position": "직무를 선택해주세요."}
