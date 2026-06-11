"""股票池配置：config/universe.yaml"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "universe.yaml"


def load_universe() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg.setdefault("cn", [])
    cfg.setdefault("us", [])
    cfg.setdefault("cn_index", [])
    # YAML 里 "600519" 若未加引号会被解析成 int，统一转回字符串并补零
    cfg["cn"] = [str(s).zfill(6) for s in cfg["cn"]]
    cfg["cn_index"] = [str(s).zfill(6) for s in cfg["cn_index"]]
    cfg["us"] = [str(s).upper() for s in cfg["us"]]
    return cfg
