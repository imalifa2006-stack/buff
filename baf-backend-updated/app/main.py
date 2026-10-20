from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from . import db
from .config import settings
from .routes import auth, reports


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect(settings.database_url)
    yield
    await db.close()


app = FastAPI(title="Baf API", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(reports.router)


@app.get("/api/health")
async def health():
    return {"ok": True}


# The Mini App itself (web/index.html) is served from the same origin, so no CORS is needed.
WEB = Path(__file__).resolve().parent.parent / "web"
if WEB.exists():
    app.mount("/", StaticFiles(directory=str(WEB), html=True), name="web")
