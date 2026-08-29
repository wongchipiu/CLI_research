"""Write human-readable and JSON daily-bar quality summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.data import storage
from quant.data.quality import analyze_daily


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="只打印汇总，完整明细仍写入文件")
    args = parser.parse_args()
    daily_dir = storage.DATA_DIR / "daily"
    if not daily_dir.exists():
        print("无数据，请先运行 scripts/update_data.py")
        raise SystemExit(1)

    reports = []
    for market_dir in sorted(daily_dir.iterdir()):
        for path in sorted(market_dir.glob("*.parquet")):
            reports.append(analyze_daily(market_dir.name, path.stem, storage.load_daily(market_dir.name, path.stem)))

    text = "\n".join(report.to_text() for report in reports)
    if not args.quiet:
        print(text)
    text_path = storage.DATA_DIR / "quality_summary.txt"
    json_path = storage.DATA_DIR / "quality_summary.json"
    text_path.write_text(text, encoding="utf-8")
    payload = {
        "summary": {
            "symbols": len(reports),
            "ok": sum(report.status == "OK" for report in reports),
            "warnings": sum(report.status == "WARN" for report in reports),
            "errors": sum(report.status == "ERROR" for report in reports),
        },
        "reports": [report.to_dict() for report in reports],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**payload["summary"], "text": str(text_path), "json": str(json_path)}, ensure_ascii=False))
    if payload["summary"]["errors"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
