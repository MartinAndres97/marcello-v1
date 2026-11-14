from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.database import get_sessionmaker
from app.routers import admin, exports, survey
from app.seed import seed_survey
from app.templating import BASE_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    with get_sessionmaker()() as db:
        seed_survey(db)
    yield


settings = get_settings()
app = FastAPI(title="Marcello V1", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="marcello_admin",
                   max_age=settings.session_hours * 3600, same_site="strict", https_only=settings.cookie_secure)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy",
                                "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                                "frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if request.url.path.startswith(("/admin", "/api/admin")):
        response.headers["Cache-Control"] = "no-store"
    return response


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(survey.router)
app.include_router(admin.pages)
app.include_router(admin.auth)
app.include_router(admin.api)
app.include_router(exports.router)
