import re
from dataclasses import dataclass
from urllib.parse import urlparse

from app.constants import MAX_RAW_TEXT_CHARS
from app.enums import EXPERIENCE_LEVEL, POSITION, REGION
from app.services.skill_extractor import extract_skill_names, term_pattern

_MAIN_TASKS_HEADERS = [r"주요\s*업무", r"담당\s*업무", r"업무\s*내용", r"직무\s*내용", r"하는\s*일"]
_TECH_STACK_HEADERS = [r"기술\s*스택", r"사용\s*기술", r"개발\s*환경", r"tech\s*stack"]
_REQUIRED_HEADERS = [r"자격\s*요건", r"필수\s*요건", r"필수\s*사항", r"지원\s*자격", r"필수\s*역량", r"자격\s*조건"]
_PREFERRED_HEADERS = [
    r"우대\s*사항",
    r"우대\s*조건",
    r"우대\s*역량",
    r"우대\s*요건",
    r"우대",
    r"preferred\s*(?:qualifications?|skills?|experience)?",
    r"nice\s*to\s*have",
]
# 복지/전형 헤더는 이제 내용을 버리지 않고 별도 섹션으로 저장한다 (job-fit 분석엔
# 안 쓰지만 상세 페이지 표시·비교용). 여전히 앞선 우대/자격 섹션의 경계로도 작동한다.
_BENEFITS_HEADERS = [
    r"복리\s*후생", r"혜택\s*(?:및|/)?\s*복지", r"복지\s*(?:및|/)?\s*혜택",
    r"복지", r"혜택", r"근무\s*환경", r"benefits?", r"perks?",
]
_PROCESS_HEADERS = [
    r"채용\s*전형", r"전형\s*절차", r"채용\s*절차", r"모집\s*절차", r"채용\s*프로세스",
    r"전형\s*방법", r"지원\s*절차",
]
# 여전히 내용을 버리는 순수 stop 헤더 (근무조건/제출서류/지원방법 등).
_STOP_HEADERS = [
    r"근무\s*조건", r"제출\s*서류", r"지원\s*방법", r"접수\s*방법",
]

_HEADER_PATTERN = re.compile(
    "(?P<main_tasks>" + "|".join(_MAIN_TASKS_HEADERS) + ")"
    "|(?P<tech_stack>" + "|".join(_TECH_STACK_HEADERS) + ")"
    "|(?P<required>" + "|".join(_REQUIRED_HEADERS) + ")"
    "|(?P<preferred>" + "|".join(_PREFERRED_HEADERS) + ")"
    "|(?P<benefits>" + "|".join(_BENEFITS_HEADERS) + ")"
    "|(?P<process>" + "|".join(_PROCESS_HEADERS) + ")"
    "|(?P<stop>" + "|".join(_STOP_HEADERS) + ")",
    re.IGNORECASE,
)

_SECTION_LABELS = ("main_tasks", "tech_stack", "required", "preferred", "benefits", "process")

# Characters that only ever decorate a header line ("[자격요건]", "■ 우대사항",
# "혜택 및 복지 :") — stripped from both ends before checking whether the line
# is *entirely* a header. Real prose lines that merely mention "복지" inside a
# longer sentence (or inside another word like "복지카드") won't fullmatch
# after stripping, so they're left alone instead of being misread as headers.
# Includes "\r" as defense-in-depth against stray CRLF line endings that
# normalize_newlines() should already have stripped before this point.
_HEADER_DECORATION_CHARS = " \t\r[](){}【】-–—*■□▶▷◆◇○●◈▲▼✓✔•‣▪:：·|~="

# Strips a leading list-numbering prefix ("2. 우대사항", "3) 우대사항") before
# header matching, since digits/periods aren't decoration characters that
# _HEADER_DECORATION_CHARS.strip() would remove from the line.
_HEADER_NUMBERING_PATTERN = re.compile(r"^\s*\d+[.)]\s*")

# Separator between a header keyword and inline content on the same line
# ("우대사항 : Docker, AWS 경험", "우대사항 - Docker, AWS 경험"). Requiring one of
# these right after the header keyword (rather than accepting any trailing
# text) is what keeps a sentence like "우대사항이 있으신 분은..." from being
# misread as a header — there's no separator immediately after "우대사항" there.
_INLINE_HEADER_SEPARATOR_PATTERN = re.compile(r"\s*[:：\-–—]\s*")

