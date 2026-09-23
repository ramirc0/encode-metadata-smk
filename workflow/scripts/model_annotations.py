"""Annotation / experiment / file parquets -> one model-annotation table per model.

A direct port of the `annotation_manifests.py` marimo notebook. The join keeps
each annotation's own files in preference to contributing files carrying the same
`output_type`; see `merge_provenance` for why that matters.
"""

import argparse
import os
from pathlib import Path

import polars as pl
from slugify import slugify

MANIFEST_ENTRY_FORMAT = "{url}\n\tdir={dir}\n\tout={out}\n"

# Leading metadata block, identical for every model and consumed as-is by
# tarball_manifest.py, which takes the first 13 columns.
META_COLUMNS = [
    ("annotation_accession", "Annotation accession"),
    ("annotation_status", "Annotation status"),
    ("experiment_accession", "Experiment accession"),
    ("experiment_status", "Experiment status"),
    ("perturbed", "Experiment peturbed"),
    ("simple_biosample_summary", "Biosample simple summary"),
    ("target_of_assay", "Experiment target of assay"),
    ("biosample_term_name", "Experiment biosample term name"),
    ("biosample_term_id", "Biosample term id"),
    ("biosample_classification", "Biosample classification"),
    ("genome_assembly", "Assembly"),
    ("organism", "Organism"),
    ("assay_name", "Assay term name"),
]

# Per model: (pivoted column, output header, kind). "path" columns are rewritten
# to local absolute paths and are what the download manifest is built from;
# "accession" columns keep bare accessions.
FILE_COLUMNS = {
    "ChromBPNet": [
        ("models", "Annotation models file", "path"),
        ("observed_signal_profile", "Annotation observed signal profile", "path"),
        ("predicted_signal_profile", "Annotation predicted signal profile", "path"),
        (
            "training_and_test_regions",
            "Annotation test and training regions",
            "path",
        ),
        ("alignments", "Annotation alignments file accessions", "accession"),
        (
            "unfiltered_alignments",
            "Annotation unfiltered alignments file accessions",
            "accession",
        ),
    ],
    "BPNet": [
        ("models", "Annotation models file", "path"),
        (
            "observed_signal_profile_plus_strand",
            "Annotation observed signal profile file (plus strand)",
            "path",
        ),
        (
            "observed_signal_profile_minus_strand",
            "Annotation observed signal profile file (minus strand)",
            "path",
        ),
        (
            "observed_control_profile_plus_strand",
            "Annotation observed control profile file (plus strand)",
            "path",
        ),
        (
            "observed_control_profile_minus_strand",
            "Annotation observed control profile file (minus strand)",
            "path",
        ),
        (
            "training_and_test_regions",
            "Annotation training and test regions file",
            "path",
        ),
        (
            "profile_sequence_contribution_scores",
            "Annotation profile sequence contrbiution scores",
            "path",
        ),
        (
            "counts_sequence_contribution_scores",
            "Annotation counts sequence contribution scores",
            "path",
        ),
        ("alignments", "Annotation alignments file accessions", "accession"),
        (
            "unfiltered_alignments",
            "Annotation unfiltered alignments file accessions",
            "accession",
        ),
    ],
}


def build_parser():
    """Return the argument parser for model_annotations.py."""
    p = argparse.ArgumentParser(description="Build a model-annotation table.")
    p.add_argument("--annotation", required=True, help="annotation report Parquet.")
    p.add_argument("--experiment", required=True, help="experiment report Parquet.")
    p.add_argument("--file", required=True, help="file report Parquet.")
    p.add_argument("--model", required=True, choices=sorted(FILE_COLUMNS))
    p.add_argument("--model-dir", required=True, help="Local directory of model files.")
    p.add_argument(
        "--annotation-type",
        action="append",
        required=True,
        dest="annotation_types",
        help="annotation_type to keep; repeatable.",
    )
    p.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Redundant file format as 'output_type::suffix'; repeatable.",
    )
    p.add_argument("--out-table", required=True, help="Parquet table to write.")
    p.add_argument("--out-tsv", required=True, help="TSV table to write.")
    p.add_argument("--out-manifest", required=True, help="aria2c manifest to write.")
    return p


