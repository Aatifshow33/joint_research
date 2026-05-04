import dataclasses
import pytest

from joint_research.wallet_flow_coverage_schema_contract import (
    CoverageArtifactSchema,
    COVERAGE_ARTIFACT_SCHEMAS,
    get_coverage_artifact_schema,
    list_coverage_artifact_names,
)


def test_module_docstring_contains_exploratory_only_not_tradeable() -> None:
    import joint_research.wallet_flow_coverage_schema_contract as module

    assert module.__doc__ is not None
    assert "EXPLORATORY ONLY - NOT TRADEABLE" in module.__doc__
    assert "static schema contracts only" in module.__doc__


def test_coverage_artifact_schemas_exactly_ten_entries() -> None:
    assert isinstance(COVERAGE_ARTIFACT_SCHEMAS, tuple)
    assert len(COVERAGE_ARTIFACT_SCHEMAS) == 10


def test_every_entry_is_coverage_artifact_schema() -> None:
    assert all(isinstance(item, CoverageArtifactSchema) for item in COVERAGE_ARTIFACT_SCHEMAS)


def test_artifact_names_stable_order() -> None:
    expected = (
        "market_coverage.csv",
        "wallet_class_coverage.csv",
        "horizon_coverage.csv",
        "missingness_summary.csv",
        "concentration_diagnostics.csv",
        "recency_distribution.csv",
        "cost_buffer_diagnostics.csv",
        "win_rate_by_coverage.csv",
        "rerun_readiness_checklist.md",
        "operator_notes.md",
    )
    assert list_coverage_artifact_names() == expected
    assert tuple(schema.artifact for schema in COVERAGE_ARTIFACT_SCHEMAS) == expected


def test_csv_artifacts_have_format_csv_and_markdown_have_format_markdown() -> None:
    csv_names = {
        "market_coverage.csv",
        "wallet_class_coverage.csv",
        "horizon_coverage.csv",
        "missingness_summary.csv",
        "concentration_diagnostics.csv",
        "recency_distribution.csv",
        "cost_buffer_diagnostics.csv",
        "win_rate_by_coverage.csv",
    }
    markdown_names = {"rerun_readiness_checklist.md", "operator_notes.md"}

    for schema in COVERAGE_ARTIFACT_SCHEMAS:
        if schema.artifact in csv_names:
            assert schema.format == "CSV"
        elif schema.artifact in markdown_names:
            assert schema.format == "Markdown"
        else:
            pytest.fail(f"Unexpected artifact name: {schema.artifact}")


def test_required_columns_or_keys_match_expected_values() -> None:
    expected_columns = {
        "market_coverage.csv": (
            "market_id",
            "market_slug",
            "unique_flow_hours",
            "total_flow_rows",
            "coverage_bucket",
            "first_flow_ts",
            "last_flow_ts",
        ),
        "wallet_class_coverage.csv": (
            "wallet_class",
            "wallet_count",
            "unique_flow_hours",
            "total_flow_rows",
            "concentration_share",
            "coverage_bucket",
        ),
        "horizon_coverage.csv": (
            "horizon_hours",
            "market_count",
            "unique_flow_hours",
            "coverage_bucket",
            "sparse_segment_count",
        ),
        "missingness_summary.csv": (
            "field_name",
            "null_count",
            "null_rate",
            "affected_markets",
            "affected_wallet_classes",
        ),
        "concentration_diagnostics.csv": (
            "dimension",
            "entity_id",
            "entity_label",
            "flow_share",
            "rank",
            "concentration_bucket",
        ),
        "recency_distribution.csv": (
            "dimension",
            "entity_id",
            "first_flow_ts",
            "last_flow_ts",
            "age_hours",
            "recency_bucket",
        ),
        "cost_buffer_diagnostics.csv": (
            "coverage_bucket",
            "horizon_hours",
            "candidate_count",
            "improvement_below_cost_buffer_count",
            "median_edge_after_cost",
        ),
        "win_rate_by_coverage.csv": (
            "coverage_bucket",
            "horizon_hours",
            "candidate_count",
            "weak_win_rate_count",
            "median_win_rate",
        ),
        "rerun_readiness_checklist.md": (
            "coverage_reviewed",
            "bottlenecks_explained",
            "missingness_reviewed",
            "concentration_reviewed",
            "rerun_scope_required",
        ),
        "operator_notes.md": (
            "summary",
            "unresolved_gaps",
            "recommended_next_step",
            "safety_boundary",
        ),
    }
    for schema in COVERAGE_ARTIFACT_SCHEMAS:
        assert schema.required_columns_or_keys == expected_columns[schema.artifact]


def test_boundary_strings_match_expected_values() -> None:
    expected_boundaries = {
        "market_coverage.csv": "Diagnostic only.",
        "wallet_class_coverage.csv": "No wallet promotion.",
        "horizon_coverage.csv": "No rerun approval.",
        "missingness_summary.csv": "No ingestion approval.",
        "concentration_diagnostics.csv": "No live execution.",
        "recency_distribution.csv": "No tradeability claim.",
        "cost_buffer_diagnostics.csv": "No threshold loosening.",
        "win_rate_by_coverage.csv": "No candidate promotion.",
        "rerun_readiness_checklist.md": "No automatic rerun.",
        "operator_notes.md": "Exploratory only.",
    }
    for schema in COVERAGE_ARTIFACT_SCHEMAS:
        assert schema.boundary == expected_boundaries[schema.artifact]


def test_get_coverage_artifact_schema_returns_matching_schema() -> None:
    for schema in COVERAGE_ARTIFACT_SCHEMAS:
        matched = get_coverage_artifact_schema(schema.artifact)
        assert matched is schema


def test_get_coverage_artifact_schema_raises_key_error_for_unknown_artifact() -> None:
    with pytest.raises(KeyError):
        get_coverage_artifact_schema("unknown_artifact.csv")


def test_dataclass_is_frozen() -> None:
    schema = COVERAGE_ARTIFACT_SCHEMAS[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        schema.artifact = "other.csv"
