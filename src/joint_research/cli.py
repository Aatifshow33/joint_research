"""``joint-research`` CLI entrypoint."""

from __future__ import annotations

import asyncio
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import typer

from joint_research.research.wallet_flow_backfill_priority import (
    WalletFlowBackfillPriorityThresholds,
    write_wallet_flow_backfill_priority_artifacts,
)
from joint_research.research.wallet_flow_backfill_batches import (
    write_wallet_flow_backfill_batches_artifacts,
)
from joint_research.warehouse import WarehousePaths

_DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS = WalletFlowBackfillPriorityThresholds()

app = typer.Typer(no_args_is_help=True, add_completion=False)
ingest_app = typer.Typer(no_args_is_help=True, help="Ingest data into the warehouse.")
research_app = typer.Typer(no_args_is_help=True, help="Run research analyses against the warehouse.")
app.add_typer(ingest_app, name="ingest")
app.add_typer(research_app, name="research")


def _resolve_paths(warehouse_root: Path | None) -> WarehousePaths:
    if warehouse_root is not None:
        return WarehousePaths(root=warehouse_root.resolve())
    return WarehousePaths.from_env()


def _parse_iso_or_relative_days(value: str) -> datetime:
    """Accept an ISO-8601 datetime, an ISO date, or ``-Nd`` for "N days ago"."""

    if value.startswith("-") and value.endswith("d"):
        try:
            days = int(value[1:-1])
        except ValueError as exc:
            raise typer.BadParameter(f"invalid relative form: {value}") from exc
        return datetime.now(tz=timezone.utc) - timedelta(days=days)
    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise typer.BadParameter(f"unparseable timestamp: {value}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@ingest_app.command("gamma-events")
def ingest_gamma_events(
    limit: int = typer.Option(500, help="Number of events to fetch in this run."),
    active: bool = typer.Option(True, help="Filter to currently-active events."),
    closed: bool = typer.Option(False, help="Include closed events."),
    archived: bool = typer.Option(False, help="Include archived events."),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Polymarket /events from the Gamma API and append a Parquet shard."""

    from joint_research.ingest.polymarket_runner import ingest_gamma_events as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(paths=paths, limit=limit, active=active, closed=closed, archived=archived)
    )
    if result.rows_written == 0:
        typer.echo("ingested=0 rows. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} shard={result.shard_path}")


@ingest_app.command("crypto-ohlcv")
def ingest_crypto_ohlcv(
    symbol: str = typer.Option(..., help="Binance symbol, e.g. BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT."),
    interval: str = typer.Option("1h", help="Kline interval: 1m/5m/15m/1h/4h/1d/etc."),
    start: str = typer.Option("-30d", help="Start time. ISO-8601 or '-Nd' for N days ago."),
    end: str = typer.Option(
        None,
        help="End time. ISO-8601 or '-Nd'. Defaults to 'now' (UTC).",
    ),
    warehouse_root: Path = typer.Option(
        None,
        help="Override warehouse root. Defaults to $JOINT_RESEARCH_WAREHOUSE_ROOT or ./data/warehouse.",
    ),
) -> None:
    """Pull Binance klines for [start, end) and append a Parquet shard."""

    from joint_research.ingest.crypto_runner import ingest_binance_ohlcv as run  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    start_dt = _parse_iso_or_relative_days(start)
    end_dt = (
        _parse_iso_or_relative_days(end)
        if end is not None
        else datetime.now(tz=timezone.utc)
    )

    result = asyncio.run(
        run(
            paths=paths,
            symbol=symbol,
            interval=interval,
            start=start_dt,
            end=end_dt,
        )
    )
    if result.rows_written == 0:
        typer.echo(
            f"ingested=0 symbol={result.symbol} interval={result.interval} "
            f"window={result.start_iso}..{result.end_iso}. nothing written."
        )
        raise typer.Exit(code=0)
    typer.echo(
        f"ingested={result.rows_written} symbol={result.symbol} interval={result.interval} "
        f"window={result.start_iso}..{result.end_iso} shard={result.shard_path}"
    )


@ingest_app.command("crypto-derivatives")
def ingest_crypto_derivatives(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated Binance symbols.",
    ),
    limit: int = typer.Option(24, help="Funding rows per symbol."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull public/no-auth funding and perp-basis inputs into the warehouse."""

    from joint_research.ingest.crypto_derivatives import fetch_derivatives_rows  # noqa: PLC0415
    from joint_research.warehouse import CRYPTO_DERIVATIVES, ParquetWriter  # noqa: PLC0415

    paths = _resolve_paths(warehouse_root)
    symbol_list = tuple(s.strip().upper() for s in symbols.split(",") if s.strip())
    result = asyncio.run(fetch_derivatives_rows(symbols=symbol_list, limit=limit))
    if not result.rows:
        typer.echo(
            f"ingested=0 symbols={','.join(symbol_list)} errors={len(result.errors)}. "
            "nothing written."
        )
        for attempt in result.source_attempts:
            detail_suffix = f" detail={attempt.detail}" if attempt.detail else ""
            typer.echo(
                f"  source={attempt.source} symbol={attempt.symbol} type={attempt.record_type} "
                f"status={attempt.status} rows={attempt.rows}{detail_suffix}"
            )
        for error in result.errors:
            typer.echo(f"  warning={error}")
        raise typer.Exit(code=0)
    shard = ParquetWriter(table=CRYPTO_DERIVATIVES, paths=paths).write(
        [row.to_warehouse_row() for row in result.rows]
    )
    typer.echo(
        f"ingested={len(result.rows)} symbols={','.join(symbol_list)} "
        f"errors={len(result.errors)} shard={shard}"
    )
    for attempt in result.source_attempts:
        detail_suffix = f" detail={attempt.detail}" if attempt.detail else ""
        typer.echo(
            f"  source={attempt.source} symbol={attempt.symbol} type={attempt.record_type} "
            f"status={attempt.status} rows={attempt.rows}{detail_suffix}"
        )
    for error in result.errors:
        typer.echo(f"  warning={error}")


@ingest_app.command("gamma-crypto-markets")
def ingest_gamma_crypto_markets(
    limit: int = typer.Option(500, help="Max markets to fetch from Gamma."),
    active: bool = typer.Option(True, help="Only currently-active markets."),
    closed: bool = typer.Option(False, help="Include closed markets."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull crypto-tagged Polymarket markets (tag_id=21) into the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_gamma_crypto_markets as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit, active=active, closed=closed))
    if result.rows_written == 0:
        typer.echo("ingested=0 markets. nothing written.")
        raise typer.Exit(code=0)
    typer.echo(f"ingested={result.rows_written} markets shard={result.shard_path}")


@ingest_app.command("polymarket-prices")
def ingest_polymarket_prices(
    top_n: int = typer.Option(10, help="Backfill the top-N crypto markets by 1mo volume."),
    interval: str = typer.Option("1m", help="Polymarket history interval: 1h/6h/1d/1w/1m/max."),
    fidelity_minutes: int = typer.Option(60, help="Bucket size in minutes (60 = hourly)."),
    include_closed: bool = typer.Option(
        False,
        "--include-closed/--active-only",
        help="Include closed/resolved markets — required for survivorship-bias-free analysis.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull /prices-history for top-N crypto YES tokens already in the warehouse."""

    from joint_research.ingest.polymarket_history_runner import (  # noqa: PLC0415
        ingest_top_crypto_market_prices as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(
            paths=paths,
            top_n=top_n,
            interval=interval,
            fidelity_minutes=fidelity_minutes,
            include_closed=include_closed,
        )
    )
    typer.echo(
        f"tokens_attempted={result.tokens_attempted} "
        f"tokens_with_data={result.tokens_with_data} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@research_app.command("lead-lag")
def research_lead_lag(
    min_observations: int = typer.Option(30, help="Skip tokens with fewer aligned bars than this."),
    frequency: str = typer.Option(
        "hourly",
        help="Sampling frequency: 'hourly' (lags 0/1/4/24 h) or 'daily' (lags 0/1/3/7/14 d).",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/lead_lag"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for lead_lag_summary.md, lead_lag_results.csv, "
            "and lead_lag_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N candidates by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the exploratory Polymarket→crypto lead-lag report."""

    from joint_research.research.lead_lag import (  # noqa: PLC0415
        rank_signal_candidates,
        run_lead_lag_study,
        write_lead_lag_report,
    )

    paths = _resolve_paths(warehouse_root)
    token_results, bucket_results = run_lead_lag_study(
        paths=paths,
        min_observations_per_token=min_observations,
        frequency=frequency,
    )

    report_paths = write_lead_lag_report(
        output_dir=output_dir.resolve(),
        token_results=token_results,
        bucket_results=bucket_results,
    )

    markets_tested = len({(r.asset, r.market_id, r.token_id) for r in token_results})
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"markets_tested={markets_tested} "
        f"hypothesis_rows={len(token_results)} "
        f"bucket_cells={len(bucket_results)}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")
    if diagnostic_triage_md is not None:
        typer.echo(f"diagnostic_triage={diagnostic_triage_md}")
    if promotion_plan_md is not None:
        typer.echo(f"promotion_plan={promotion_plan_md}")

    if not token_results:
        typer.echo("no tokens met the min_observations threshold. backfill more data.")
        raise typer.Exit(code=0)

    sig = [b for b in bucket_results if b.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant bucket cells: {len(sig)}")
        for b in sig:
            typer.echo(
                f"  asset={b.asset} bucket={b.days_bucket} lag={b.lag_hours}h "
                f"r={b.pooled_correlation:+.3f} t={b.pooled_tstat:+.2f} "
                f"p={b.pooled_pvalue:.4f} n_obs={b.n_observations}"
            )
    else:
        typer.echo("no BH-significant bucket cells at alpha=0.05 (expected with limited data)")

    typer.echo(f"\ntop {show_top} exploratory candidates by |t|:")
    for c in rank_signal_candidates(token_results, limit=show_top):
        typer.echo(
            f"  rank={c.rank:>2} asset={c.asset:>4} lag={c.lag_hours:>2}h "
            f"r={c.correlation:+.3f} t={c.tstat:+.2f} p={c.pvalue_two_sided:.4f} "
            f"n={c.n} market={c.market_slug or c.market_id}"
        )


@research_app.command("robustness")
def research_robustness(
    min_observations: int = typer.Option(60, help="Minimum aligned bars per market/horizon."),
    min_nonzero_changes: int = typer.Option(
        20,
        help="Minimum non-zero Polymarket probability changes.",
    ),
    max_flat_fraction: float = typer.Option(
        0.90,
        help="Reject markets with a higher fraction of zero probability changes.",
    ),
    min_days_to_resolution: float = typer.Option(
        3.0,
        help="Reject markets whose last aligned sample is this close to resolution.",
    ),
    train_fraction: float = typer.Option(0.60, help="Earlier fraction used as train/discovery."),
    n_permutations: int = typer.Option(200, help="Deterministic shuffles per market/horizon."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/robustness"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for robustness_summary.md, robustness_results.csv, "
            "and robustness_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N robustness candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only robustness checks over Polymarket→crypto candidates."""

    from joint_research.research.robustness import (  # noqa: PLC0415
        CandidateGrade,
        run_robustness_study,
        write_robustness_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_robustness_study(
        paths=paths,
        min_observations=min_observations,
        min_nonzero_changes=min_nonzero_changes,
        max_flat_fraction=max_flat_fraction,
        min_days_to_resolution=min_days_to_resolution,
        train_fraction=train_fraction,
        n_permutations=n_permutations,
    )
    report_paths = write_robustness_report(
        output_dir=output_dir.resolve(),
        results=results,
    )

    counts = {grade.value: sum(1 for r in results if r.grade is grade) for grade in CandidateGrade}
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"hypothesis_rows={len(results)} "
        f"promising={counts['PROMISING']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [r for r in results if r.grade is not CandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no robustness candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} robustness candidates:")
    for r in candidates:
        oos_match = (
            r.train_correlation * r.test_correlation > 0
            if not (math.isnan(r.train_correlation) or math.isnan(r.test_correlation))
            else False
        )
        typer.echo(
            f"  rank={r.rank:>2} grade={r.grade.value:<9} asset={r.asset:>4} "
            f"lag={r.lag_hours:>2}h oos_match={oos_match} "
            f"emp_p={r.empirical_pvalue:.4f} stability={r.rolling_stability:.2f} "
            f"n={r.n_observations} market={r.market_slug or r.market_id}"
        )


@research_app.command("composite-signal")
def research_composite_signal(
    min_train_samples: int = typer.Option(30, help="Minimum train samples per rule."),
    min_test_samples: int = typer.Option(20, help="Minimum test samples per rule."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/composite_signal"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for composite_signal_summary.md, composite_signal_results.csv, "
            "and composite_signal_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N composite candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run deterministic composite signal scans over warehouse features."""

    from joint_research.research.composite_signal import (  # noqa: PLC0415
        CompositeCandidateGrade,
        run_composite_signal_study,
        write_composite_signal_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_composite_signal_study(
        paths=paths,
        min_train_samples=min_train_samples,
        min_test_samples=min_test_samples,
    )
    report_paths = write_composite_signal_report(
        output_dir=output_dir.resolve(),
        results=results,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in CompositeCandidateGrade
    }
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"rule_rows={len(results)} "
        f"simulation_ready={counts['SIMULATION_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"weak={counts['WEAK']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.grade is not CompositeCandidateGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no composite candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} composite candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"test_acc={result.test_accuracy:.2f} "
            f"test_avg={result.test_average_forward_return:+.5f} "
            f"rule={result.rule_family} market={result.market_slug or result.market_id}"
        )


@research_app.command("derivatives-regime")
def research_derivatives_regime(
    min_segment_samples: int = typer.Option(
        24,
        help="Minimum sample count for funding/basis segment analysis.",
    ),
    min_combined_samples: int = typer.Option(
        36,
        help="Minimum sample count for combined regime segments.",
    ),
    train_fraction: float = typer.Option(0.6, help="Temporal train split fraction."),
    output_dir: Path = typer.Option(
        Path("artifacts/research/derivatives_regime"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for derivatives_regime_summary.md, derivatives_regime_results.csv, "
            "and derivatives_regime_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N derivatives-regime candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run derivatives-regime-conditioned Polymarket -> crypto signal analysis."""

    from joint_research.research.derivatives_regime import (  # noqa: PLC0415
        RegimeCandidateGrade,
        run_derivatives_regime_study,
        write_derivatives_regime_report,
    )

    paths = _resolve_paths(warehouse_root)
    results = run_derivatives_regime_study(
        paths=paths,
        min_segment_samples=min_segment_samples,
        min_combined_samples=min_combined_samples,
        train_fraction=train_fraction,
    )
    report_paths = write_derivatives_regime_report(
        output_dir=output_dir.resolve(),
        results=results,
    )
    counts = {
        grade.value: sum(1 for result in results if result.grade is grade)
        for grade in RegimeCandidateGrade
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

    candidates = [r for r in results if r.grade is not RegimeCandidateGrade.REJECTED][:show_top]
    if not candidates:
        typer.echo("no regime candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} derivatives-regime candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.grade.value:<16} "
            f"asset={result.asset:>4} horizon={result.horizon_hours:>2}h "
            f"segment={result.segment_type}:{result.segment_value} "
            f"improvement={result.test_improvement_over_baseline:+.5f} "
            f"win_rate={result.test_win_rate:.2f} "
            f"market={result.market_slug or result.market_id}"
        )


@research_app.command("wallet-flow-coverage-gate")
def research_wallet_flow_coverage_gate(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/wallet_flow_signal"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_coverage_gate.md.",
    ),
    min_covered_markets: int = typer.Option(
        25,
        help="Minimum markets with wallet-flow rows required for PASS.",
    ),
    min_coverage_ratio: float = typer.Option(
        0.20,
        help="Minimum covered_markets / total_markets required for PASS.",
    ),
    min_total_wallet_flow_rows: int = typer.Option(
        1000,
        help="Minimum total wallet-flow rows required for PASS.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        500,
        help="Minimum market-flow hourly rows required for PASS.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        500,
        help="Minimum whale-flow hourly rows required for PASS.",
    ),
    show_top: int = typer.Option(10, help="Top covered markets to include in the report."),
) -> None:
    """Run a non-tradeable wallet-flow backfill coverage gate."""

    from joint_research.research.wallet_flow_coverage_gate import (  # noqa: PLC0415
        WalletFlowCoverageGateThresholds,
        write_wallet_flow_coverage_gate_report,
    )

    thresholds = WalletFlowCoverageGateThresholds(
        min_covered_markets=min_covered_markets,
        min_coverage_ratio=min_coverage_ratio,
        min_total_wallet_flow_rows=min_total_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, gate = write_wallet_flow_coverage_gate_report(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        top_limit=show_top,
    )

    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"gate_status={gate.status} "
        f"covered_markets={gate.covered_markets} "
        f"total_markets={gate.total_markets} "
        f"coverage_ratio={gate.coverage_ratio:.4f} "
        f"wallet_flow_rows={gate.total_wallet_flow_rows}"
    )
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"coverage_report={report_path}")
    if gate.failure_reasons:
        typer.echo("failure_reasons=" + ";".join(gate.failure_reasons))


@research_app.command("wallet-flow-backfill-priority")
def research_wallet_flow_backfill_priority(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_backfill_priority.md and wallet_flow_backfill_priority.csv.",
    ),
    min_wallet_flow_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_wallet_flow_rows,
        "--min-wallet-flow-rows",
        help="Minimum wallet-flow rows required per market before it is deprioritized.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_market_flow_hourly_rows,
        "--min-market-flow-hourly-rows",
        help="Minimum market-flow hourly rows required per market before it is deprioritized.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_whale_flow_hourly_rows,
        "--min-whale-flow-hourly-rows",
        help="Minimum whale-flow hourly rows required per market before it is deprioritized.",
    ),
    show_top: int = typer.Option(25, "--show-top", help="Top-N priorities to render."),
) -> None:
    """Rank wallet-flow data backfill priorities (non-tradeable)."""

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=min_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, csv_path, plan = write_wallet_flow_backfill_priority_artifacts(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        top_limit=show_top,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"backfill_markets={plan.backfill_markets}")
    typer.echo(f"active_backfill_markets={plan.active_backfill_markets}")
    typer.echo(f"total_markets={plan.total_markets}")
    typer.echo(f"priorities_rendered={len(plan.priorities)}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"priority_report={report_path}")
    typer.echo(f"priority_csv={csv_path}")


@research_app.command("wallet-flow-backfill-batches")
def research_wallet_flow_backfill_batches(
    coverage_csv: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan/wallet_flow_coverage.csv"),
        "--coverage-csv",
        help="Wallet-flow coverage CSV produced by the backfill planner.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help="Directory for wallet_flow_backfill_batches.md and wallet_flow_backfill_batches.csv.",
    ),
    min_wallet_flow_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_wallet_flow_rows,
        "--min-wallet-flow-rows",
        help="Minimum wallet-flow rows required per market before it is deprioritized.",
    ),
    min_market_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_market_flow_hourly_rows,
        "--min-market-flow-hourly-rows",
        help="Minimum market-flow hourly rows required per market before it is deprioritized.",
    ),
    min_whale_flow_hourly_rows: int = typer.Option(
        _DEFAULT_WALLET_FLOW_BACKFILL_PRIORITY_THRESHOLDS.min_whale_flow_hourly_rows,
        "--min-whale-flow-hourly-rows",
        help="Minimum whale-flow hourly rows required per market before it is deprioritized.",
    ),
    batch_size: int = typer.Option(25, "--batch-size", help="Markets per backfill batch."),
    max_batches: int = typer.Option(5, "--max-batches", help="Maximum number of batches to plan."),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Planning-only mode; this command never executes ingestion.",
    ),
) -> None:
    """Plan deterministic wallet-flow backfill batches (non-tradeable)."""

    thresholds = WalletFlowBackfillPriorityThresholds(
        min_wallet_flow_rows=min_wallet_flow_rows,
        min_market_flow_hourly_rows=min_market_flow_hourly_rows,
        min_whale_flow_hourly_rows=min_whale_flow_hourly_rows,
    )
    report_path, csv_path, plan = write_wallet_flow_backfill_batches_artifacts(
        coverage_csv=coverage_csv.resolve(),
        output_dir=output_dir.resolve(),
        thresholds=thresholds,
        batch_size=batch_size,
        max_batches=max_batches,
        dry_run=dry_run,
    )

    typer.echo("EXPLORATORY ONLY - NOT TRADEABLE")
    typer.echo(f"dry_run={dry_run}")
    typer.echo(f"batches={len(plan.batches)}")
    typer.echo(f"markets_planned={len(plan.rows)}")
    typer.echo(f"batch_size={batch_size}")
    typer.echo("No candidates promoted.")
    typer.echo("No threshold changes.")
    typer.echo("No live trading changes.")
    typer.echo(f"batch_report={report_path}")
    typer.echo(f"batch_csv={csv_path}")


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
            "and wallet_flow_signal_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N wallet-flow candidates."),
    diagnostic_report: bool = typer.Option(
        False,
        "--diagnostic-report/--no-diagnostic-report",
        help="Also write wallet_flow_diagnostic_triage.md from rejection diagnostics.",
    ),
    promotion_plan: bool = typer.Option(
        False,
        "--promotion-plan/--no-promotion-plan",
        help="Also write wallet_flow_promotion_plan.md as a non-tradeable data/action plan.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run wallet-flow-conditioned Polymarket -> crypto signal analysis."""

    from joint_research.research.wallet_flow_signal import (  # noqa: PLC0415
        WalletFlowCandidateGrade,
        build_wallet_flow_rejection_diagnostics,
        run_wallet_flow_signal_study_with_details,
        write_wallet_flow_signal_report,
    )
    from joint_research.research.wallet_flow_diagnostic_triage import (  # noqa: PLC0415
        write_wallet_flow_diagnostic_triage_report,
    )
    from joint_research.research.wallet_flow_promotion_plan import (  # noqa: PLC0415
        write_wallet_flow_promotion_plan_report,
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
    diagnostic_triage_md = None
    promotion_plan_md = None
    diagnostics = None
    if diagnostic_report or promotion_plan:
        diagnostics = build_wallet_flow_rejection_diagnostics(
            raw_results=study_details.raw_results,
            final_results=results,
        )
    if diagnostic_report and diagnostics is not None:
        diagnostic_triage_md = write_wallet_flow_diagnostic_triage_report(
            output_dir=resolved_output_dir,
            diagnostics=diagnostics,
        )
    if promotion_plan and diagnostics is not None:
        promotion_plan_md = write_wallet_flow_promotion_plan_report(
            output_dir=resolved_output_dir,
            diagnostics=diagnostics,
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


@research_app.command("simulate")
def research_simulate(
    candidate_source: str = typer.Option(
        "robustness",
        help="Candidate source: robustness|composite-signal|derivatives-regime|wallet-flow-signal.",
    ),
    starting_capital: float = typer.Option(200.0, help="Paper bankroll in USD."),
    fixed_notional: float = typer.Option(10.0, help="Fixed paper notional per trade."),
    max_simultaneous_exposure: float = typer.Option(
        50.0,
        help="Maximum simultaneous simulated exposure in USD.",
    ),
    fee_bps: float = typer.Option(10.0, help="Per-side paper fee in basis points."),
    slippage_bps: float = typer.Option(10.0, help="Per-side paper slippage in basis points."),
    min_samples: int = typer.Option(20, help="Minimum simulation observations per candidate."),
    min_probability_move: float = typer.Option(
        0.001,
        help="Skip signals with smaller absolute probability movement.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/research/simulation"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for simulation_summary.md, simulation_trades.csv, "
            "simulation_results.csv, and simulation_candidates.json."
        ),
    ),
    show_top: int = typer.Option(10, help="Print the top-N simulated candidates."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run paper-only walk-forward simulation for robust candidates."""

    from joint_research.research.simulation import (  # noqa: PLC0415
        SimulationGrade,
        CANDIDATE_SOURCES,
        run_simulation_study,
        write_simulation_report,
    )

    if candidate_source not in CANDIDATE_SOURCES:
        raise typer.BadParameter(
            "candidate_source must be one of: "
            + ",".join(sorted(CANDIDATE_SOURCES))
        )

    paths = _resolve_paths(warehouse_root)
    results = run_simulation_study(
        paths=paths,
        candidate_source=candidate_source,
        starting_capital=starting_capital,
        fixed_notional=fixed_notional,
        max_simultaneous_exposure=max_simultaneous_exposure,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        min_samples=min_samples,
        min_probability_move=min_probability_move,
    )
    resolved_output_dir = output_dir.resolve()
    file_prefix = "simulation"
    if candidate_source == "wallet-flow-signal":
        file_prefix = "simulation_wallet_flow"
        if output_dir == Path("artifacts/research/simulation"):
            resolved_output_dir = Path("artifacts/research/simulation_wallet_flow").resolve()
    report_paths = write_simulation_report(
        output_dir=resolved_output_dir,
        results=results,
        file_prefix=file_prefix,
    )

    counts = {
        grade.value: sum(1 for result in results if result.simulation_grade is grade)
        for grade in SimulationGrade
    }
    total_pnl = sum(result.total_paper_pnl for result in results)
    total_trades = sum(result.trade_count for result in results)
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"candidate_source={candidate_source} "
        f"candidates_simulated={len(results)} "
        f"trades={total_trades} "
        f"paper_pnl=${total_pnl:.2f} "
        f"paper_ready={counts['PAPER_READY']} "
        f"watchlist={counts['WATCHLIST']} "
        f"rejected={counts['REJECTED']}"
    )
    typer.echo(f"summary={report_paths.summary_md}")
    typer.echo(f"trades_csv={report_paths.trades_csv}")
    typer.echo(f"results_csv={report_paths.results_csv}")
    typer.echo(f"candidates_json={report_paths.candidates_json}")

    candidates = [
        result for result in results if result.simulation_grade is not SimulationGrade.REJECTED
    ][:show_top]
    if not candidates:
        typer.echo("no simulation candidates survived beyond REJECTED.")
        raise typer.Exit(code=0)

    typer.echo(f"\ntop {show_top} simulated candidates:")
    for result in candidates:
        typer.echo(
            f"  rank={result.rank:>2} grade={result.simulation_grade.value:<11} "
            f"asset={result.asset:>4} lag={result.lag_hours:>2}h "
            f"trades={result.trade_count} win={result.win_rate:.2f} "
            f"pnl=${result.total_paper_pnl:.2f} dd=${result.max_drawdown:.2f} "
            f"market={result.market_slug or result.market_id}"
        )


@ingest_app.command("wallet-activity")
def ingest_wallet_activity(
    limit: int = typer.Option(50, help="Top-N wallets to discover and pull activity for."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull whale wallet activity (top traders + market top-holders) via DataAPI."""

    from joint_research.ingest.wallet_runner import (  # noqa: PLC0415
        ingest_whale_wallet_activity as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(run(paths=paths, limit=limit))
    typer.echo(
        f"wallets_selected={result.wallets_selected} "
        f"activities_fetched={result.activities_fetched} "
        f"rows_written={result.rows_written} "
        f"shard={result.shard_path or '(none)'}"
    )


@ingest_app.command("polymarket-wallet-flow")
def ingest_polymarket_wallet_flow(
    limit_markets: int = typer.Option(20, help="Top-N crypto-tagged markets to scope ingestion."),
    limit_events: int = typer.Option(500, help="Maximum rows to write for this run."),
    min_volume: float = typer.Option(
        0.0,
        help="Minimum market volume (1mo, fallback total) required for market selection.",
    ),
    asset: str | None = typer.Option(
        None,
        help="Optional asset filter (e.g. BTC, ETH, SOL, XRP).",
    ),
    lookback_hours: int | None = typer.Option(
        None,
        help="Optional lookback window; keep only rows newer than N hours.",
    ),
    large_trade_usdc: float = typer.Option(
        1_000.0,
        help="USDC notional threshold used to tag large trades.",
    ),
    include_copy_signals: bool = typer.Option(
        True,
        "--include-copy-signals/--no-copy-signals",
        help="Include copy-trader relationship evidence rows when available.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Pull public Polymarket wallet/trader flow into the warehouse."""

    from joint_research.ingest.polymarket_wallet_flow import (  # noqa: PLC0415
        ingest_polymarket_wallet_flow as run,
    )

    paths = _resolve_paths(warehouse_root)
    result = asyncio.run(
        run(
            paths=paths,
            limit_markets=limit_markets,
            limit_events=limit_events,
            min_volume=min_volume,
            asset=asset,
            lookback_hours=lookback_hours,
            large_trade_usdc=large_trade_usdc,
            include_copy_signals=include_copy_signals,
        )
    )
    typer.echo(
        f"markets_scanned={result.markets_scanned} "
        f"markets_with_rows={result.markets_with_rows} "
        f"skipped_markets={result.skipped_markets} "
        f"rows_written={result.rows_written} "
        f"trade_rows={result.trade_rows} "
        f"copy_rows={result.copy_rows} "
        f"sources={','.join(result.source_clients) if result.source_clients else '(none)'} "
        f"shard={result.shard_path or '(none)'}"
    )
    for warning in result.warnings:
        typer.echo(f"  warning={warning}")


@ingest_app.command("wallet-flow-backfill-plan")
def ingest_wallet_flow_backfill_plan(
    asset: str = typer.Option(
        "ALL",
        help="Asset scope: BTC|ETH|SOL|XRP|ALL.",
    ),
    stage: str = typer.Option(
        "stage_1_quick",
        help="Stage: stage_1_quick|stage_2_depth|stage_3_breadth.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="Execute the selected stage using the existing polymarket-wallet-flow ingestor.",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run mode (default). Automatically disabled when --execute is passed.",
    ),
    limit_markets: int | None = typer.Option(
        None,
        help="Optional stage market cap override.",
    ),
    limit_events: int = typer.Option(
        2000,
        help="Maximum rows to write when running in --execute mode.",
    ),
    min_volume: float = typer.Option(
        0.0,
        help="Minimum 1mo/total market volume required for plan eligibility.",
    ),
    output_dir: Path = typer.Option(
        Path("artifacts/ingest/wallet_flow_backfill_plan"),
        "--output-dir",
        "--out-path",
        help=(
            "Directory for wallet_flow_backfill_plan.md, wallet_flow_backfill_plan.csv, "
            "and wallet_flow_coverage.csv."
        ),
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Build a safe staged wallet-flow backfill plan, and optionally execute one stage."""

    from joint_research.ingest.wallet_flow_backfill_plan import (  # noqa: PLC0415
        STAGE_ORDER,
        run_wallet_flow_backfill_plan,
    )

    valid_assets = {"BTC", "ETH", "SOL", "XRP", "ALL"}
    normalized_asset = asset.strip().upper()
    if normalized_asset not in valid_assets:
        raise typer.BadParameter("asset must be one of BTC|ETH|SOL|XRP|ALL")
    if stage not in STAGE_ORDER:
        raise typer.BadParameter("stage must be one of stage_1_quick|stage_2_depth|stage_3_breadth")

    paths = _resolve_paths(warehouse_root)
    result = run_wallet_flow_backfill_plan(
        paths=paths,
        output_dir=output_dir.resolve(),
        asset=normalized_asset,
        stage=stage,
        limit_markets=limit_markets,
        limit_events=limit_events,
        min_volume=min_volume,
        execute=execute,
        dry_run=(dry_run and not execute),
    )
    typer.echo(
        "EXPLORATORY ONLY - NOT TRADEABLE\n"
        f"asset={normalized_asset} stage={result.selected_stage} "
        f"stage_markets={result.selected_stage_markets} "
        f"stage_1={result.stage_counts.get('stage_1_quick', 0)} "
        f"stage_2={result.stage_counts.get('stage_2_depth', 0)} "
        f"stage_3={result.stage_counts.get('stage_3_breadth', 0)} "
        f"dry_run={not execute}"
    )
    typer.echo(f"plan_md={result.artifacts.plan_md}")
    typer.echo(f"plan_csv={result.artifacts.plan_csv}")
    typer.echo(f"coverage_csv={result.artifacts.coverage_csv}")
    typer.echo(
        f"coverage_before wallet_flow_rows={result.before.wallet_flow_rows} "
        f"trade_rows={result.before.trade_rows} "
        f"copy_rows={result.before.copy_rows} "
        f"market_flow_hourly_rows={result.before.market_flow_hourly_rows} "
        f"whale_flow_hourly_rows={result.before.whale_flow_hourly_rows}"
    )

    if result.execution is None:
        return

    execution = result.execution
    typer.echo(
        f"executed stage={execution.stage} "
        f"rows_written={execution.rows_written} "
        f"trade_rows={execution.trade_rows_written} "
        f"copy_rows={execution.copy_rows_written} "
        f"markets_scanned={execution.markets_scanned} "
        f"markets_with_rows={execution.markets_with_rows} "
        f"skipped_markets={execution.skipped_markets} "
        f"sources={','.join(execution.source_clients) if execution.source_clients else '(none)'}"
    )
    typer.echo(
        f"coverage_after wallet_flow_rows={execution.after.wallet_flow_rows} "
        f"trade_rows={execution.after.trade_rows} "
        f"copy_rows={execution.after.copy_rows} "
        f"market_flow_hourly_rows={execution.after.market_flow_hourly_rows} "
        f"whale_flow_hourly_rows={execution.after.whale_flow_hourly_rows}"
    )
    for warning in execution.warnings:
        typer.echo(f"  warning={warning}")


@research_app.command("event-study")
def research_event_study(
    min_trade_size_usdc: float = typer.Option(
        100.0, help="Skip trades smaller than this notional in USDC."
    ),
    out_path: Path = typer.Option(
        Path("data/research/event_study_catalog.parquet"),
        help="Output Parquet path for the event-study cells.",
    ),
    show_top: int = typer.Option(20, help="Print the top-N cells by |t-stat|."),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Run the whale-trade → crypto-return event study."""

    from joint_research.research.event_study import (  # noqa: PLC0415
        run_event_study,
        write_event_study_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    result = run_event_study(
        paths=paths,
        min_trade_size_usdc=min_trade_size_usdc,
    )
    write_event_study_catalog(out_path=out_path.resolve(), result=result)

    typer.echo(
        f"trades_total={result.n_trades_total} "
        f"wallets={result.n_wallets} assets={result.n_assets} "
        f"cells={len(result.cells)}"
    )

    sig = [c for c in result.cells if c.bh_significant_at_0_05]
    if sig:
        typer.echo(f"BH-significant cells: {len(sig)}")
        for c in sig:
            typer.echo(
                f"  asset={c.asset} dir={c.direction} lag={c.lag_hours}h "
                f"mean={c.mean_log_return*1e4:+.2f}bps "
                f"t={c.tstat_vs_zero:+.2f} p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
            )
    else:
        typer.echo("no BH-significant cells at alpha=0.05")

    typer.echo(f"\ntop {show_top} cells by |t|:")
    ordered = sorted(
        (c for c in result.cells if not math.isnan(c.tstat_vs_zero)),
        key=lambda c: -abs(c.tstat_vs_zero),
    )[:show_top]
    for c in ordered:
        typer.echo(
            f"  asset={c.asset:>4} dir={c.direction:>8} lag={c.lag_hours:>2}h "
            f"mean={c.mean_log_return*1e4:+7.2f}bps t={c.tstat_vs_zero:+.2f} "
            f"p={c.pvalue_vs_zero:.4f} n={c.n_trades}"
        )


@research_app.command("cryp-backtest")
def research_cryp_backtest(
    symbols: str = typer.Option(
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT",
        help="Comma-separated symbol list to backtest.",
    ),
    feature_lookback: int = typer.Option(14, help="Hours of history fed to feature pipeline."),
    max_holding_hours: int = typer.Option(24, help="Max bars to hold a trade if neither stop nor TP hits."),
    round_trip_cost_bps: float = typer.Option(
        14.0,
        help="Combined entry+exit fee + slippage in bps. Bybit perp taker is ~11 bps round-trip; 14 leaves buffer.",
    ),
    out_path: Path = typer.Option(
        Path("data/research/cryp_backtest_trades.parquet"),
        help="Output Parquet path for the per-trade ledger.",
    ),
    warehouse_root: Path = typer.Option(None),
) -> None:
    """Backtest cryp's deterministic breakout/mean-reversion on warehouse OHLCV."""

    from joint_research.research.cryp_backtest import (  # noqa: PLC0415
        run_cryp_backtest,
        write_backtest_catalog,
    )

    paths = _resolve_paths(warehouse_root)
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    results = []
    for symbol in symbol_list:
        res = run_cryp_backtest(
            paths=paths,
            symbol=symbol,
            feature_lookback=feature_lookback,
            max_holding_hours=max_holding_hours,
            round_trip_cost_bps=round_trip_cost_bps,
        )
        results.append(res)
        s = res.summary()
        typer.echo(
            f"symbol={res.symbol:<10} candles={res.n_candles:>5} "
            f"breakout_props={res.n_proposals_breakout:>4} "
            f"mr_props={res.n_proposals_mean_reversion:>4} "
            f"trades={s['n_trades']:>4} "
            f"hit_rate={s['hit_rate']:.2f} "
            f"mean_bps={s['mean_net_bps']:+7.2f} "
            f"total_bps={s['total_net_bps']:+8.1f} "
            f"max_dd_bps={s['max_drawdown_bps']:7.1f} "
            f"sharpe={s['sharpe_per_trade']:+5.2f}"
        )

    write_backtest_catalog(out_path=out_path.resolve(), results=results)
    typer.echo(f"\ntrades catalog: {out_path.resolve()}")


if __name__ == "__main__":
    app()
