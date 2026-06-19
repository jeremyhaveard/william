"""Loads and exposes the govcon search configuration."""
import os
import yaml

_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "search_config.yaml")


def load_config() -> dict:
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def enabled_sources() -> dict[str, dict]:
    """Return only sources with enabled: true."""
    cfg = load_config()
    return {k: v for k, v in cfg.get("sources", {}).items() if v.get("enabled", False)}


def is_enabled(source: str) -> bool:
    return source in enabled_sources()


def enabled_by_platform(platform: str) -> list[dict]:
    """Return list of enabled source configs for a given platform."""
    return [v for v in enabled_sources().values() if v.get("platform") == platform]
