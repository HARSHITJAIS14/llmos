"""Config: ~/.lsfg/config.toml + env + ~/.lsfg/.env, with a default for every key (§17.3)."""
from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path

HOME = Path(os.environ.get("LSFG_HOME", Path.home() / ".lsfg"))
CONFIG_PATH = HOME / "config.toml"
ENV_PATH = HOME / ".env"
CACHE_DIR = HOME / "cache"
TRACE_DIR = HOME / "traces"
RUN_DIR = HOME / "run"
DB_PATH = HOME / "lsfg.db"
SOCKET_PATH = RUN_DIR / "lsfg.sock"


@dataclass
class PlannerCfg:
    model: str = "claude-opus-5-5"
    effort: str = "low"
    replan_effort: str = "medium"
    fast: bool = False
    schema: str = "flat"             # "anyof" is more exact but the API rejects it: "compiled grammar is too large"
    fallback_model: str = ""
    timeout_s: float = 30.0
    max_tokens: int = 4000


@dataclass
class JevCfg:
    model: str = "jev-latest"
    url: str = "https://api.typesafe.ai/v1/systemone"
    timeout_s: float = 3.0
    tau_safe: float = 0.60
    tau_irreversible: float = 0.85
    margin: float = 0.15
    max_candidates: int = 200
    keep_top: int = 60


@dataclass
class BudgetCfg:
    task_s: float = 120.0
    steps: int = 40
    opus_calls: int = 3
    jev_calls: int = 30
    explore_actions: int = 8
    step_timeout_s: float = 6.0
    open_app_timeout_s: float = 15.0
    open_url_timeout_s: float = 12.0
    explore_timeout_s: float = 20.0
    resolve_timeout_s: float = 4.0


@dataclass
class ConfirmCfg:
    irreversible: bool = True
    auto_when_explicit: bool = False


@dataclass
class PrivacyCfg:
    mask_content: bool = False
    extra_denylist: list[str] = field(default_factory=list)


@dataclass
class TraceCfg:
    store_ui_text: bool = True
    keep_runs: int = 200


@dataclass
class UrlCfg:
    allowed_schemes: list[str] = field(
        default_factory=lambda: ["http", "https", "x-apple.systempreferences", "mailto"])


@dataclass
class Config:
    planner: PlannerCfg = field(default_factory=PlannerCfg)
    jev: JevCfg = field(default_factory=JevCfg)
    budgets: BudgetCfg = field(default_factory=BudgetCfg)
    confirm: ConfirmCfg = field(default_factory=ConfirmCfg)
    privacy: PrivacyCfg = field(default_factory=PrivacyCfg)
    trace: TraceCfg = field(default_factory=TraceCfg)
    urls: UrlCfg = field(default_factory=UrlCfg)
    typesafe_api_key: str = ""
    anthropic_api_key: str = ""
    env_file_mode_ok: bool = True


def _apply(section, values: dict) -> None:
    for f in fields(section):
        if f.name in values:
            setattr(section, f.name, values[f.name])


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def load_config(path: Path | None = None) -> Config:
    cfg = Config()
    path = path or CONFIG_PATH
    if path.exists():
        data = tomllib.loads(path.read_text())
        for f in fields(cfg):
            section = getattr(cfg, f.name)
            if is_dataclass(section) and isinstance(data.get(f.name), dict):
                _apply(section, data[f.name])
    env_file = _read_env_file(ENV_PATH) if ENV_PATH.exists() else {}
    if ENV_PATH.exists():
        mode = stat.S_IMODE(ENV_PATH.stat().st_mode)
        cfg.env_file_mode_ok = (mode & 0o077) == 0
    cfg.typesafe_api_key = os.environ.get("TYPESAFE_API_KEY") or env_file.get("TYPESAFE_API_KEY", "")
    cfg.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY") or env_file.get("ANTHROPIC_API_KEY", "")
    return cfg


def ensure_dirs() -> None:
    for d in (HOME, CACHE_DIR, TRACE_DIR, RUN_DIR):
        d.mkdir(parents=True, exist_ok=True)
