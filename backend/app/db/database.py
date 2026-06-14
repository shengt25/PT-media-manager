from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session
from app.config import settings


def get_db_path() -> Path:
    path = Path(settings.db_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


engine = create_engine(f"sqlite:///{get_db_path()}", connect_args={"check_same_thread": False})


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
