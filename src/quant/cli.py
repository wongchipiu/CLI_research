"""Unified deterministic entry point for the cross-project research workflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from quant.adapters import IntegrationError
from quant.contracts import ContractError
from quant.services.workflow import WorkflowError, WorkflowRequest, run_workflow
from quant.workspace import DEFAULT_CONFIG, WorkspaceConfig, WorkspaceConfigError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant")
    subparsers = parser.add_subparsers(dest="command", required=True)
    workflow = subparsers.add_parser("workflow", help="quality summary -> study -> gpt_quant validation")
    workflow.add_argument("--workspace", type=Path, default=DEFAULT_CONFIG)
    workflow.add_argument("--strategy", required=True)
    workflow.add_argument("--market", required=True, choices=("cn", "us"))
    workflow.add_argument("--universe")
    workflow.add_argument("--membership-file")
    workflow.add_argument("--start")
    workflow.add_argument("--end")
    workflow.add_argument("--study-file", required=True)
    workflow.add_argument("--train-ratio", type=float, default=0.6)
    workflow.add_argument("--validation-ratio", type=float, default=0.2)
    workflow.add_argument("--train-end")
    workflow.add_argument("--final-start")
    workflow.add_argument("--walk-forward", action="store_true")
    workflow.add_argument("--wf-train-days", type=int, default=756)
    workflow.add_argument("--wf-test-days", type=int, default=126)
    workflow.add_argument("--max-position-weight", type=float, default=1.0)
    workflow.add_argument("--max-gross-exposure", type=float, default=1.0)
    workflow.add_argument("--target-volatility", type=float)
    workflow.add_argument("--volatility-window", type=int, default=20)
    workflow.add_argument("--regime-window", type=int)
    workflow.add_argument("--risk-off-exposure", type=float, default=0.0)
    workflow.add_argument("-p", "--param", action="append", default=[])
    args = parser.parse_args(argv)

    try:
        config = WorkspaceConfig.load(args.workspace)
        output = run_workflow(
            WorkflowRequest(
                strategy=args.strategy,
                market=args.market,
                params=tuple(args.param),
                study_file=args.study_file,
                universe=args.universe,
                membership_file=args.membership_file,
                start=args.start,
                end=args.end,
                train_ratio=args.train_ratio,
                validation_ratio=args.validation_ratio,
                train_end=args.train_end,
                final_start=args.final_start,
                walk_forward=args.walk_forward,
                wf_train_days=args.wf_train_days,
                wf_test_days=args.wf_test_days,
                max_position_weight=args.max_position_weight,
                max_gross_exposure=args.max_gross_exposure,
                target_volatility=args.target_volatility,
                volatility_window=args.volatility_window,
                regime_window=args.regime_window,
                risk_off_exposure=args.risk_off_exposure,
            ),
            config,
        )
    except (WorkspaceConfigError, WorkflowError, ContractError, IntegrationError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if output["decision"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
