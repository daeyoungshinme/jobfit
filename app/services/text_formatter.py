import re

from markupsafe import Markup, escape

_BULLET_PATTERN = re.compile(r"^(?:[•\-*·▪‣◦▶○]|\d+[.)])\s+")
# Matches both bracket styles job_parser._BRACKET_LINE_PATTERN treats as a
# section-boundary/sub-heading convention ("[...]" and "【...】"), so a line
# recognized as a heading there renders as <h4> here too instead of <p>.
_HEADING_LINE_PATTERN = re.compile(r"^(?:\[(?P<square>.+)\]|【(?P<corner>.+)】)$")


def render_bulleted_html(text: str) -> Markup:
    """Render plain posting text as structured HTML for display.

    Bullet-prefixed lines become a `<ul>`, lines fully wrapped in brackets
    ("[Culture 조직 문화]") become `<h4>` sub-headings, and a non-bulleted
    line right after a bullet (a wrapped continuation of that bullet's
    sentence in the source text) is appended to the previous `<li>` instead
    of starting a stray paragraph. Everything else is a `<p>`.

    Storage stays plain text; this only affects rendering, and every text
    fragment is escaped before assembly since the source is pasted from an
    external site.
    """
    if not text:
        return Markup("")

    html_parts: list[str] = []
    list_items: list[str] = []

    def flush_list() -> None:
        if list_items:
            items_html = "".join(f"<li>{item}</li>" for item in list_items)
            html_parts.append(f"<ul>{items_html}</ul>")
            list_items.clear()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        bullet_match = _BULLET_PATTERN.match(line)
        if bullet_match:
            list_items.append(str(escape(line[bullet_match.end():].strip())))
            continue

        heading_match = _HEADING_LINE_PATTERN.match(line)
        if heading_match:
            heading_text = (heading_match.group("square") or heading_match.group("corner")).strip()
            if heading_text:
                flush_list()
                html_parts.append(f"<h4>{escape(heading_text)}</h4>")
                continue

        if list_items:
            list_items[-1] += " " + str(escape(line))
        else:
            html_parts.append(f"<p>{escape(line)}</p>")

    flush_list()
    return Markup("".join(html_parts))
