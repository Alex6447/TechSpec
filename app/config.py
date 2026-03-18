from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Telegram
    telegram_bot_token: str

    # Database
    database_url: str

    # Security
    master_key: str
    admin_token: str

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    twa_base_url: str = "http://localhost:8000"

    # Arqen B2B Platform
    arqen_base_url: str = "https://sandbox.arqen.finance"


settings = Settings()
