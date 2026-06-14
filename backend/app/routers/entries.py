import shutil
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from pydantic import BaseModel
from pathlib import Path
from app.db.database import get_session
from app.db.models import Entry
from app.db import crud

router = APIRouter(prefix="/entries", tags=["entries"])


class EntryCreate(BaseModel):
    name: str
    source_path: str
    link_path: str
    media_type: str


class EntryUpdate(BaseModel):
    name: str | None = None
    source_path: str | None = None
    link_path: str | None = None
    media_type: str | None = None


def _normalize_path(p: str) -> str:
    return str(Path(p).expanduser().resolve())


def _validate_create(data: EntryCreate, session: Session):
    if not data.source_path.strip() or not data.link_path.strip():
        raise HTTPException(400, "source_path and link_path cannot be empty")
    if data.media_type not in ("movie", "tv"):
        raise HTTPException(400, "media_type must be 'movie' or 'tv'")
    source = _normalize_path(data.source_path)
    link = _normalize_path(data.link_path)
    if source == link:
        raise HTTPException(400, "source_path and link_path must be different")
    all_entries = crud.entry_get_all(session)
    for e in all_entries:
        if e.name == data.name:
            raise HTTPException(400, f"Entry name '{data.name}' already exists")
        if e.source_path == source:
            raise HTTPException(400, f"source_path already used by '{e.name}'")
        if e.link_path == link:
            raise HTTPException(400, f"link_path already used by '{e.name}'")
    if not Path(source).exists():
        raise HTTPException(400, f"source_path does not exist: {source}")


@router.get("/")
def list_entries(session: Session = Depends(get_session)):
    return crud.entry_get_all(session)


@router.post("/", status_code=201)
def create_entry(data: EntryCreate, session: Session = Depends(get_session)):
    _validate_create(data, session)
    source = _normalize_path(data.source_path)
    link = _normalize_path(data.link_path)
    Path(link).mkdir(parents=True, exist_ok=True)
    entry = Entry(name=data.name, source_path=source, link_path=link, media_type=data.media_type)
    return crud.entry_create(session, entry)


@router.patch("/{entry_id}")
def update_entry(entry_id: int, data: EntryUpdate, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    if data.name is not None:
        entry.name = data.name
    if data.source_path is not None:
        entry.source_path = _normalize_path(data.source_path)
    if data.link_path is not None:
        entry.link_path = _normalize_path(data.link_path)
    if data.media_type is not None:
        if data.media_type not in ("movie", "tv"):
            raise HTTPException(400, "media_type must be 'movie' or 'tv'")
        entry.media_type = data.media_type
    return crud.entry_update(session, entry)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, session: Session = Depends(get_session)):
    entry = crud.entry_get(session, entry_id)
    if not entry:
        raise HTTPException(404, "Entry not found")
    shutil.rmtree(entry.link_path, ignore_errors=True)
    for media in crud.media_get_by_entry(session, entry_id):
        crud.media_delete(session, media)
    crud.entry_delete(session, entry)
