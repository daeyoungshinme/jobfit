from app.services.text_formatter import render_bulleted_html


def test_consecutive_bullets_become_one_list():
    html = str(render_bulleted_html("• 첫 번째 항목\n• 두 번째 항목\n• 세 번째 항목"))
    assert html == "<ul><li>첫 번째 항목</li><li>두 번째 항목</li><li>세 번째 항목</li></ul>"


def test_bracketed_line_becomes_subheading_and_closes_list():
    html = str(render_bulleted_html("[Culture 조직 문화]\n• 유연근무제\n[Health 건강]\n• 건강검진 지원"))
    assert html == (
        "<h4>Culture 조직 문화</h4><ul><li>유연근무제</li></ul>"
        "<h4>Health 건강</h4><ul><li>건강검진 지원</li></ul>"
    )


def test_corner_bracket_line_becomes_subheading():
    # job_parser._BRACKET_LINE_PATTERN treats "【...】" as a section boundary
    # the same way it treats "[...]" — rendering should match that.
    html = str(render_bulleted_html("【유의사항】\n• 반드시 확인해주세요"))
    assert html == "<h4>유의사항</h4><ul><li>반드시 확인해주세요</li></ul>"


def test_wrapped_continuation_merges_into_previous_bullet():
    html = str(render_bulleted_html("• 아키텍처를 설계했고,\n확장성 측면에서 개선했습니다."))
    assert html == "<ul><li>아키텍처를 설계했고, 확장성 측면에서 개선했습니다.</li></ul>"


def test_plain_lines_without_bullets_become_paragraphs():
    html = str(render_bulleted_html("첫 문단입니다.\n둘째 문단입니다."))
    assert html == "<p>첫 문단입니다.</p><p>둘째 문단입니다.</p>"


def test_empty_text_returns_empty_markup():
    assert str(render_bulleted_html("")) == ""


def test_html_special_characters_are_escaped():
    html = str(render_bulleted_html("• <script>alert(1)</script> & 기타"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html