# A line that is entirely wrapped in brackets ("[지원서 작성 Tip - 반드시
# 작성해주세요!]", "【유의사항】") but didn't match any known section/stop
# keyword above *and* mentions a note/tip-style keyword is, in practice, a
# boilerplate annotation rather than real section content — postings use
# this bracket convention to visually set apart notes, tips, and
# disclaimers. Treated as an implicit stop marker so it closes whatever
# tracked section is currently open instead of having its content (and
# everything after it, until the next recognized header) silently absorbed
# into that section, the way it otherwise would with no boundary. Checked
# against the raw line, before decoration-char stripping would remove the
# brackets themselves.
#
# Bracket lines *without* a note/tip keyword are deliberately left alone
# (not treated as a boundary) because postings just as commonly use the
# same bracket convention for category sub-headings *within* a section
# ("[플랫폼 개발]" inside 주요업무, followed by more bullets of that same
# section) — treating every bracket line as a stop would close the section
# immediately and drop everything after it.
# text_formatter.render_bulleted_html() already renders such a line as an
# <h4> sub-heading, so leaving it as ordinary section content is what the
# rest of the app expects.
_BRACKET_LINE_PATTERN = re.compile(r"^[\[【].*[\]】]$")
_BRACKET_NOTE_KEYWORDS_PATTERN = re.compile(r"tip|유의|안내|참고|주의|필독|note", re.IGNORECASE)

# 직무 추측 키워드는 app/enums.py 의 POSITION 멤버 meta["terms"] 에서 온다.
# POSITION 은 더 구체적인 라벨(풀스택)이 일반 라벨(백엔드/프론트엔드)보다 먼저
# 오도록 정렬돼 있어 그대로 순회하면 된다.
_POSITION_TERMS: list[tuple[str, tuple[str, ...]]] = [
    (m.code, m.meta.get("terms", ())) for m in POSITION if m.meta.get("terms")
]

_BRACKET_TITLE_PATTERN = re.compile(r"^\[(?P<company>[^\]]{1,50})\]\s*(?P<rest>.+)$")
# Excludes common trailing punctuation from the \S+ name capture so e.g.
# "(주)ABC," or "(주)ABC)" doesn't sweep the punctuation into the guessed name.
_COMPANY_NAME_CHARS = r"[^\s,.)\]}]+"
_COMPANY_PATTERN = re.compile(
    rf"\(주\)\s?{_COMPANY_NAME_CHARS}|㈜\s?{_COMPANY_NAME_CHARS}|{_COMPANY_NAME_CHARS}\s?주식회사"
)
# Job boards like Wanted often lead with a bullet-separated metadata line
# ("회사명∙지역∙경력조건") instead of a "[회사명] 직무명" bracket line. The
# negated classes exclude "\n" (defense-in-depth against a multi-line blob
# reaching here) and separators are [ \t]* rather than \s* so the match can
# never span a line.
_METADATA_LINE_PATTERN = re.compile(
    r"^(?P<company>[^∙·•\n]{1,50}?)[ \t]*[∙·•][ \t]*[^∙·•\n]{1,30}?[ \t]*[∙·•][ \t]*경력"
)

# Capped at 1-2 digits since real experience ranges ("3~5년") never go past
# double digits — an unbounded \d+ would also match unrelated 4-digit year
# ranges like "2020-2023년" (founding year, funding round) as if they were
# an experience level.
_EXPERIENCE_RANGE_PATTERN = re.compile(r"\b(\d{1,2})\s*[~\-]\s*(\d{1,2})\s*년")
_EXPERIENCE_MIN_PATTERN = re.compile(r"(\d+)\s*년\s*이상")

_ADDRESS_LABEL_PATTERN = re.compile(r"(?:회사\s*)?(?:주소|근무지|위치)\s*[:：]\s*(?P<value>.+)")
_SIDO_NAMES = "|".join(re.escape(code) for code in REGION.codes())
# Every quantifier is bounded and inter-token whitespace is [ \t]* (not \s*)
# so this can't backtrack catastrophically on a long pathological line or
# span a newline.
_ADDRESS_PATTERN = re.compile(
    rf"(?:{_SIDO_NAMES})(?:특별시|광역시|특별자치시|특별자치도|도)?[ \t]*"
    r"[가-힣]{1,12}(?:시|군|구)[ \t]*(?:[가-힣]{1,12}(?:시|군|구)[ \t]*)?"
    r"[가-힣0-9.\-]{1,40}(?:로|길)[ \t]*[0-9\-]{1,12}(?:[ \t]*,?[ \t]*[0-9]{1,4}층)?(?:[ \t]*\([가-힣0-9]{1,20}\))?"
)


