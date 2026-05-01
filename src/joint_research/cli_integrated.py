"""Integrated ``joint-research`` CLI entrypoint extensions.

This module keeps the existing CLI commands from :mod:`joint_research.cli` and replaces
only the wallet-flow research command with the Phase 4.10 diagnostic-report option.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import typer

from joint_research.cli import _resolve_paths, app, research_app

__all__ = ["app"]


def _replace_research_command(command_name: str) -> None:
    """Remove an existing Typer command registration by name before overriding it."""

    research_typer = cast(Any, research_app)
    research_typer.registered_commands = [
        command
        for command in research_typer.registered_commands
        if getattr(command, "name", None) != command_name
    ]


_replace_research_command("wallet-flow-signal")


@research_app.command("wallet-flow-signal")
def research_wallet_flow_signal(
    min_segment_samples: int = typer.Option(
        24,
        help="Minimum sample count for segmented wallet-flow analysis.",
    ),
    min_feature_samples: int = typer.Option(
        36,
        help="Minimum sample count for all-sample feature rows.",
    ),
    train_fraction: float = typer.Option(0.6, help="Temporal train split fraction."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_signal_summary.md, wallet_flow_signal_results.csv, "
            "wallet_flow_signal_candidates.json, and optional diagnostic triage output."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N wallet-flow candidates."),
    diagnostic_report: bool = typer.Option(
        False,
        "--diagnostic-report",
        help="Also write wallet_flow_diagnostic_triage.md from rejection diagnostics.",
    ),
    diagnostic_near_miss_limit: int = typer.Option(
        10,
        "--diagnostic-near-miss-limit",
        help="Maximum near-miss rows to include in the diagnostic triage report.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run wallet-flow-conditioned Polymarket -> crypto signal analysis."""

    from joint_research.research.wallet_flow_diagnostic_triage import (  # noqa: PLC0415
        read_wallet_flow_rejection_diagnostics,
        write_wallet_flow_diagnostic_triage_report,
    )
    from joint_research.research.wallet_flow_signal import (  # noqa: PLC0415
        WalletFlowCandidateGrade,
        run_wallet_flow_signal_study_with_details,
        write_wallet_flow_signal_report,
    )

    paths = _resolve_paths(warehouse_root)
    study_details = run_wallet_flow_signal_study_with_details(
        paths=paths,
        min_segment_samples=min_segment_samples,
        min_feature_samples=min_feature_samples,
        train_fraction=train_fraction,
    )
    results = study_details.results
    resolved_output_dir = output_dir.resolve()
    report_paths = write_wallet_flow_signal_report(
        output_dir=resolved_output_dir,
        results=results,
        study_details=study_details,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in WalletFlowCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"segment_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    if diagnostic_report:
        diagnostics = read_wallet_flow_rejection_diagnostics(report_paths.rejection_diagnostics_csv)
        triage_path = write_wallet_flow_diagnostic_triage_report(
            output_dir=resolved_output_dir,
            diagnostics=diagnostics,
            near_miss_limit=diagnostic_near_miss_limit,
        )
        typer.echo("No promotion thresholds were changed.")
        typer.echo("This report explains rejection causes; it does not approve candidates.")
        typer.echo(f"diagnostic_triage={triage_path}")

    candidates = [r for r in results if r.grade is not WalletFlowCandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no wallet-flow candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} wallet-flow candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"feature={result.feature_name} "
            f"segment={result.segment_type}:{result.segment_value} "
            f"improvement={result.test_improvement_over_baseline:+.5f} "
            f"win_rate={result.test_win_rate:.2f} "
            f"market={result.market_slug or result.market_id}"
        )
