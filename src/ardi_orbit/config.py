"""Configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the orbit agent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    # LLM models (litellm-style names: <provider>/<model>)
    solver_model: str = Field(
        default="openai/mimo-v2.5-reasoner",
        alias="ARDI_ORBIT_SOLVER_MODEL",
    )
    strategy_model: str = Field(
        default="openai/mimo-v2.5-flash",
        alias="ARDI_ORBIT_STRATEGY_MODEL",
    )

    # MiMo OpenAI-compatible endpoint (litellm reads OPENAI_API_KEY/_BASE per call)
    mimo_api_key: str | None = Field(default=None, alias="MIMO_API_KEY")
    mimo_api_base: str = Field(
        default="https://platform.xiaomimimo.com/v1",
        alias="MIMO_API_BASE",
    )

    # Binaries
    ardi_agent_bin: str = Field(default="ardi-agent", alias="ARDI_AGENT_BIN")
    awp_wallet_bin: str = Field(default="awp-wallet", alias="AWP_WALLET_BIN")

    # Behavior
    min_confidence: float = Field(default=0.75, alias="ARDI_ORBIT_MIN_CONFIDENCE", ge=0, le=1)
    max_commits_per_epoch: int = Field(
        default=5, alias="ARDI_ORBIT_MAX_COMMITS_PER_EPOCH", ge=1, le=15
    )
    dry_run: bool = Field(default=True, alias="ARDI_ORBIT_DRY_RUN")
    log_level: str = Field(default="INFO", alias="ARDI_ORBIT_LOG_LEVEL")
    state_dir: Path = Field(
        default=Path("~/.ardi-orbit").expanduser(),
        alias="ARDI_ORBIT_STATE_DIR",
    )

    def expanded_state_dir(self) -> Path:
        """Return state dir with ~ expanded; create if missing."""
        path = Path(str(self.state_dir)).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path


def load_settings() -> Settings:
    """Load settings from env (and .env if present)."""
    return Settings()