def live(df):
    """Drop rows retracted by ENCODE (deleted/revoked/archived status)."""
    return df.filter(
        pl.col("status")
        .is_in(["deleted", "revoked", "archived"])
        .not_()
        .fill_null(False)
    )


def etl_files(path):
    """file report -> id, file_accession, output_type."""
    return (
        live(pl.read_parquet(path))
        .select("id", "download_url", "output_type")
        .rename({"download_url": "file_accession"})
        .with_columns(pl.col("file_accession").str.split("/").list.last())
    )


def etl_experiments(path):
    """experiment report -> the biosample / assay metadata block."""
    return (
        live(pl.read_parquet(path))
        .select(
            "id",
            "accession",
            "status",
            "perturbed",
            "assay_name",
            "organism",
            "genome_assembly",
            "biosample_classification",
            "biosample_term_name",
            "biosample_ontology",
            "simple_biosample_summary",
            "target_of_assay",
        )
        .rename({"accession": "experiment_accession", "status": "experiment_status"})
    )


def etl_annotations(path):
    """annotation report -> one row per (annotation, experimental_input, file).

    `files` and `contributing_files` are concatenated into a single column with a
    parallel `is_own` flag recording which list each entry came from.
    """
    return (
        live(pl.read_parquet(path))
        .select(
            "accession",
            "status",
            "annotation_type",
            "genome_assembly",
            "date_created",
            pl.col("experimental_input").str.split(","),
            pl.concat_list(
                pl.col("files").str.split(","),
                pl.col("contributing_files").str.split(","),
            ).alias("files"),
            pl.concat_list(
                pl.col("files").str.split(",").list.eval(pl.lit(True)),
                pl.col("contributing_files").str.split(",").list.eval(pl.lit(False)),
            ).alias("is_own"),
        )
        .rename(
            {"accession": "annotation_accession", "status": "annotation_status"}
        )
        .explode("experimental_input")
        .explode("files", "is_own")
    )


def merge_provenance(df):
    """Drop contributing files whose output_type the annotation already produces.

    ENCODE sometimes lists a contributing file borrowed from *another* annotation
    under the same `output_type` as one of this annotation's own files. Stacking
    both into the pivot produces comma-joined multi-file cells, which break the
    manifest's `Path(...).exists()` check and silently contaminate the tables.
    Contributing-only output types (control profiles, alignments, bias models) are
    kept, because the annotation has none of its own to prefer.
    """
    return (
        df.with_columns(
            pl.col("is_own")
            .any()
            .over("annotation_accession", "output_type")
            .alias("_has_own")
        )
        .filter(pl.col("is_own") | pl.col("_has_own").not_())
        .drop("is_own", "_has_own")
    )


def join_tables(annotations, experiments, files):
    """Annotations joined to their experiment and file rows, provenance applied."""
    return merge_provenance(
        annotations.join(
            experiments, how="left", left_on="experimental_input", right_on="id"
        )
        .drop("experimental_input")
        .join(files, how="left", left_on="files", right_on="id")
        .drop("files")
    )


def parse_exclusions(raw):
    """['output type::.suffix', ...] -> [(output_type, suffix), ...]."""
    rules = []
    for item in raw:
        output_type, _, suffix = item.partition("::")
        if not suffix:
            raise ValueError(f"--exclude needs 'output_type::suffix', got {item!r}")
        rules.append((output_type, suffix))
    return rules


