"""Model annotation tables -> one concatenated metadata manifest.

Takes the leading metadata block (the first 13 columns) of each model table,
tags each row with its model, and stacks them.
"""

import argparse

import polars as pl
from slugify import slugify

META_WIDTH = 13

COLUMN_ORDER = [
    "annotation_accession",
    "annotation_type",
    "annotation_status",
    "experiment_accession",
    "assay_term_name",
    "experiment_status",
    "experiment_peturbed",
    "experiment_target_of_assay",
    "experiment_biosample_term_name",
    "assembly",
    "organism",
    "biosample_simple_summary",
    "biosample_classification",
    "biosample_term_id",
]


def build_parser():
    """Return the argument parser for tarball_manifest.py."""
    p = argparse.ArgumentParser(description="Concatenate model metadata blocks.")
    p.add_argument(
        "-i", "--input", required=True, nargs="+", help="Model annotation Parquets."
    )
    p.add_argument(
        "--model",
        required=True,
        nargs="+",
        help="Model name per input, in the same order.",
    )
    p.add_argument("-o", "--output", required=True, help="TSV to write.")
    return p


def main(argv=None):
    """Stack each model's metadata block into one TSV."""
    args = build_parser().parse_args(argv)
    if len(args.input) != len(args.model):
        raise SystemExit("--input and --model must have the same number of values")

    frames = [
        pl.read_parquet(path, columns=range(META_WIDTH))
        .rename(lambda c: slugify(c, separator="_"))
        # Literal, not the annotation_type column: the ChromBPNet table also
        # holds ProCapNet annotations, which ship under the ChromBPNet label.
        .with_columns(pl.lit(f"{model}-model").alias("annotation_type"))
        .select(COLUMN_ORDER)
        for path, model in zip(args.input, args.model)
    ]

    df = pl.concat(frames, how="vertical")
    df.write_csv(args.output, separator="\t")
    print(f"{args.output}: {df.height} rows x {df.width} columns")


if __name__ == "__main__":
    main()
