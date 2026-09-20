from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./naseem.db"
    run_migrations_on_start: bool = False

    # Google Sheets webhook
    sheet_webhook_url: str = ""

    # Meta CAPI
    meta_pixel_id: str = ""
    meta_access_token: str = ""

    # TikTok Events API
    tiktok_pixel_id: str = ""
    tiktok_access_token: str = ""

    # Snap CAPI
    snap_pixel_id: str = ""
    snap_access_token: str = ""

    # MaxMind GeoIP2 Insights (IP fraud detection)
    maxmind_account_id: str = ""
    maxmind_license_key: str = ""

    # Frontend origin for CORS
    frontend_url: str = "https://naseem.beauty"

    # Admin (Profit Calculator + stats)
    admin_api_key: str = ""

    # Environment
    environment: str = "production"

    # Temporary test mode: any phone, skip Saudi/VPN geo block.
    restrict_orders_to_saudi: bool = False

    # Pricing (SAR) — source of truth
    price_1: int = 199
    price_2: int = 279
    price_3: int = 349
    price_upsell: int = 99


settings = Settings()
