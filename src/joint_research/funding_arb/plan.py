"""Growth projection for the $200 -> $5,000 compounding plan.

The honest decomposition: at a small base, monthly contributions do most of the
work and the strategy yield is a top-up. This module makes that explicit — it
projects the month-by-month balance from a starting stake, a fixed monthly
contribution, and an annualized net yield, and reports how much of the final
balance came from contributions vs. returns.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonthPoint:
    month: int
    contributed_to_date: float
    balance: float
    return_to_date: float


@dataclass(frozen=True)
class GrowthPlan:
    start: float
    monthly_contribution: float
    annual_yield: float
    months: int
    points: list[MonthPoint]

    @property
    def final_balance(self) -> float:
        return self.points[-1].balance if self.points else self.start

    @property
    def total_contributed(self) -> float:
        return self.start + self.monthly_contribution * self.months

    @property
    def total_return(self) -> float:
        return self.final_balance - self.total_contributed

    @property
    def return_share(self) -> float:
        """Fraction of the final balance that came from strategy returns."""
        return self.total_return / self.final_balance if self.final_balance else 0.0


def project_growth(
    *,
    start: float,
    monthly_contribution: float,
    annual_yield: float,
    months: int,
) -> GrowthPlan:
    """Project a contribution-plus-yield balance path, compounded monthly.

    Contributions are added at the start of each month, then the monthly yield
    (``annual_yield / 12``) is applied — a deliberately conservative ordering.
    """
    if start < 0 or monthly_contribution < 0:
        raise ValueError("start_and_contribution_must_be_nonnegative")
    if months < 0:
        raise ValueError("months_must_be_nonnegative")

    monthly_rate = annual_yield / 12.0
    balance = start
    contributed = start
    points: list[MonthPoint] = []
    for month in range(1, months + 1):
        balance += monthly_contribution
        contributed += monthly_contribution
        balance *= 1.0 + monthly_rate
        points.append(
            MonthPoint(
                month=month,
                contributed_to_date=round(contributed, 2),
                balance=round(balance, 2),
                return_to_date=round(balance - contributed, 2),
            )
        )
    return GrowthPlan(
        start=start,
        monthly_contribution=monthly_contribution,
        annual_yield=annual_yield,
        months=months,
        points=points,
    )


def monthly_contribution_for_target(
    *,
    start: float,
    target: float,
    annual_yield: float,
    months: int,
) -> float:
    """Solve the fixed monthly contribution needed to reach ``target``.

    Closed-form from the future-value-of-an-annuity identity, so it is exact
    rather than searched.
    """
    if months <= 0:
        raise ValueError("months_must_be_positive")
    r = annual_yield / 12.0
    if r == 0:
        return max(0.0, (target - start) / months)
    growth = (1.0 + r) ** months
    fv_start = start * growth
    # Contributions added at start of month -> annuity-due factor.
    annuity_due = (growth - 1.0) / r * (1.0 + r)
    needed = (target - fv_start) / annuity_due
    return max(0.0, needed)
