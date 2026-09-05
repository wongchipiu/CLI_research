import json

from quant.backtest.summary import collect_results, render_monthly_review


def test_summary_prioritizes_oos_and_excludes_full_sample_from_candidates(tmp_path):
    full_dir = tmp_path / "full"
    full_dir.mkdir()
    (full_dir / "metrics.json").write_text(
        json.dumps({"strategy": "full", "market": "us", "sharpe": 9.0, "cagr": 1.0}),
        encoding="utf-8",
    )
    oos_dir = tmp_path / "oos"
    oos_dir.mkdir()
    (oos_dir / "metrics.json").write_text(
        json.dumps(
            {
                "strategy": "holdout",
                "market": "us",
                "universe_point_in_time": True,
                "params": {"lookback": 60},
                "validation": {
                    "out_of_sample": {
                        "start": "2023-01-01",
                        "end": "2025-01-01",
                        "n_days": 500,
                        "total_return": 0.2,
                        "cagr": 0.1,
                        "sharpe": 1.2,
                        "max_drawdown": -0.1,
                        "calmar": 1.0,
                        "completed_trades": 55,
                        "excess_cagr": 0.03,
                    },
                    "stability": {"passed": True},
                    "parameter_robustness": {"passed": True},
                    "walk_forward": {"passed": True},
                },
            }
        ),
        encoding="utf-8",
    )

    frame = collect_results(tmp_path)
    review = render_monthly_review(frame, "2026-07")

    assert list(frame["strategy"]) == ["holdout", "full"]
    assert "| 1 | holdout |" not in review
    assert "| 2 | full |" not in review
    assert "旧口径/探索/示例/未完成最终测试，不可准入：2 组" in review
