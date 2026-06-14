import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import init_db
from app.routers import entries, media, scan, scrape
from app.routers import auth as auth_router
from app.core.auth import verify_token
from app.core.backup import run_backup, _needs_backup
from app.config import settings

BACKUP_CHECK_INTERVAL = 24 * 3600


async def backup_loop():
    while True:
        if _needs_backup():
            run_backup()
        await asyncio.sleep(BACKUP_CHECK_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(backup_loop())
    yield


app = FastAPI(
    title="PT Media Manager",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.auth_enabled else "/docs",
    redoc_url=None if settings.auth_enabled else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router must be publicly accessible
app.include_router(auth_router.router)

# All other routers require token verification
app.include_router(entries.router, dependencies=[Depends(verify_token)])
app.include_router(media.router, dependencies=[Depends(verify_token)])
app.include_router(scan.router, dependencies=[Depends(verify_token)])
app.include_router(scrape.router, dependencies=[Depends(verify_token)])