def pivot_model(df, annotation_types, exclusions):
    """Filter to one model's annotations and pivot file accessions by output_type."""
    keep = pl.col("annotation_type").is_in(annotation_types)
    for output_type, suffix in exclusions:
        keep = keep & (
            pl.col("output_type").eq(output_type)
            & pl.col("file_accession").str.ends_with(suffix)
        ).not_()

    return (
        df.filter(keep)
        .pivot(
            "output_type",
            values="file_accession",
            aggregate_function=pl.element().implode(),
        )
        .rename(lambda c: slugify(c, separator="_"))
        .drop("null", strict=False)
    )


def dedup_oldest(df):
    """One row per experiment: earliest date_created, ties by descending accession."""
    return (
        df.filter(pl.col("experiment_accession").is_not_null())
        .with_columns(
            pl.col("date_created")
            .str.slice(0, 10)
            .str.to_date("%Y-%m-%d", strict=False)
            .alias("annotation_date")
        )
        .sort(
            ["annotation_date", "annotation_accession"],
            descending=[False, True],
            nulls_last=True,
        )
        .unique(subset="experiment_accession", keep="first", maintain_order=True)
    )


def derive(df, columns, model_dir):
    """Add biosample_term_id and rewrite file columns to paths / bare accessions."""
    missing = [c for c, _, _ in columns if c not in df.columns]
    df = df.with_columns(
        [pl.lit(None, dtype=pl.List(pl.String)).alias(c) for c in missing]
    )

    exprs = [
        pl.col("biosample_ontology")
        .str.extract(r"([A-Za-z]+_\d+)/?$", 1)
        .str.replace("_", ":")
        .alias("biosample_term_id")
    ]
    for source, _, kind in columns:
        if kind == "path":
            exprs.append(
                pl.col(source)
                .list.eval(pl.lit(model_dir + "/") + pl.element())
                .list.join(",")
            )
        else:
            exprs.append(
                pl.col(source)
                .list.eval(pl.element().str.split(".").list.first())
                .list.join(",")
            )
    return df.with_columns(exprs)


def write_manifest(df, columns, path):
    """Write aria2c entries for every path column entry missing from disk."""
    seen = set()
    with open(path, "w") as handle:
        for source, _, kind in columns:
            if kind != "path":
                continue
            for cell in df[source].to_list():
                if not cell:
                    continue
                # is_own keeps these single-valued; split defensively so a stray
                # multi-file cell yields real URLs instead of one bogus path.
                for entry in cell.split(","):
                    target = Path(entry)
                    if target.exists():
                        continue
                    accession = target.name.split(os.extsep)[0]
                    if accession in seen:
                        continue
                    seen.add(accession)
                    url = (
                        f"https://encodeproject.org/{accession}"
                        f"/@@download/{target.name}"
                    )
                    print(f"{target} does not exist")
                    handle.write(
                        MANIFEST_ENTRY_FORMAT.format(
                            url=url, dir=target.parent, out=target.name
                        )
                    )


def main(argv=None):
    """Build one model's annotation table, TSV, and download manifest."""
    args = build_parser().parse_args(argv)
    columns = FILE_COLUMNS[args.model]

    joined = join_tables(
        etl_annotations(args.annotation),
        etl_experiments(args.experiment),
        etl_files(args.file),
    )
    pivoted = pivot_model(
        joined, args.annotation_types, parse_exclusions(args.exclude)
    )
    derived = derive(dedup_oldest(pivoted), columns, args.model_dir)

    write_manifest(derived, columns, args.out_manifest)

    table = derived.select(
        [pl.col(source).alias(header) for source, header in META_COLUMNS]
        + [pl.col(source).alias(header) for source, header, _ in columns]
    ).sort("Annotation accession")

    table.write_parquet(args.out_table)
    table.write_csv(args.out_tsv, separator="\t")

    experiments = table.get_column("Experiment accession").n_unique()
    print(
        f"{args.model}: {table.height} rows, {experiments} experiments, "
        f"{table.width} columns"
    )


if __name__ == "__main__":
    main()
