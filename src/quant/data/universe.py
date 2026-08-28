"""股票池配置：config/universe.yaml"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "universe.yaml"


def list_universe_profiles() -> list[str]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return sorted(cfg.get("profiles", {"default": cfg}))


def load_universe(profile: str | None = None) -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        root = yaml.safe_load(f)
    profiles = root.get("profiles")
    if profiles:
        active = profile or root.get("default_profile", "baseline")
        if active not in profiles:
            raise KeyError(f"未知股票池 {active!r}，可选: {sorted(profiles)}")
        cfg = dict(profiles[active])
        cfg["profile"] = active
        cfg["as_of"] = root.get("as_of")
    else:
        cfg = dict(root)
        cfg["profile"] = profile or "default"
    cfg.setdefault("cn", [])
    cfg.setdefault("us", [])
    cfg.setdefault("cn_index", [])
    # YAML 里 "600519" 若未加引号会被解析成 int，统一转回字符串并补零
    cfg["cn"] = [str(s).zfill(6) for s in cfg["cn"]]
    cfg["cn_index"] = [str(s).zfill(6) for s in cfg["cn_index"]]
    cfg["us"] = [str(s).upper() for s in cfg["us"]]
    cfg.setdefault("point_in_time", False)
    cfg.setdefault("survivorship_bias", "not documented")
    return cfg
