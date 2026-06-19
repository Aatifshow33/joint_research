from __future__ import annotations

import pytest
from joint_research.funding_arb.plan import (
    monthly_contribution_for_target,
    project_growth,
)


def test_zero_yield_is_pure_contributions() -> None:
    plan = project_growth(start=200, monthly_contribution=400, annual_yield=0.0, months=12)
    assert plan.final_balance == pytest.approx(200 + 400 * 12)
    assert plan.total_return == pytest.approx(0.0)


def test_contributions_dominate_at_small_base() -> None:
    plan = project_growth(start=200, monthly_contribution=375, annual_yield=0.15, months=12)
    # Returns should be a small slice of the final balance at this scale.
    assert plan.return_share < 0.15
    assert plan.final_balance > plan.total_contributed


def test_solver_hits_target_when_plugged_back_in() -> None:
    needed = monthly_contribution_for_target(
        start=200, target=5000, annual_yield=0.15, months=12
    )
    plan = project_growth(
        start=200, monthly_contribution=needed, annual_yield=0.15, months=12
    )
    assert plan.final_balance == pytest.approx(5000, abs=1.0)


def test_solver_zero_yield_is_linear() -> None:
    needed = monthly_contribution_for_target(
        start=200, target=5000, annual_yield=0.0, months=12
    )
    assert needed == pytest.approx((5000 - 200) / 12)


def test_project_growth_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError):
        project_growth(start=-1, monthly_contribution=10, annual_yield=0.1, months=12)
