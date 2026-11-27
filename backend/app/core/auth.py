from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import Cookie, Header, HTTPException
from app.config import settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30
COOKIE_NAME = "ptmm_token"


def create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": username, "exp": expire}, settings.jwt_secret, algorithm=ALGORITHM)


async def verify_token(
    ptmm_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
):
    if not settings.auth_enabled:
        return None
    token = ptmm_token
    if token is None and authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
