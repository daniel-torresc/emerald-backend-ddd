"""Application settings loaded from environment variables and .env file."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database connection and pool settings."""

    model_config = SettingsConfigDict(env_prefix="DATABASE_", frozen=True)

    url: str = Field(min_length=1)
    pool_size: int = Field(default=10, ge=1)
    max_overflow: int = Field(default=20, ge=0)
    echo: bool = False
    echo_pool: bool = False


class JwtSettings(BaseSettings):
    """JWT token configuration."""

    model_config = SettingsConfigDict(env_prefix="JWT_", frozen=True)

    secret_key: str = Field(min_length=1)
    algorithm: Literal["HS256", "HS384", "HS512", "RS256"] = "HS256"
    access_token_ttl_minutes: int = Field(default=15, gt=0)
    refresh_token_ttl_days: int = Field(default=30, gt=0)
    issuer: str = Field(default="emerald-finance", min_length=1)


class OidcSettings(BaseSettings):
    """OIDC social login configuration (all optional)."""

    model_config = SettingsConfigDict(env_prefix="OIDC_", frozen=True)

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_redirect_uri: str | None = None

    @model_validator(mode="after")
    def validate_provider_completeness(self) -> OidcSettings:
        """If client_id is set for a provider, client_secret and redirect_uri must also be set."""
        providers = [
            ("google", self.google_client_id, self.google_client_secret, self.google_redirect_uri),
            (
                "microsoft",
                self.microsoft_client_id,
                self.microsoft_client_secret,
                self.microsoft_redirect_uri,
            ),
        ]
        for name, client_id, client_secret, redirect_uri in providers:
            if client_id is not None:
                missing = []
                if client_secret is None:
                    missing.append(f"{name}_client_secret")
                if redirect_uri is None:
                    missing.append(f"{name}_redirect_uri")
                if missing:
                    msg = f"When {name}_client_id is set, {', '.join(missing)} must also be set"
                    raise ValueError(msg)
        return self


class CorsSettings(BaseSettings):
    """CORS configuration."""

    model_config = SettingsConfigDict(env_prefix="CORS_", frozen=True)

    allowed_origins: list[str] = ["http://localhost:3000"]
    allow_credentials: bool = True
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]


class AppSettings(BaseSettings):
    """Root application settings composing all sub-settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        frozen=True,
    )

    app_name: str = Field(default="Emerald Finance", min_length=1)
    environment: Literal["development", "staging", "production", "testing"] = "development"
    debug: bool = False
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JwtSettings = Field(default_factory=JwtSettings)
    oidc: OidcSettings = Field(default_factory=OidcSettings)
    cors: CorsSettings = Field(default_factory=CorsSettings)
