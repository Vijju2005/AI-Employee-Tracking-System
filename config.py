"""
EBT System — Configuration
All sensitive values are loaded from environment variables / .env file.
"""

import os
from datetime import timedelta
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str) -> str:
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in your values."
        )
    return value


class Config:
    def __init__(self):
        # Refresh and evaluate attributes dynamically on instance instantiation
        self.DB_HOST = os.environ.get("DB_HOST", "localhost")
        self.DB_PORT = os.environ.get("DB_PORT", "3306")
        self.DB_NAME = os.environ.get("DB_NAME", "ebt_system")
        self.DB_USER = os.environ.get("DB_USER", "ebt_app")
        self.DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

        _raw_url = (
            os.environ.get("DATABASE_URL", "").strip()
            or os.environ.get("JAWSDB_URL", "").strip()
            or os.environ.get("MYSQL_URL", "").strip()
        )
        _cloud_db_url = _raw_url if _raw_url else None
        _db_backend = os.environ.get("DB_USE_SQLITE", "0")

        if _cloud_db_url:
            if _cloud_db_url.startswith("mysql://"):
                self.SQLALCHEMY_DATABASE_URI = _cloud_db_url.replace("mysql://", "mysql+pymysql://", 1)
            else:
                self.SQLALCHEMY_DATABASE_URI = _cloud_db_url
        elif _db_backend == "1":
            _sqlite_path = os.path.join(os.path.dirname(__file__), "ebt_system.db")
            self.SQLALCHEMY_DATABASE_URI = f"sqlite:///{_sqlite_path}"
        else:
            _user = quote_plus(self.DB_USER)
            _pass = quote_plus(self.DB_PASSWORD)
            self.SQLALCHEMY_DATABASE_URI = (
                f"mysql+pymysql://{_user}:{_pass}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
            )

        _engine_opts = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "pool_timeout": 20,
            "max_overflow": 10,
        }

        _is_tidb = (
            "tidbcloud.com" in (self.SQLALCHEMY_DATABASE_URI or "")
            or self.DB_HOST.endswith("tidbcloud.com")
            or "tidbcloud" in self.DB_HOST
            or os.environ.get("DB_SSL", "").lower() in ("true", "1", "yes")
        )
        if _is_tidb:
            try:
                import certifi
                _ca_path = certifi.where()
            except ImportError:
                _ca_path = "/etc/ssl/certs/ca-certificates.crt"

            _engine_opts["connect_args"] = {
                "ssl": {
                    "ca": _ca_path,
                    "check_hostname": True,
                }
            }

        self.SQLALCHEMY_ENGINE_OPTIONS = _engine_opts

    # ── Flask ──────────────────────────────────────────────────────────
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-insecure-key-change-in-production")
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_SECRET_KEY: str = os.environ.get("WTF_CSRF_SECRET_KEY", SECRET_KEY)

    # ── Session ────────────────────────────────────────────────────────
    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    # ── Database Class-Level Fallbacks ─────────────────────────────────
    DB_HOST: str = os.environ.get("DB_HOST", "localhost")
    DB_PORT: str = os.environ.get("DB_PORT", "3306")
    DB_NAME: str = os.environ.get("DB_NAME", "ebt_system")
    DB_USER: str = os.environ.get("DB_USER", "ebt_app")
    DB_PASSWORD: str = os.environ.get("DB_PASSWORD", "")

    SQLALCHEMY_DATABASE_URI: str = "mysql+pymysql://ebt_app@localhost:3306/ebt_system?charset=utf8mb4"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_timeout": 20,
        "max_overflow": 10,
    }


    # ── Application ────────────────────────────────────────────────────
    APP_NAME: str = os.environ.get("APP_NAME", "EBT System")
    TIMEZONE: str = os.environ.get("TIMEZONE", "Asia/Kolkata")

    # ── Pagination ─────────────────────────────────────────────────────
    ITEMS_PER_PAGE: int = 15

    # ── Report output directory ────────────────────────────────────────
    REPORTS_DIR: str = os.path.join(os.path.dirname(__file__), "app", "static", "reports")

    # ── Email / Flask-Mail ─────────────────────────────────────────────
    MAIL_SERVER: str = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT: int = int(os.environ.get("MAIL_PORT", 25))
    MAIL_USE_TLS: bool = os.environ.get("MAIL_USE_TLS", "false").lower() in ("true", "1", "yes")
    MAIL_USE_SSL: bool = os.environ.get("MAIL_USE_SSL", "false").lower() in ("true", "1", "yes")
    MAIL_USERNAME: str | None = os.environ.get("MAIL_USERNAME") or None
    MAIL_PASSWORD: str | None = os.environ.get("MAIL_PASSWORD") or None
    MAIL_DEFAULT_SENDER: str = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME") or "noreply@ebtsystem.local"
    )
    MAIL_SUPPRESS_SEND: bool = os.environ.get("MAIL_SUPPRESS_SEND", "true").lower() in ("true", "1", "yes")


class DevelopmentConfig(Config):
    DEBUG: bool = True
    FLASK_ENV: str = "development"

    def __init__(self):
        super().__init__()


class ProductionConfig(Config):
    DEBUG: bool = False
    FLASK_ENV: str = "production"
    SESSION_COOKIE_SECURE: bool = True
    WTF_CSRF_SSL_STRICT: bool = True

    def __init__(self):
        super().__init__()
        # Enforce required env vars in production
        _require_env("SECRET_KEY")
        if not (os.environ.get("DATABASE_URL") or os.environ.get("JAWSDB_URL") or os.environ.get("MYSQL_URL") or os.environ.get("DB_USE_SQLITE") == "1"):
            _require_env("DB_PASSWORD")


class TestingConfig(Config):
    TESTING: bool = True
    WTF_CSRF_ENABLED: bool = False  # Disable CSRF in tests
    # Use SQLite in-memory for tests — no MySQL required in sandbox/CI
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}   # SQLite doesn't need pool options

    def __init__(self):
        super().__init__()
        self.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        self.SQLALCHEMY_ENGINE_OPTIONS = {}


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
