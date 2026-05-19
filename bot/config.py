from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    owner_id: int
    master_channel_id: int
    control_panel_chat_id: int

    database_url: str

    sightengine_api_user: str = ""
    sightengine_api_secret: str = ""

    toxicity_threshold: float = 0.7
    nsfw_threshold: float = 0.5

    analytics_hub_channel_id: Optional[int] = None        # numeric ID for copying messages
    analytics_hub_channel_username: Optional[str] = None  # @username for web scraping views

    broadcast_rate_limit: int = 25
    media_group_delay: float = 1.0

    daily_report_time: str = "07:00"
    backup_day_of_week: int = 0

    @field_validator("daily_report_time")
    @classmethod
    def validate_time(cls, v: str) -> str:
        parts = v.split(":")
        assert len(parts) == 2 and all(p.isdigit() for p in parts), "daily_report_time must be HH:MM"
        return v

    @property
    def daily_report_hour(self) -> int:
        return int(self.daily_report_time.split(":")[0])

    @property
    def daily_report_minute(self) -> int:
        return int(self.daily_report_time.split(":")[1])


settings = Settings()
