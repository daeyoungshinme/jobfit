from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db import init_db
from app.routers import analysis, jobs, resumes
from app.templates import templates

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobFit", lifespan=lifespan)


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render 404/5xx as the styled page for browser navigations; everything else
    (and API/non-HTML clients) keeps FastAPI's default JSON response."""
    if _wants_html(request):
        if exc.status_code == 404:
            return templates.TemplateResponse(
                request, "404.html", {"detail": exc.detail}, status_code=404
            )
        if exc.status_code >= 500:
            return templates.TemplateResponse(
                request, "500.html", {"detail": exc.detail}, status_code=exc.status_code
            )
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Unexpected errors: a styled page for browsers, plain 500 otherwise.
    Starlette still re-raises afterwards, so server logs / test failures are
    unaffected."""
    if _wants_html(request):
        return templates.TemplateResponse(request, "500.html", {}, status_code=500)
    return PlainTextResponse("Internal Server Error", status_code=500)


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(analysis.router)


@app.get("/")
def root():
    return RedirectResponse(url="/jobs")
