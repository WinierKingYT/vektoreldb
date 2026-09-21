"""Opt-in selectivity-aware retrieval planning."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchPlan:
    mode: str
    candidate_limit: int
    exact: bool = False
    selectivity: float | None = None


class SelectivityQueryPlanner:
    """Choose a conservative filtered-search strategy from measured selectivity."""

    def __init__(self, *, strict_threshold: float = 0.05, medium_threshold: float = 0.5):
        if not 0 < strict_threshold < medium_threshold <= 1:
            raise ValueError("planner thresholds must satisfy 0 < strict < medium <= 1")
        self.strict_threshold = strict_threshold
        self.medium_threshold = medium_threshold

    def plan(
        self,
        selectivity: float | None,
        *,
        limit: int,
        has_user_filter: bool,
    ) -> SearchPlan:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if not has_user_filter or selectivity is None:
            return SearchPlan("normal_ann", limit, selectivity=selectivity)
        if not 0 <= selectivity <= 1:
            raise ValueError("selectivity must be between 0 and 1")
        if selectivity <= self.strict_threshold:
            return SearchPlan("exact_fallback", limit, exact=True, selectivity=selectivity)
        if selectivity <= self.medium_threshold:
            return SearchPlan(
                "wide_ann", min(100, max(limit * 4, 20)), selectivity=selectivity
            )
        return SearchPlan("normal_ann", limit, selectivity=selectivity)
