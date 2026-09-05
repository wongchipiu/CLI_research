"""Aggregate compact backtest summaries and write a monthly review."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.backtest.report import RESULTS_DIR
from quant.backtest.summary import collect_results, render_monthly_review


PROJECT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default=date.today().strftime("%Y-%m"))
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR)
    args = parser.parse_args()

    frame = collect_results(args.results_dir)
    args.results_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.results_dir / "summary.csv"
    frame.to_csv(summary_path, index=False, encoding="utf-8")

    review_dir = PROJECT_DIR / "docs" / "monthly_review"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / f"{args.month}.md"
    review_path.write_text(render_monthly_review(frame, args.month), encoding="utf-8")
    print(
        json.dumps(
            {
                "results": len(frame),
                "oos_validated": int(frame["oos_validated"].sum()) if not frame.empty else 0,
                "summary": str(summary_path),
                "monthly_review": str(review_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
