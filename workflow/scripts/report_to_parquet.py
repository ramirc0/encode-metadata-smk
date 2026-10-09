"""Cleaned ENCODE report TSV -> Parquet with snake_case columns.

Column names are slugified. Plain `slugify` drops `%` and `#`, which collapses
distinct ENCODE headers onto one name and makes the read fail: in
star_quality_metric_report, `% of chimeric reads` and `# of chimeric reads` both
become `of_chimeric_reads`. Those markers are spelled out before slugifying so a
percentage and a count stay separate columns.
"""

import argparse
import sys

import polars as pl
from slugify import slugify

# Applied to the raw header before slugify, which would otherwise drop them.
_MARKERS = [("%", " pct "), ("#", " num ")]


def build_parser():
    """Build the report_to_parquet.py command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser for the report_to_parquet.py flags.
    """
    p = argparse.ArgumentParser(description="Convert a report TSV to Parquet.")
    p.add_argument("-i", "--input", required=True, help="Cleaned report TSV.")
    p.add_argument("-o", "--output", required=True, help="Parquet file to write.")
    return p


def normalize(name):
    """Convert an ENCODE header to snake_case, keeping `%` and `#` distinct.

    Parameters
    ----------
    name : str
        Raw ENCODE column header.

    Returns
    -------
    str
        Slugified header with `%` spelled `pct` and `#` spelled `num`.
    """
    for marker, replacement in _MARKERS:
        name = name.replace(marker, replacement)
    return slugify(name, separator="_")


def deduplicate(names):
    """Suffix repeated names `_2`, `_3`, ... in order of appearance.

    Parameters
    ----------
    names : list of str
        Column names, possibly repeated.

    Returns
    -------
    list of str
        Names with every repeat after the first suffixed by its count.
    """
    counts, out = {}, []
    for name in names:
        counts[name] = counts.get(name, 0) + 1
        out.append(name if counts[name] == 1 else f"{name}_{counts[name]}")
    return out


def main(argv=None):
    """Read the cleaned TSV, normalize headers, and write Parquet.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments. Defaults to `sys.argv[1:]`.
    """
    args = build_parser().parse_args(argv)

    df = pl.read_csv(
        args.input,
        separator="\t",
        infer_schema_length=2**21,
    )

    normalized = [normalize(c) for c in df.columns]
    final = deduplicate(normalized)
    for before, after in zip(normalized, final):
        if before != after:
            print(f"collision: {before!r} kept as {after!r}", file=sys.stderr)

    df.columns = final
    df.write_parquet(args.output)
    print(f"{args.output}: {df.height} rows x {df.width} columns")


if __name__ == "__main__":
    main()
