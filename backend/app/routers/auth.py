import bcrypt
from fastapi import APIRouter, Depends, Form, HTTPException, Response
from app.config import settings
from app.core.auth import create_token, verify_token, COOKIE_NAME

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(response: Response, username: str = Form(), password: str = Form()):
    if not settings.auth_enabled:
        raise HTTPException(status_code=404, detail="Auth not enabled")
    if username != settings.auth_username:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(password.encode(), settings.auth_password_hash.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.auth_enabled,
        max_age=30 * 24 * 3600,
    )
    return {"authenticated": True, "token": token}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax")
    return {"authenticated": False}


@router.get("/me")
def me(_=Depends(verify_token)):
    return {"authenticated": True}
