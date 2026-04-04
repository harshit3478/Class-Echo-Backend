from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CLOUDINARY_URL: str | None = None
    CLOUDINARY_CLOUD_NAME: str | None = None
    CLOUDINARY_API_KEY: str | None = None
    CLOUDINARY_API_SECRET: str | None = None

    REDIS_URL: str = "redis://localhost:6379/0"

    ADMIN_NAME: str | None = None
    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None

    @field_validator(
        "DATABASE_URL",
        "SECRET_KEY",
        "CLOUDINARY_URL",
        "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY",
        "CLOUDINARY_API_SECRET",
        "REDIS_URL",
        "ADMIN_NAME",
        "ADMIN_EMAIL",
        "ADMIN_PASSWORD",
        mode="before",
    )
    @classmethod
    def strip_env_strings(cls, value: str | None):
        if isinstance(value, str):
            cleaned = value.strip()
            while cleaned and cleaned[0] in {'"', "'", "`"}:
                cleaned = cleaned[1:].strip()
            while cleaned and cleaned[-1] in {'"', "'", "`"}:
                cleaned = cleaned[:-1].strip()
            return cleaned
        return value

    @model_validator(mode="after")
    def normalize_cloudinary_config(self):
        cloudinary_url = (
            self.CLOUDINARY_URL
            or self.CLOUDINARY_CLOUD_NAME
            or self.CLOUDINARY_API_KEY
            or self.CLOUDINARY_API_SECRET
        )

        if isinstance(cloudinary_url, str) and cloudinary_url.startswith("cloudinary://"):
            parsed = urlparse(cloudinary_url)
            self.CLOUDINARY_CLOUD_NAME = self.strip_env_strings(parsed.hostname)
            self.CLOUDINARY_API_KEY = self.strip_env_strings(parsed.username)
            self.CLOUDINARY_API_SECRET = self.strip_env_strings(parsed.password)

        missing = [
            name
            for name in (
                "CLOUDINARY_CLOUD_NAME",
                "CLOUDINARY_API_KEY",
                "CLOUDINARY_API_SECRET",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Missing Cloudinary configuration: {', '.join(missing)}")

        return self

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
