"""Header normalization must not merge distinct ENCODE columns."""

import polars as pl
import pytest
from slugify import slugify

from report_to_parquet import deduplicate, main, normalize


def test_percent_and_count_headers_stay_distinct():
    """`% of x` and `# of x` are different measurements, not one column.

    Plain slugify drops both markers and collapses them, which is what made
    star_quality_metric_report unconvertible.
    """
    headers = ["% of chimeric reads", "# of chimeric reads"]

    assert len({slugify(h, separator="_") for h in headers}) == 1, "premise"
    assert len({normalize(h) for h in headers}) == 2


def test_normalize_spells_out_markers():
    assert normalize("% of chimeric reads") == "pct_of_chimeric_reads"
    assert normalize("# of chimeric reads") == "num_of_chimeric_reads"


def test_normalize_is_plain_snake_case_otherwise():
    assert normalize("Biosample term name") == "biosample_term_name"
    assert normalize("@id") == "id"


def test_deduplicate_suffixes_repeats_in_order():
    assert deduplicate(["id", "id", "a", "id"]) == ["id", "id_2", "a", "id_3"]


def test_deduplicate_leaves_unique_names_alone():
    assert deduplicate(["a", "b"]) == ["a", "b"]


@pytest.mark.parametrize(
    "headers",
    [
        ["ID", "@id"],                                    # document_report
        ["% of chimeric reads", "# of chimeric reads"],   # star_quality_metric
    ],
)
def test_colliding_reports_now_convert(tmp_path, headers):
    """Reports that previously raised DuplicateError produce distinct columns."""
    source = tmp_path / "report.tsv"
    source.write_text("\t".join(headers) + "\n" + "\t".join("12") + "\n")
    out = tmp_path / "report.parquet"

    main(["--input", str(source), "--output", str(out)])

    assert len(set(pl.read_parquet(out).columns)) == 2
