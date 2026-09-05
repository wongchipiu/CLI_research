"""Migrate legacy daily files to normalized share-volume and provenance schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.data import storage


def main() -> None:
    daily_dir = storage.DATA_DIR / "daily"
    migrated = 0
    if daily_dir.exists():
        for market_dir in sorted(daily_dir.iterdir()):
            for path in sorted(market_dir.glob("*.parquet")):
                frame = storage.load_daily(market_dir.name, path.stem)
                if frame is None:
                    continue
                storage.save_daily(market_dir.name, path.stem, frame)
                migrated += 1
    print(json.dumps({"migrated_files": migrated, "volume_unit": "share"}, indent=2))


if __name__ == "__main__":
    main()
