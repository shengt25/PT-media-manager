from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    db_path: str = "~/.config/ptmm/ptmm.db"
    backup_count: int = 5
    incomplete_ext: list[str] = [".part", ".!qB"]
    ignore_ext: list[str] = [".jpg", ".txt", ".nfo", ".srt", ".sub"]

    tmdb_api_key: str

    auth_enabled: bool = False
    auth_username: str = ""
    auth_password_hash: str = ""
    jwt_secret: str = ""

    model_config = SettingsConfigDict(env_file=".env")

    @model_validator(mode="after")
    def check_auth_config(self):
        if self.auth_enabled:
            missing = [f for f, v in [("AUTH_USERNAME", self.auth_username), ("AUTH_PASSWORD_HASH", self.auth_password_hash), ("JWT_SECRET", self.jwt_secret)] if not v]
            if missing:
                raise ValueError(f"AUTH_ENABLED=true requires: {', '.join(missing)}")
        return self


settings = Settings()