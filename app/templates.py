from fastapi.templating import Jinja2Templates

from app.constants import FLASH_MESSAGES
from app.services.text_formatter import render_bulleted_html

def nav_active_for(path: str) -> str:
    if path.startswith("/resumes"):
        return "resumes"
    if path.startswith("/analysis"):
        return "analysis"
    return "jobs"


templates = Jinja2Templates(directory="app/templates")
templates.env.filters["bulleted"] = render_bulleted_html
templates.env.globals["flash_messages"] = FLASH_MESSAGES
templates.env.globals["nav_active_for"] = nav_active_for
