from fastapi import APIRouter, Depends
from sqlmodel import Session
from pydantic import BaseModel
from app.db.database import get_session
from app.db import crud

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    tmdb_proxy: str | None = None


@router.get("/")
def get_settings(session: Session = Depends(get_session)):
    return crud.get_app_settings(session)


@router.put("/")
def update_settings(data: SettingsUpdate, session: Session = Depends(get_session)):
    return crud.update_app_settings(session, data.tmdb_proxy)
