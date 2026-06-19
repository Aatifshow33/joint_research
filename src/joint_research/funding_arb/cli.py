"""``funding-arb`` CLI: scan live funding opportunities and project growth.

No orders are placed. ``scan`` ranks delta-neutral cross-venue funding
opportunities from live perp-DEX data; ``plan`` projects the contribution-driven
path of a small stake toward a target.
"""

from __future__ import annotations

import typer

from joint_research.funding_arb.plan import (
    monthly_contribution_for_target,
    project_growth,
)
from joint_research.funding_arb.scanner import scan_funding_opportunities

app = typer.Typer(help="Delta-neutral funding-rate arbitrage (scan + growth plan, no execution).")


@app.command()
def scan(
    taker_fee: float = typer.Option(0.0005, "--taker-fee", help="Per-leg taker fee fraction."),
    haircut: float = typer.Option(
        0.5, "--haircut", help="Discount on snapshot APR (0.5 = assume half persists)."
    ),
    major_only: bool = typer.Option(
        True, "--major-only/--all", help="Restrict to liquid majors (safer)."
    ),
    min_apr: float = typer.Option(
        0.05, "--min-apr", help="Minimum realistic (haircut) APR to surface."
    ),
) -> None:
    """Fetch live funding from Hyperliquid + dYdX and rank opportunities."""
    from joint_research.funding_arb.venues import fetch_dydx_quotes, fetch_hyperliquid_quotes

    quotes = fetch_hyperliquid_quotes() + fetch_dydx_quotes()
    opps = scan_funding_opportunities(
        quotes,
        taker_fee=taker_fee,
        haircut=haircut,
        major_only=major_only,
        min_realistic_apr=min_apr,
    )
    typer.echo(f"quotes={len(quotes)} opportunities={len(opps)} (realistic APR >= {min_apr:.0%})")
    typer.echo(
        f"{'base':<6} {'long@':<12} {'short@':<12} {'gross_apr':>9} "
        f"{'real_apr':>9} {'breakeven':>10}"
    )
    for o in opps[:15]:
        typer.echo(
            f"{o.base:<6} {o.long_venue:<12} {o.short_venue:<12} "
            f"{o.gross_apr:>8.0%} {o.realistic_apr:>8.0%} {o.breakeven_hours:>8.0f}h"
        )
    if not opps:
        typer.echo("  (no opportunities clear the threshold right now)")


@app.command()
def plan(
    start: float = typer.Option(200.0, "--start", help="Starting stake (USD)."),
    monthly: float = typer.Option(375.0, "--monthly", help="Monthly contribution (USD)."),
    annual_yield: float = typer.Option(0.15, "--yield", help="Assumed net annual yield."),
    months: int = typer.Option(12, "--months", help="Projection horizon."),
    target: float = typer.Option(5000.0, "--target", help="Target balance for the solver."),
) -> None:
    """Project the month-by-month path and the contribution needed for a target."""
    result = project_growth(
        start=start, monthly_contribution=monthly, annual_yield=annual_yield, months=months
    )
    typer.echo(
        f"start ${start:.0f} | +${monthly:.0f}/mo | {annual_yield:.0%}/yr net | {months} months"
    )
    typer.echo(f"{'month':>5} {'contributed':>12} {'balance':>10} {'from_returns':>13}")
    for p in result.points:
        typer.echo(
            f"{p.month:>5} {p.contributed_to_date:>12.0f} {p.balance:>10.0f} "
            f"{p.return_to_date:>13.0f}"
        )
    typer.echo(
        f"\nfinal ${result.final_balance:.0f} "
        f"(${result.total_contributed:.0f} contributed + "
        f"${result.total_return:.0f} returns; "
        f"{result.return_share:.0%} from returns)"
    )
    needed = monthly_contribution_for_target(
        start=start, target=target, annual_yield=annual_yield, months=months
    )
    typer.echo(
        f"to hit ${target:.0f} in {months} months at {annual_yield:.0%}/yr: "
        f"contribute ${needed:.0f}/month"
    )


if __name__ == "__main__":  # pragma: no cover
    app()
