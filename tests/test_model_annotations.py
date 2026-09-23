"""The provenance merge and the dedup rule are the two load-bearing invariants."""

import polars as pl

from model_annotations import dedup_oldest, merge_provenance, parse_exclusions


def _rows(records):
    return pl.DataFrame(
        records,
        schema={
            "annotation_accession": pl.String,
            "output_type": pl.String,
            "file_accession": pl.String,
            "is_own": pl.Boolean,
        },
        orient="row",
    )


def test_own_file_wins_over_borrowed_contributing_file():
    """A contributing file sharing an output_type with an own file is dropped.

    ENCODE lists files borrowed from other annotations under the same
    output_type. Keeping both produces comma-joined multi-file cells that break
    the manifest's existence check and contaminate the table.
    """
    df = _rows(
        [
            ("ENCSR1", "observed signal profile", "OWN.bigWig", True),
            ("ENCSR1", "observed signal profile", "BORROWED.bigWig", False),
        ]
    )

    kept = merge_provenance(df)

    assert kept.get_column("file_accession").to_list() == ["OWN.bigWig"]


def test_contributing_only_output_types_survive():
    """Control profiles, alignments and bias models have no own counterpart."""
    df = _rows(
        [
            ("ENCSR1", "observed signal profile", "OWN.bigWig", True),
            ("ENCSR1", "alignments", "CONTRIB.bam", False),
        ]
    )

    kept = merge_provenance(df)

    assert sorted(kept.get_column("file_accession").to_list()) == [
        "CONTRIB.bam",
        "OWN.bigWig",
    ]


def test_provenance_is_scoped_per_annotation():
    """One annotation owning an output_type must not mask another's contribution."""
    df = _rows(
        [
            ("ENCSR1", "observed signal profile", "OWN.bigWig", True),
            ("ENCSR2", "observed signal profile", "CONTRIB.bigWig", False),
        ]
    )

    kept = merge_provenance(df)

    assert kept.height == 2


def _dedup_rows(records):
    return pl.DataFrame(
        records,
        schema={
            "experiment_accession": pl.String,
            "annotation_accession": pl.String,
            "date_created": pl.String,
        },
        orient="row",
    )


def test_dedup_keeps_earliest_annotation():
    df = _dedup_rows(
        [
            ("EXP1", "ENCSR_B", "2024-05-01T00:00:00"),
            ("EXP1", "ENCSR_A", "2023-01-01T00:00:00"),
        ]
    )

    assert dedup_oldest(df).get_column("annotation_accession").to_list() == ["ENCSR_A"]


def test_dedup_breaks_ties_by_descending_accession():
    df = _dedup_rows(
        [
            ("EXP1", "ENCSR_A", "2023-01-01T00:00:00"),
            ("EXP1", "ENCSR_Z", "2023-01-01T00:00:00"),
        ]
    )

    assert dedup_oldest(df).get_column("annotation_accession").to_list() == ["ENCSR_Z"]


def test_dedup_drops_rows_without_an_experiment():
    df = _dedup_rows(
        [
            ("EXP1", "ENCSR_A", "2023-01-01T00:00:00"),
            (None, "ENCSR_B", "2023-01-01T00:00:00"),
        ]
    )

    assert dedup_oldest(df).height == 1


def test_parse_exclusions_splits_on_double_colon():
    assert parse_exclusions(["predicted signal profile::.bigWig"]) == [
        ("predicted signal profile", ".bigWig")
    ]
