"""Generate a launchd plist without loading or changing macOS services."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant.live_risk.launchd import render_launchd_plist


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--label", default="com.quant.live-risk-paper")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    payload = render_launchd_plist(
        root,
        args.config,
        python_path=args.python,
        label=args.label,
    )
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
        print(output)
    else:
        sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
