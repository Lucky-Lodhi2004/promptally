from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Promptally API"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"
    SITE_URL: str = "https://promptally.com"
    
    # PostgreSQL Connection URL
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/promptally"
    
    # Optional checkout contention lock. PostgreSQL remains authoritative.
    REDIS_URL: str = ""

    # Security & JWT
    SECRET_KEY: str = "promptally-secret-key-change-in-production-super-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCKOUT_SECONDS: int = 900
    MAX_REQUEST_BODY_BYTES: int = 120 * 1024 * 1024
    MAX_UPLOAD_FILES: int = 100
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://promptally.com",
    ]

    # Device & IP Rate Limits
    MAX_ACCOUNTS_PER_IP: int = 2
    MAX_ACCOUNTS_PER_DEVICE: int = 2
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_READ_PER_MINUTE: int = 60
    # Optional shared secret sent by the Next.js server (header X-Internal-Render) so that
    # server-side renders for crawlers do not consume one shared per-IP budget. Empty = disabled.
    INTERNAL_RENDER_TOKEN: str = ""
    # Email delivery uses a dedicated Redis logical DB; no result backend is needed.
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6388/1"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_SECURITY: str = "starttls"
    SMTP_USERNAME: str = "contact@promptally.dev"
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "contact@promptally.dev"
    EMAIL_TOKEN_TTL_SECONDS: int = 900
    EMAIL_RESEND_COOLDOWN_SECONDS: int = 60

    # Razorpay (India - INR ~$1 equivalent)
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_PLAN_ID: str = ""
    # Seller OAuth application, separate from platform subscription credentials.
    RAZORPAY_PARTNER_CLIENT_ID: str = ""
    RAZORPAY_PARTNER_CLIENT_SECRET: str = ""
    RAZORPAY_PARTNER_WEBHOOK_SECRET: str = ""
    RAZORPAY_PARTNER_ENVIRONMENT: str = "test"
    RAZORPAY_PARTNER_REDIRECT_URI: str = ""

    # Dodo platform account (independent of sellers' accounts).
    DODO_API_KEY: str = ""
    DODO_WEBHOOK_SECRET: str = ""
    DODO_PRODUCT_ID: str = ""
    DODO_ENVIRONMENT: str = "test"
    CREDENTIALS_ENCRYPTION_KEY: str = ""

    # Only these direct peers may supply forwarding/country headers. Keep Uvicorn
    # proxy rewriting disabled so request.client remains the actual socket peer.
    TRUSTED_PROXY_CIDRS: List[str] = []
    # Both peer CIDR and this credential are required to trust client IP/country.
    TRUSTED_PROXY_TOKEN: str = ""
    GEOIP_DATABASE_PATH: str = ""
    # Optional operator-supplied USD/INR quote; otherwise fetch ECB reference rate.
    USD_TO_INR_RATE: str = ""
    FX_CACHE_SECONDS: int = 3600
    PRIVATE_STORAGE_DIR: Path = BASE_DIR / "private_uploads"

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # File and Media Uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"

    # IndexNow Key for instant search indexing
    INDEXNOW_KEY: str = "promptally-indexnow-key"

    # Product analytics (PostHog)
    POSTHOG_API_KEY: str = ""
    POSTHOG_HOST: str = "https://us.i.posthog.com"

    @property
    def secure_cookies(self) -> bool:
        return self.ENVIRONMENT != 'development' or self.SITE_URL.startswith('https://')

    class Config:
        case_sensitive = True
        env_file = str(ENV_PATH)
        extra = "allow"

settings = Settings()
