from fastapi.templating import Jinja2Templates

from app.constants import FLASH_MESSAGES
from app.services.text_formatter import render_bulleted_html

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["bulleted"] = render_bulleted_html
templates.env.globals["flash_messages"] = FLASH_MESSAGES
