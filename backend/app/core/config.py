from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ticket Booking System"
    database_url: str = "postgresql+psycopg://tickets:tickets@localhost:5432/tickets"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 1440
    seat_hold_ttl_minutes: int = 10
    waitlist_offer_ttl_minutes: int = 10
    frontend_url: str = "http://localhost:5173"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "tickets@example.com"
    smtp_from_name: str = "Ticket Booking System"
    scheduler_interval_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

