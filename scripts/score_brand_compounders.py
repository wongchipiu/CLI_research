"""Score emerging consumer brands from a dated, auditable metric snapshot.

This is a screening model, not a valuation model. It intentionally keeps the
subjective brand-evidence grade visible in the input instead of hiding it in a
black-box factor.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_DIR / "config" / "brand_compounders.json"
sys.path.insert(0, str(PROJECT_DIR / "src"))

from quant.research.brand_compounders import rank


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    result = rank(json.loads(args.input.read_text(encoding="utf-8")))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.compact:
        result = {
            "as_of": result["as_of"],
            "model": result["model"],
            "ranked": [
                {
                    "rank": item["rank"],
                    "symbol": item["symbol"],
                    "score": item["score"],
                    "market_stage": item["market_stage"],
                }
                for item in result["ranked"]
            ],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
