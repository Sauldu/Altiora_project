from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    jwt_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(64))
    database_url: str = Field(default="sqlite:///./auth.db")
    access_token_expire_minutes: int = 60
    host: str = "0.0.0.0"
    port: int = 8005


settings = Settings()