def normalize_newlines(text: str) -> str:
    """Collapse CRLF/CR line endings to LF.

    Native <textarea> form submissions round-trip through CRLF regardless of
    what the DOM's .value reports, so raw_text can pick up "\\r\\n" on every
    edit save even though it was "\\n"-only right after creation. Section
    header detection in _find_header_lines/_split_sections works on whole
    lines and silently fails to match when a stray "\\r" survives, so this
    must run before that text is parsed or stored.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


@dataclass
class ParsedJobPosting:
    required_skills: list[str]
    preferred_skills: list[str]
    main_tasks_text: str
    required_text: str
    preferred_text: str
    sections_detected: bool
    benefits_text: str = ""
    process_text: str = ""


@dataclass
class GuessedFields:
    """Best-effort guesses for form fields, derived from pasted posting text.

    Empty string means "couldn't guess" — the user fills that field in manually,
    same as today.
    """

    title: str
    company: str
    position: str
    experience_level: str
    address: str
    employment_type: str = ""
    remote_policy: str = ""
    deadline: str = ""
    salary_text: str = ""


def _find_header_lines(lines: list[str]) -> list[tuple[int, str, str]]:
    """Return (line_index, label, inline_content) for every header line.

    Matching is restricted to whole lines (after stripping bullet/bracket
    decoration and any list-numbering prefix) rather than scanning the raw
    text for the keyword anywhere. That's what keeps a stray "복지" inside
    "복지카드" or a real sentence like "...성장하는 복지 끝판왕 기업" from being
    misread as a header, and keeps a header word at the end of one line
    (e.g. "...서비스 운영 지원") from bridging across the newline into an
    unrelated header on the next line ("자격요건") the way a plain text-wide
    regex search would.

    A line doesn't have to be *only* the header, though: "우대사항 : Docker,
    AWS 경험" is recognized too, with "Docker, AWS 경험" returned as
    inline_content to fold into that section's body. The colon/dash right
    after the header keyword is what makes this safe — without a separator
    there, trailing text is prose (e.g. "우대사항이 있으신 분은...") and the
    line is left alone.
    """
    headers: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        body = stripped_line.strip(_HEADER_DECORATION_CHARS)
        if not body:
            continue
        body = _HEADER_NUMBERING_PATTERN.sub("", body, count=1)
        if not body:
            continue
        match = _HEADER_PATTERN.fullmatch(body)
        if match:
            headers.append((i, match.lastgroup, ""))
            continue
        match = _HEADER_PATTERN.match(body)
        if match:
            sep_match = _INLINE_HEADER_SEPARATOR_PATTERN.match(body, match.end())
            if sep_match:
                headers.append((i, match.lastgroup, body[sep_match.end():].strip()))
            continue
        if _BRACKET_LINE_PATTERN.fullmatch(stripped_line) and _BRACKET_NOTE_KEYWORDS_PATTERN.search(body):
            headers.append((i, "stop", ""))
    return headers


def _split_sections(text: str) -> tuple[dict[str, str], bool]:
    """Split raw text into labeled sections based on section header lines.

    Falls back to treating the whole text as the required section when no
    recognizable header is present, since most postings lead with must-have
    qualifications. The second return value is False in that fallback case,
    so callers can tell "no headers recognized at all" apart from a posting
    that legitimately only has a required-qualifications section.
    """
    lines = text.splitlines()
    headers = _find_header_lines(lines)
    if not headers:
        sections = {"required": text, **{label: "" for label in _SECTION_LABELS if label != "required"}}
        return sections, False

    # Text before the first recognized header is usually a title/intro blurb,
    # not part of whichever section happens to come first — drop it rather
    # than folding it into that section (raw_text still keeps the full text).
    parts: dict[str, list[str]] = {label: [] for label in _SECTION_LABELS}
    for i, (line_no, label, inline) in enumerate(headers):
        if label == "stop":
            continue
        start = line_no + 1
        end = headers[i + 1][0] if i + 1 < len(headers) else len(lines)
        chunk_lines = [inline] + lines[start:end] if inline else lines[start:end]
        parts[label].append("\n".join(chunk_lines))

    sections = {label: "\n".join(chunk for chunk in chunks if chunk) for label, chunks in parts.items()}
    return sections, True


def apply_parsed_sections(job, parsed: ParsedJobPosting) -> None:
    """Write a ParsedJobPosting's section fields onto a JobPosting-like object.

    Shared by `jobs.py` (create/edit) and `db.py::_backfill_job_postings` so
    both keep the exact same set of fields in step with the parser output —
    the backfill previously refreshed the section *text* but left
    required_skills/preferred_skills stale.
    """
    job.main_tasks = parsed.main_tasks_text
    job.required_text = parsed.required_text
    job.preferred_text = parsed.preferred_text
    job.required_skills = parsed.required_skills
    job.preferred_skills = parsed.preferred_skills
    job.sections_detected = parsed.sections_detected
    job.benefits_text = parsed.benefits_text
    job.process_text = parsed.process_text


def parse_job_posting(raw_text: str) -> ParsedJobPosting:
    raw_text = (raw_text or "")[:MAX_RAW_TEXT_CHARS]
    sections, sections_detected = _split_sections(raw_text)
    required_text = sections["required"]
    preferred_text = sections["preferred"]
    tech_stack_text = sections["tech_stack"]
    required_skills = extract_skill_names(required_text + "\n" + tech_stack_text)
    preferred_skills = extract_skill_names(preferred_text)
    # A skill mentioned in both sections counts as required (the stronger claim).
    preferred_skills = [s for s in preferred_skills if s not in required_skills]
    return ParsedJobPosting(
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        main_tasks_text=sections["main_tasks"].strip(),
        required_text=required_text.strip(),
        preferred_text=preferred_text.strip(),
        sections_detected=sections_detected,
        benefits_text=sections["benefits"].strip(),
        process_text=sections["process"].strip(),
    )


_TITLE_SCAN_LINES = 5


def _guess_title_and_company(raw_text: str) -> tuple[str, str]:
    non_empty_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not non_empty_lines:
        return "", ""
    # Job boards often lead with a metadata line ("회사명∙지역∙경력조건") before
    # the actual "[회사명] 직무명" line, so scan a few lines for a bracket tag
    # instead of assuming it's always the very first line.
    for line in non_empty_lines[:_TITLE_SCAN_LINES]:
        bracket_match = _BRACKET_TITLE_PATTERN.match(line)
        if bracket_match:
            return bracket_match.group("rest").strip()[:200], bracket_match.group("company").strip()
    # No bracket line — fall back to a "회사명∙지역∙경력..." metadata line, using
    # the next non-empty line (not the metadata line itself) as the title.
    for i, line in enumerate(non_empty_lines[:_TITLE_SCAN_LINES]):
        meta_match = _METADATA_LINE_PATTERN.match(line)
        if meta_match:
            company = meta_match.group("company").strip()[:50]
            title = non_empty_lines[i + 1][:200] if i + 1 < len(non_empty_lines) else ""
            return title, company
    return non_empty_lines[0][:200], ""


def _guess_company(raw_text: str) -> str:
    match = _COMPANY_PATTERN.search(raw_text)
    return match.group(0).strip() if match else ""


def _guess_position(title: str, raw_text: str) -> str:
    """제목·본문에서 직무를 추측해 POSITION 코드를 돌려준다 (없으면 "")."""
    for code, terms in _POSITION_TERMS:
        if any(term_pattern(term).search(title) for term in terms):
            return code
    for code, terms in _POSITION_TERMS:
        if any(term_pattern(term).search(raw_text) for term in terms):
            return code
    return ""


def guess_position_code(title: str, raw_text: str = "") -> str:
    """제목·본문에서 POSITION 코드를 추측한다 (없으면 ""). 공개 래퍼 —
    이력서 target_position 백필 등 파서 밖에서도 재사용한다."""
    return _guess_position(title, raw_text)


def _experience_code_for_range(lo: int, hi: int) -> str:
    """(lo, hi) 가 표준 버킷의 경계와 정확히 일치하면 그 코드를, 아니면 "lo~hi년"
    자유 문자열을 돌려준다 (사용자가 공고에 적힌 정확한 수치를 보도록)."""
    for member in EXPERIENCE_LEVEL:
        if member.meta.get("min_years") == lo and member.meta.get("max_years") == hi:
            return member.code
    return f"{lo}~{hi}년"


def _guess_experience_level(raw_text: str) -> str:
    if re.search(r"신입", raw_text):
        return "entry"
    if re.search(r"경력\s*무관|\b무관\b", raw_text):
        return "any"
    range_match = _EXPERIENCE_RANGE_PATTERN.search(raw_text)
    if range_match:
        return _experience_code_for_range(int(range_match.group(1)), int(range_match.group(2)))
    min_match = _EXPERIENCE_MIN_PATTERN.search(raw_text)
    if min_match:
        n = int(min_match.group(1))
        return "y10p" if n >= 10 else f"{n}년 이상"
    return ""


def _guess_address(raw_text: str) -> str:
    label_match = _ADDRESS_LABEL_PATTERN.search(raw_text)
    if label_match:
        return label_match.group("value").strip()[:300]
    pattern_match = _ADDRESS_PATTERN.search(raw_text)
    return pattern_match.group(0).strip()[:300] if pattern_match else ""


# 고용형태 — 더 구체적인 것부터. 아무것도 안 걸리면 "" (정규직 단정은 하지 않음).
_EMPLOYMENT_TERMS: list[tuple[str, tuple[str, ...]]] = [
    ("contract", ("계약직",)),
    ("intern", ("인턴", "인턴십", "체험형 인턴", "채용전환형")),
    ("dispatch", ("파견직", "파견")),
    ("freelance", ("프리랜서", "프리랜스", "외주")),
    ("fulltime", ("정규직",)),
]

_HYBRID_PATTERN = re.compile(r"하이브리드|주\s*\d\s*(?:일|회)\s*(?:재택|출근)|부분\s*재택|재택\s*병행")
_REMOTE_PATTERN = re.compile(r"(?:완전\s*|풀\s*)?재택(?:\s*근무)?|리모트|remote|원격\s*근무", re.IGNORECASE)

_DEADLINE_DATE_PATTERN = re.compile(
    r"(?:마감|접수\s*마감|모집\s*마감|~|까지|채용\s*종료)[^\n0-9]{0,8}(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})"
)
_ALWAYS_HIRING_PATTERN = re.compile(r"상시\s*채용|수시\s*채용|채용\s*시\s*(?:마감|까지)|충원\s*시\s*마감")
_SALARY_PATTERN = re.compile(
    r"(?:연봉|급여|연 소득|처우)[^\n]{0,40}?\d[\d,]*\s*(?:만원|만\s*원|억|천만원)[^\n]{0,15}"
)


def _guess_employment_type(raw_text: str) -> str:
    for code, terms in _EMPLOYMENT_TERMS:
        if any(term_pattern(term).search(raw_text) for term in terms):
            return code
    return ""


def _guess_remote_policy(raw_text: str) -> str:
    if _HYBRID_PATTERN.search(raw_text):
        return "hybrid"
    if _REMOTE_PATTERN.search(raw_text):
        return "remote"
    return ""


def _guess_deadline(raw_text: str) -> str:
    if _ALWAYS_HIRING_PATTERN.search(raw_text):
        return "상시"
    match = _DEADLINE_DATE_PATTERN.search(raw_text)
    if match:
        year, month, day = (int(g) for g in match.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def _guess_salary(raw_text: str) -> str:
    match = _SALARY_PATTERN.search(raw_text)
    return match.group(0).strip()[:200] if match else ""


_SOURCE_SITE_DOMAINS: list[tuple[str, str]] = [
    ("saramin.co.kr", "사람인"),
    ("jobkorea.co.kr", "잡코리아"),
    ("wanted.co.kr", "원티드"),
    ("programmers.co.kr", "프로그래머스"),
    ("jobplanet.co.kr", "잡플래닛"),
    ("incruit.com", "인크루트"),
    ("rocketpunch.com", "로켓펀치"),
    ("linkedin.com", "LinkedIn"),
    ("catch.co.kr", "캐치"),
]


def guess_source_site(url: str) -> str:
    """Guess the job board name from a posting URL's domain.

    Falls back to the bare domain when it isn't a recognized Korean job
    board, so the field isn't just blank for e.g. a company's own careers
    page — still better than nothing, and the user can edit it either way.
    """
    if not url:
        return ""
    # urlparse() puts the whole string into .path (not .netloc) when there's
    # no scheme, which is the common case for pasted URLs like
    # "wanted.co.kr/wd/123" — prepend "//" so it's parsed as authority+path.
    if "://" not in url:
        url = "//" + url
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return ""
    for domain, label in _SOURCE_SITE_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return label
    return host


def guess_posting_fields(raw_text: str) -> GuessedFields:
    """Best-effort guesses for title/company/position/experience_level/address from raw_text.

    Rule-based only (no external AI API), matching this project's skill
    extraction approach. Callers should treat every field as a suggestion the
    user can still edit before saving.
    """
    raw_text = (raw_text or "")[:MAX_RAW_TEXT_CHARS]
    title, company = _guess_title_and_company(raw_text)
    if not company:
        company = _guess_company(raw_text)
    position = _guess_position(title, raw_text)
    experience_level = _guess_experience_level(raw_text)
    address = _guess_address(raw_text)
    return GuessedFields(
        title=title,
        company=company,
        position=position,
        experience_level=experience_level,
        address=address,
        employment_type=_guess_employment_type(raw_text),
        remote_policy=_guess_remote_policy(raw_text),
        deadline=_guess_deadline(raw_text),
        salary_text=_guess_salary(raw_text),
    )
