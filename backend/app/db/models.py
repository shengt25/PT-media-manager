from sqlmodel import SQLModel, Field
from sqlalchemy import CheckConstraint
from typing import Literal


class Entry(SQLModel, table=True):
    id:          int | None = Field(default=None, primary_key=True)
    name:        str = Field(unique=True)
    source_path: str = Field(unique=True)
    link_path:   str = Field(unique=True)
    media_type:  str  # 'movie' | 'tv'


class Media(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "scrape_status IN ('pending', 'confirmed', 'partial')",
            name="ck_media_scrape_status",
        ),
    )

    id:              int | None = Field(default=None, primary_key=True)
    entry_id:        int = Field(foreign_key="entry.id")
    source_name:     str
    date_added:      str
    scrape_status:   str = Field(default="pending")  # 'pending' | 'confirmed' | 'partial'
    tmdb_id:         int | None = None
    generated_files: str | None = None  # JSON list of file paths created by scrape
    size:            int | None = None  # bytes, sum of file sizes under link_path/source_name
    scrape_language: str | None = None
    image_language:  str | None = None


class AppSettings(SQLModel, table=True):
    # Singleton row (id=1) holding app-wide runtime settings
    id:         int | None = Field(default=1, primary_key=True)
    tmdb_proxy: str | None = None  # e.g. "http://127.0.0.1:7890", used for all TMDB requests
