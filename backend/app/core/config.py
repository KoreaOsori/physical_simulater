"""Application settings, sourced from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path (not relative ".env") so this resolves the same way
# regardless of the process's cwd — matches how the data accessors
# (e.g. app/data/human_data.py) always anchor paths off __file__ rather
# than trusting cwd, since that differs between native dev (`cd backend`)
# and the Docker image (WORKDIR /app, same directory the volume mounts
# backend/ onto, but not guaranteed to stay that way).
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "physical-simulater-backend"
    # Human macro connectome chat panel (docs/30) — DB-grounded RAG only,
    # gpt-5-mini via OpenAI's Responses API. Empty string (not None) so a
    # missing key fails loudly with a clear "not configured" response
    # instead of a confusing attribute error deep in the OpenAI client.
    openai_api_key: str = ""
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    # Species selection turned out not to need a config switch: each species
    # gets its own route namespace instead (/api/... for C. elegans,
    # /api/fly/... for Drosophila — see app/api/routes/fly.py), so both can be
    # loaded and queried at once rather than one active organism at a time.

    # "hodgkin_huxley" runs the real Brian2 network simulation (app/simulation/
    # hh_model.py) against the imported connectome; "rule_based" uses the
    # single-edge placeholder narration (app/simulation/engine.py). HH is the
    # v1 target fidelity, but takes a few seconds per command (see hh_model.py).
    simulation_engine: str = "hodgkin_huxley"

    # Same switch for the Drosophila v2 olfactory-circuit subset (app/simulation/
    # fly_hh_model.py / fly_engine.py). HH is ~15s/command at this network's
    # scale (2,452 neurons / 139,496 synapses) — see fly_hh_model.py's
    # docstring for the measured cost.
    fly_simulation_engine: str = "hodgkin_huxley"


@lru_cache
def get_settings() -> Settings:
    return Settings()
