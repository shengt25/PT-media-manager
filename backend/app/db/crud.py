from sqlmodel import Session, select
from app.db.models import Entry, Media


# --- Entry ---

def entry_get_all(session: Session) -> list[Entry]:
    return session.exec(select(Entry)).all()


def entry_get(session: Session, entry_id: int) -> Entry | None:
    return session.get(Entry, entry_id)


def entry_get_by_name(session: Session, name: str) -> Entry | None:
    return session.exec(select(Entry).where(Entry.name == name)).first()


def entry_create(session: Session, entry: Entry) -> Entry:
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def entry_update(session: Session, entry: Entry) -> Entry:
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def entry_delete(session: Session, entry: Entry):
    session.delete(entry)
    session.commit()


# --- Media ---

def media_get_by_entry(session: Session, entry_id: int) -> list[Media]:
    return session.exec(select(Media).where(Media.entry_id == entry_id)).all()


def media_get(session: Session, media_id: int) -> Media | None:
    return session.get(Media, media_id)


def media_get_by_source_name(session: Session, entry_id: int, source_name: str) -> Media | None:
    return session.exec(
        select(Media).where(Media.entry_id == entry_id, Media.source_name == source_name)
    ).first()


def media_get_by_source_and_link(session: Session, entry_id: int, source_name: str, video_stem: str | None) -> Media | None:
    return session.exec(
        select(Media).where(
            Media.entry_id == entry_id,
            Media.source_name == source_name,
            Media.video_stem == video_stem,
        )
    ).first()


def media_create(session: Session, media: Media) -> Media:
    session.add(media)
    session.commit()
    session.refresh(media)
    return media


def media_update(session: Session, media: Media) -> Media:
    session.add(media)
    session.commit()
    session.refresh(media)
    return media


def media_delete(session: Session, media: Media):
    session.delete(media)
    session.commit()
