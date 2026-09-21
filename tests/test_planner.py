import pytest

from personal_vector_db.planner import SelectivityQueryPlanner


def test_planner_uses_exact_fallback_for_strict_filters() -> None:
    plan = SelectivityQueryPlanner().plan(0.01, limit=8, has_user_filter=True)

    assert plan.mode == "exact_fallback"
    assert plan.exact is True
    assert plan.candidate_limit == 8


def test_planner_overfetches_for_medium_selectivity() -> None:
    plan = SelectivityQueryPlanner().plan(0.25, limit=8, has_user_filter=True)

    assert plan.mode == "wide_ann"
    assert plan.exact is False
    assert plan.candidate_limit == 32


def test_planner_keeps_unfiltered_search_normal() -> None:
    plan = SelectivityQueryPlanner().plan(None, limit=8, has_user_filter=False)

    assert plan.mode == "normal_ann"
    assert plan.candidate_limit == 8


def test_planner_rejects_invalid_thresholds_and_selectivity() -> None:
    with pytest.raises(ValueError):
        SelectivityQueryPlanner(strict_threshold=0.5, medium_threshold=0.2)
    with pytest.raises(ValueError):
        SelectivityQueryPlanner().plan(1.1, limit=8, has_user_filter=True)
