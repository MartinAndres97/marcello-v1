import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import require_admin
from app.services import export_service as ex
from app.services import repository

log = logging.getLogger("marcello.export")
router = APIRouter(prefix="/api/admin/export", dependencies=[Depends(require_admin)])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file(content: bytes, media_type: str, ext: str) -> Response:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Response(content, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="marcello_v1_{stamp}.{ext}"',
        "Cache-Control": "no-store",
    })


@router.get("/xlsx")
def export_xlsx(include_test: bool = False, db: Session = Depends(get_db)):
    return _file(ex.build_xlsx(repository.load_submissions(db, include_test)), XLSX, "xlsx")


@router.get("/csv")
def export_csv(include_test: bool = False, db: Session = Depends(get_db)):
    return _file(ex.build_csv(repository.load_submissions(db, include_test)), "text/csv; charset=utf-8", "csv")


@router.get("/json")
def export_json(include_test: bool = False, db: Session = Depends(get_db)):
    return _file(ex.build_json(repository.load_submissions(db, include_test)), "application/json", "json")


def _backup(fmt: str, media_type: str) -> Response:
    try:
        return _file(ex.run_pg_dump(fmt), media_type, fmt)
    except ex.BackupError as exc:
        log.error("Respaldo %s fallido: %s", fmt, exc)
        raise HTTPException(status_code=500, detail="No se pudo generar el respaldo de PostgreSQL")


@router.get("/postgres.sql")
def export_sql():
    return _backup("sql", "application/sql")


@router.get("/postgres.dump")
def export_dump():
    return _backup("dump", "application/octet-stream")
