import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import LoginIn
from app.security import client_ip, is_admin, login_limiter, require_admin, verify_admin
from app.services import analytics, repository
from app.templating import templates

pages = APIRouter()
auth = APIRouter(prefix="/api/admin")
api = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@pages.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    if not is_admin(request):
        return RedirectResponse("/admin/login", status_code=303)
    return templates.TemplateResponse(request, "admin.html", {})


@pages.get("/admin/login", include_in_schema=False)
def login_page(request: Request):
    if is_admin(request):
        return RedirectResponse("/admin", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@auth.post("/login")
def login(payload: LoginIn, request: Request):
    ip = client_ip(request)
    if login_limiter.blocked(ip):
        raise HTTPException(status_code=429, detail="Demasiados intentos fallidos. Intente de nuevo en unos minutos.")
    if not verify_admin(payload.username, payload.password):
        login_limiter.hit(ip)
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    request.session.clear()
    request.session["admin"] = True
    return {"ok": True}


@auth.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@api.get("/me")
def me():
    return {"admin": True}


@api.get("/dashboard")
def dashboard(include_test: bool = False, db: Session = Depends(get_db)):
    return analytics.compute_dashboard(repository.load_submissions(db, include_test))


@api.get("/submissions")
def submissions(
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
    q: Optional[str] = Query(None, max_length=100), profile: Optional[int] = Query(None, ge=1, le=10),
    country: Optional[str] = Query(None, max_length=100), region: Optional[str] = Query(None, max_length=100),
    city: Optional[str] = Query(None, max_length=100), date_from: Optional[date] = None,
    date_to: Optional[date] = None, include_test: bool = False, db: Session = Depends(get_db),
):
    total, items = repository.list_submissions(
        db, page=page, page_size=page_size, q=q, profile=profile, country=country, region=region, city=city,
        date_from=date_from, date_to=date_to, include_test=include_test)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@api.get("/submissions/{submission_id}")
def submission_detail(submission_id: uuid.UUID, db: Session = Depends(get_db)):
    detail = repository.get_submission_detail(db, submission_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Envío no encontrado")
    return detail
