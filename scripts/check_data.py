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
from quant.workspace import WorkspaceConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="只打印汇总，完整明细仍写入文件")
    parser.add_argument("--market", choices=["cn", "us"])
    parser.add_argument("--workspace", type=Path, help="versioned workspace YAML; paths are cwd-independent")
    parser.add_argument("--allow-errors", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.workspace:
        WorkspaceConfig.load(args.workspace).apply()
    daily_dir = storage.DATA_DIR / "daily"
    if not daily_dir.exists():
        print("无数据，请先运行 scripts/update_data.py")
        raise SystemExit(1)

    reports = []
    included_markets = {args.market, "cn-index"} if args.market == "cn" else {args.market} if args.market else None
    for market_dir in sorted(daily_dir.iterdir()):
        if included_markets is not None and market_dir.name not in included_markets:
            continue
        for path in sorted(market_dir.glob("*.parquet")):
            reports.append(analyze_daily(market_dir.name, path.stem, storage.load_daily(market_dir.name, path.stem)))

    text = "\n".join(report.to_text() for report in reports)
    if not args.quiet:
        print(text)
    suffix = f"_{args.market}" if args.market else ""
    text_path = storage.DATA_DIR / f"quality_summary{suffix}.txt"
    json_path = storage.DATA_DIR / f"quality_summary{suffix}.json"
    text_path.write_text(text, encoding="utf-8")
    payload = {
        "schema_version": 1,
        "artifact_type": "data_quality_summary",
        "market": args.market or "all",
        "summary": {
            "symbols": len(reports),
            "ok": sum(report.status == "OK" for report in reports),
            "warnings": sum(report.status == "WARN" for report in reports),
            "errors": sum(report.status == "ERROR" for report in reports),
        },
        "reports": [report.to_dict() for report in reports],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "schema_version": payload["schema_version"],
        "artifact_type": payload["artifact_type"],
        "market": payload["market"],
        "summary": payload["summary"],
        "text_path": str(text_path.resolve()),
        "json_path": str(json_path.resolve()),
    }, ensure_ascii=False))
    if payload["summary"]["errors"] and not args.allow_errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
