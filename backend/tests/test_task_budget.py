"""Time-budget threshold unit tests."""

import pytest

from app.schemas.task import BudgetLevel
from app.services.tasks import calculate_budget_level


@pytest.mark.parametrize(
    ("estimated", "actual", "expected"),
    [
        (0, 100, BudgetLevel.NOT_SET),
        (100, 0, BudgetLevel.NORMAL),
        (100, 79, BudgetLevel.NORMAL),
        (100, 80, BudgetLevel.NEAR_LIMIT),
        (100, 99, BudgetLevel.NEAR_LIMIT),
        (100, 100, BudgetLevel.EXHAUSTED),
        (100, 149, BudgetLevel.EXHAUSTED),
        (100, 150, BudgetLevel.SEVERE),
    ],
)
def test_budget_thresholds(
    estimated: int,
    actual: int,
    expected: BudgetLevel,
) -> None:
    assert calculate_budget_level(estimated, actual) == expected

