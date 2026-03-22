from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional, List
from pathlib import Path

class Settings(BaseSettings):

    # API Settings
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")
    debug: bool = Field(False, alias="DEBUG")
    testing: bool = Field(False, alias="TESTING")
    rate_limit_per_minute: int = Field(300, alias="RATE_LIMIT_PER_MINUTE") # Increased for development

    # Browser Settings
    browser_headless: bool = Field(True, alias="BROWSER_HEADLESS")
    browser_max_pages: int = Field(20, alias="BROWSER_MAX_PAGES") # Increased
    browser_timeout: int = Field(60000, alias="BROWSER_TIMEOUT") # Increased from 30s

    # Audit Settings
    default_viewport_width: int = Field(1280, alias="VIEWPORT_WIDTH")
    default_viewport_height: int = Field(720, alias="VIEWPORT_HEIGHT")
    max_audit_duration: int = Field(600, alias="MAX_AUDIT_DURATION") # Increased

    # Engine Settings
    enabled_engines: List[str] = Field(
        ["wcag_deterministic", "contrast_engine", "structural_engine", "ai_engine"],
        alias="ENABLED_ENGINES"
    )
    enable_ai_engine: bool = Field(True, alias="ENABLE_AI_ENGINE")

    @field_validator('enabled_engines')
    @classmethod
    def validate_engines(cls, v: List[str]) -> List[str]:
        valid_engines = {
            "wcag_deterministic", "contrast_engine", "structural_engine", 
            "ai_engine", "heuristic", "navigation", "form_engine"
        }
        invalid = [e for e in v if e not in valid_engines]
        if invalid:
            raise ValueError(f"Invalid engines configured: {invalid}")
        return v

    # Thresholds
    contrast_thresholds: dict = Field(
        default_factory=lambda: {
            "body_text": 4.5,
            "large_text": 3.0,
            "ui_component": 3.0,
            "graphical_object": 3.0
        },
        alias="CONTRAST_THRESHOLDS"
    )

    @field_validator('contrast_thresholds')
    @classmethod
    def validate_thresholds(cls, v: dict) -> dict:
        for k, val in v.items():
            if not isinstance(val, (int, float)) or not (1.0 <= val <= 21.0):
                raise ValueError(f"Contrast threshold for {k} must be between 1.0 and 21.0")
        return v

    # Confidence Weights
    confidence_weights: dict = Field(
        default_factory=lambda: {
            "contrast": {
                "detection_reliability": 0.98,
                "context_clarity": 0.95,
                "pattern_match": 0.9,
                "evidence_quality": 1.0
            },
            "structural": {
                "detection_reliability": 0.9,
                "context_clarity": 0.85,
                "pattern_match": 0.9,
                "evidence_quality": 0.85
            },
            "navigation": {
                "detection_reliability": 0.95,
                "context_clarity": 0.9,
                "pattern_match": 0.95,
                "evidence_quality": 0.9
            }
        },
        alias="CONFIDENCE_WEIGHTS"
    )

    # AI Model Settings
    llava_model_path: Path = Field(Path("./models/llava"), alias="LLAVA_MODEL_PATH")
    mistral_model_path: Path = Field(Path("./models/mistral-7b"), alias="MISTRAL_MODEL_PATH")
    ai_use_local: bool = Field(True, alias="AI_USE_LOCAL")
    ai_confidence_threshold: float = Field(0.7, alias="AI_CONFIDENCE_THRESHOLD")
    ai_max_retries: int = Field(3, alias="AI_MAX_RETRIES")
    ai_retry_delay: float = Field(1.0, alias="AI_RETRY_DELAY")
    ai_default_score: int = Field(85, alias="AI_DEFAULT_SCORE")

    # AI Endpoints
    llava_endpoint: str = Field("http://localhost:8001", alias="LLAVA_ENDPOINT")
    mistral_endpoint: str = Field("http://localhost:8002", alias="MISTRAL_ENDPOINT")

    # Engine Heuristics
    hover_simulation_delay: int = Field(100, alias="HOVER_SIMULATION_DELAY")
    density_threshold: float = Field(20.0, alias="DENSITY_THRESHOLD")
    max_focusable_elements: int = Field(10, alias="MAX_FOCUSABLE_ELEMENTS")

    # Database
    database_url: str = Field("sqlite:///./accesslens.db", alias="DATABASE_URL")

    @field_validator('database_url')
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if v.startswith(("postgresql://", "postgres://", "postgresql+asyncpg://")):
            raise ValueError(
                "PostgreSQL DATABASE_URL detected. This application uses SQLite only. "
                "Set DATABASE_URL=sqlite:///./accesslens.db in your .env file."
            )
        return v

    # Redis (optional — leave unset or set to None to disable)
    redis_url: Optional[str] = Field(None, alias="REDIS_URL")

    # Storage
    storage_path: Path = Field(Path("./data"), alias="STORAGE_PATH")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_file: Optional[Path] = Field(None, alias="LOG_FILE")
    json_logs: bool = Field(True, alias="JSON_LOGS")

    # Security
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()

import sys
if "pytest" in sys.modules or (len(sys.argv) > 0 and "pytest" in sys.argv[0]):
    settings.testing = True


settings.llava_model_path.parent.mkdir(parents=True, exist_ok=True)
settings.mistral_model_path.parent.mkdir(parents=True, exist_ok=True)
settings.storage_path.mkdir(parents=True, exist_ok=True)