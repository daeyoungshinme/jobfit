import pytest

from app.enums import (
    APPLY_CHANNEL,
    EXPERIENCE_LEVEL,
    JOB_STATUS,
    JOB_STATUS_DEFAULT,
    POSITION,
    REGION,
    enum_label,
)

ALL_SETS = [JOB_STATUS, EXPERIENCE_LEVEL, POSITION, REGION, APPLY_CHANNEL]


@pytest.mark.parametrize("enum_set", ALL_SETS)
def test_codes_and_labels_are_unique(enum_set):
    codes = enum_set.codes()
    labels = enum_set.labels()
    assert len(codes) == len(set(codes))
    assert len(labels) == len(set(labels))


@pytest.mark.parametrize("enum_set", ALL_SETS)
def test_choices_pairs_match_codes_and_labels(enum_set):
    assert enum_set.choices() == list(zip(enum_set.codes(), enum_set.labels()))


def test_normalize_accepts_code_label_and_rejects_unknown():
    assert JOB_STATUS.normalize("interview") == "interview"
    assert JOB_STATUS.normalize("면접") == "interview"          # (구)라벨
    assert JOB_STATUS.normalize("  지원완료 ") == "applied"      # 공백 허용
    assert JOB_STATUS.normalize("없는값") is None
    assert JOB_STATUS.normalize("") is None
    assert JOB_STATUS.normalize(None) is None


def test_label_of_falls_back_to_raw_code():
    assert JOB_STATUS.label_of("interview") == "면접"
    assert JOB_STATUS.label_of("2~8년") == "2~8년"  # 미상 → 원문 그대로
    assert JOB_STATUS.label_of("") == ""


def test_job_status_default_is_a_valid_code():
    assert JOB_STATUS.has(JOB_STATUS_DEFAULT)
    assert JOB_STATUS_DEFAULT == "interest"


def test_job_status_meta_flags_partition_correctly():
    assert JOB_STATUS.codes_where("early") == {"interest", "planned"}
    assert JOB_STATUS.codes_where("advanced") == {"doc_pass", "interview", "offer", "rejected"}
    assert JOB_STATUS.codes_where("applied") == {
        "applied", "doc_pass", "interview", "offer", "rejected",
    }
    assert JOB_STATUS.codes_where("awaiting") == {"applied"}
    assert JOB_STATUS.codes_where("interviewing") == {"interview"}


def test_experience_level_bucket_metadata():
    assert EXPERIENCE_LEVEL.get("entry").meta["bucket"] == "신입"
    assert EXPERIENCE_LEVEL.get("y3_5").meta["bucket"] == "경력"
    assert EXPERIENCE_LEVEL.get("y3_5").meta["min_years"] == 3
    assert EXPERIENCE_LEVEL.get("y10p").meta["max_years"] is None
    assert EXPERIENCE_LEVEL.get("any").meta["bucket"] is None


def test_position_ordering_prefers_specific_labels():
    codes = POSITION.codes()
    assert codes.index("fullstack") < codes.index("backend")
    assert codes.index("data_eng") < codes.index("backend")


def test_region_code_equals_label():
    for member in REGION:
        assert member.code == member.label


def test_apply_channel_source_site_keys_cover_guessed_sites():
    # guess_source_site 가 돌려주는 사이트명들이 채널 추천에 매핑돼야 한다
    # (예전 SOURCE_SITE_TO_CHANNEL 에 없어 매핑이 실패하던 버그).
    for site in ("프로그래머스", "인크루트", "로켓펀치", "캐치"):
        matched = [
            m.code for m in APPLY_CHANNEL
            if any(k in site.lower() or site in k for k in m.meta.get("source_site_keys", ()))
        ]
        assert matched, site


def test_enum_label_global_handles_unknown_enum_and_code():
    assert enum_label("job_status", "interview") == "면접"
    assert enum_label("job_status", "2~8년") == "2~8년"
    assert enum_label("nonexistent", "x") == "x"
