from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import analysis, jobs, resumes

_STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobFit", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(jobs.router)
app.include_router(resumes.router)
app.include_router(analysis.router)


@app.get("/")
def root():
    return RedirectResponse(url="/jobs")
