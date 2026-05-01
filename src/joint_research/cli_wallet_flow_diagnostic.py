"""Wallet-flow diagnostic triage command entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer

from joint_research.research.wallet_flow_diagnostic_triage import (
    read_wallet_flow_rejection_diagnostics,
    write_wallet_flow_diagnostic_triage_report,
)

app = typer.Typer(add_completion=False)


@app.command()
def main(
    diagnostics_csv: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal/wallet_flow_rejection_diagnostics.csv"),
        help="Input wallet-flow rejection diagnostics CSV.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_diagnostic_triage.md.",
    ),
    near_miss_limit: int = typer.Option(10, help="Maximum near-miss rows in the report."),
) -> None:
    diagnostics = read_wallet_flow_rejection_diagnostics(diagnostics_csv)
    report_path = write_wallet_flow_diagnostic_triage_report(
        output_dir=output_dir.resolve(),
        diagnostics=diagnostics,
        near_miss_limit=near_miss_limit,
    )
    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo("No promotion thresholds were changed.")
    typer.echo("This report explains rejection causes; it does not approve candidates.")
    typer.echo(f"diagnostics={len(diagnostics)}")
    typer.echo(f"triage_report={report_path}")


if __name__ == "__main__":
    app()
