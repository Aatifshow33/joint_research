"""EXPLORATORY ONLY - NOT TRADEABLE

This module defines static schema contracts only; it does not write artifacts, run ingestion,
rerun research, approve execution, or promote candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CoverageArtifactSchema:
    artifact: str
    format: str
    required_columns_or_keys: Tuple[str, ...]
    boundary: str


COVERAGE_ARTIFACT_SCHEMAS: Tuple[CoverageArtifactSchema, ...] = (
    CoverageArtifactSchema(
        artifact="market_coverage.csv",
        format="CSV",
        required_columns_or_keys=(
            "market_id",
            "market_slug",
            "unique_flow_hours",
            "total_flow_rows",
            "coverage_bucket",
            "first_flow_ts",
            "last_flow_ts",
        ),
        boundary="Diagnostic only.",
    ),
    CoverageArtifactSchema(
        artifact="wallet_class_coverage.csv",
        format="CSV",
        required_columns_or_keys=(
            "wallet_class",
            "wallet_count",
            "unique_flow_hours",
            "total_flow_rows",
            "concentration_share",
            "coverage_bucket",
        ),
        boundary="No wallet promotion.",
    ),
    CoverageArtifactSchema(
        artifact="horizon_coverage.csv",
        format="CSV",
        required_columns_or_keys=(
            "horizon_hours",
            "market_count",
            "unique_flow_hours",
            "coverage_bucket",
            "sparse_segment_count",
        ),
        boundary="No rerun approval.",
    ),
    CoverageArtifactSchema(
        artifact="missingness_summary.csv",
        format="CSV",
        required_columns_or_keys=(
            "field_name",
            "null_count",
            "null_rate",
            "affected_markets",
            "affected_wallet_classes",
        ),
        boundary="No ingestion approval.",
    ),
    CoverageArtifactSchema(
        artifact="concentration_diagnostics.csv",
        format="CSV",
        required_columns_or_keys=(
            "dimension",
            "entity_id",
            "entity_label",
            "flow_share",
            "rank",
            "concentration_bucket",
        ),
        boundary="No live execution.",
    ),
    CoverageArtifactSchema(
        artifact="recency_distribution.csv",
        format="CSV",
        required_columns_or_keys=(
            "dimension",
            "entity_id",
            "first_flow_ts",
            "last_flow_ts",
            "age_hours",
            "recency_bucket",
        ),
        boundary="No tradeability claim.",
    ),
    CoverageArtifactSchema(
        artifact="cost_buffer_diagnostics.csv",
        format="CSV",
        required_columns_or_keys=(
            "coverage_bucket",
            "horizon_hours",
            "candidate_count",
            "improvement_below_cost_buffer_count",
            "median_edge_after_cost",
        ),
        boundary="No threshold loosening.",
    ),
    CoverageArtifactSchema(
        artifact="win_rate_by_coverage.csv",
        format="CSV",
        required_columns_or_keys=(
            "coverage_bucket",
            "horizon_hours",
            "candidate_count",
            "weak_win_rate_count",
            "median_win_rate",
        ),
        boundary="No candidate promotion.",
    ),
    CoverageArtifactSchema(
        artifact="rerun_readiness_checklist.md",
        format="Markdown",
        required_columns_or_keys=(
            "coverage_reviewed",
            "bottlenecks_explained",
            "missingness_reviewed",
            "concentration_reviewed",
            "rerun_scope_required",
        ),
        boundary="No automatic rerun.",
    ),
    CoverageArtifactSchema(
        artifact="operator_notes.md",
        format="Markdown",
        required_columns_or_keys=(
            "summary",
            "unresolved_gaps",
            "recommended_next_step",
            "safety_boundary",
        ),
        boundary="Exploratory only.",
    ),
)


def get_coverage_artifact_schema(artifact: str) -> CoverageArtifactSchema:
    for schema in COVERAGE_ARTIFACT_SCHEMAS:
        if schema.artifact == artifact:
            return schema
    raise KeyError(f"Unknown coverage artifact: {artifact}")


def list_coverage_artifact_names() -> Tuple[str, ...]:
    return tuple(schema.artifact for schema in COVERAGE_ARTIFACT_SCHEMAS)
