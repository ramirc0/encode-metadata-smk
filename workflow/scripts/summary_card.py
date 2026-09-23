"""Headline numbers for one ENCODE snapshot, emitted as a Typst source file.

Writes `summary.typ`; the rule compiles it to PNG. The card answers "how much is
in this pull" at a glance: reports fetched, bytes, rows, and per-model table size.
"""

import argparse

import polars as pl

# Fixed width so `1fr` and `100%` have something to resolve against; on an
# auto-width page they collapse and the divider disappears.
TEMPLATE = """\
#set page(width: auto, height: auto, margin: 10pt, fill: white)
#set text(size: 10pt)

#block(width: 380pt)[
  #rect(
    width: 100%,
    radius: 5pt,
    inset: 16pt,
    stroke: 0.7pt + luma(55%),
    fill: luma(99%),
  )[
    #text(size: 13pt, weight: "bold")[ENCODE snapshot #RUN_ID]
    #h(1fr)
    #text(size: 9pt, fill: luma(45%))[#SUBTITLE]

    #v(4pt)

    #grid(
      columns: (1fr, 1fr, 1fr),
      row-gutter: 3pt,
      #HEADLINES
    )

    #v(10pt)
    #line(length: 100%, stroke: 0.4pt + luma(80%))
    #v(8pt)

    #grid(
      columns: (1fr, auto, auto, auto),
      column-gutter: 14pt,
      row-gutter: 4pt,
      #MODELROWS
    )

    #v(10pt)
    #line(length: 100%, stroke: 0.4pt + luma(80%))
    #v(6pt)
    #text(size: 9pt, fill: luma(45%))[#FOOTER]
  ]
]
"""


def build_parser():
    """Return the argument parser for summary_card.py."""
    p = argparse.ArgumentParser(description="Render snapshot headline numbers.")
    p.add_argument("--provenance", required=True, help="provenance.tsv.")
    p.add_argument(
        "--table", required=True, nargs="+", help="Model annotation Parquets."
    )
    p.add_argument(
        "--manifest", required=True, nargs="+", help="Model download manifests."
    )
    p.add_argument(
        "--model", required=True, nargs="+", help="Model name per table, in order."
    )
    p.add_argument("--run-id", required=True, help="Snapshot id.")
    p.add_argument("-o", "--output", required=True, help="Typst source to write.")
    return p


def human_bytes(n):
    """Byte count -> a short human-readable string."""
    size = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024


def human_count(n):
    """Row count -> a short human-readable string."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M"
    if n >= 1_000:
        return f"{n / 1_000:.1f} K"
    return str(n)


def _cell(value, label):
    """One headline number stacked over its caption."""
    return (
        f'[#text(size: 20pt, weight: "bold")[{value}] \\ '
        f"#text(size: 8.5pt, fill: luma(40%))[{label}]]"
    )


def _header_row(labels):
    """Bold header cells; every column but the first right-aligned."""
    cells = [f'[#text(weight: "bold")[{labels[0]}]]'] + [
        f'[#align(right)[#text(weight: "bold")[{label}]]]' for label in labels[1:]
    ]
    return ", ".join(cells) + ","


def main(argv=None):
    """Read the run's outputs and write the Typst card source."""
    args = build_parser().parse_args(argv)
    if not len(args.table) == len(args.manifest) == len(args.model):
        raise SystemExit("--table, --manifest and --model must be the same length")

    prov = pl.read_csv(args.provenance, separator="\t")
    total_bytes = int(prov.get_column("bytes").sum())
    total_rows = int(prov.get_column("rows").fill_null(0).sum())

    headlines = [
        _cell(prov.height, "reports fetched"),
        _cell(human_bytes(total_bytes), "downloaded"),
        _cell(human_count(total_rows), "metadata rows"),
    ]

    queued = 0
    model_rows = [_header_row(["model", "annotations", "experiments", "queued"])]
    for model, table, manifest in zip(args.model, args.table, args.manifest):
        df = pl.read_parquet(table)
        experiments = df.get_column("Experiment accession").n_unique()
        with open(manifest) as handle:
            pending = sum(1 for line in handle if line.startswith("http"))
        queued += pending
        model_rows.append(
            f"[{model}], "
            + ", ".join(
                f"[#align(right)[{value:,}]]"
                for value in (df.height, experiments, pending)
            )
            + ","
        )

    source = (
        TEMPLATE.replace("#RUN_ID", args.run_id)
        .replace("#SUBTITLE", f"{len(args.model)} model tables")
        .replace("#HEADLINES", "\n    ".join(f"{c}," for c in headlines))
        .replace("#MODELROWS", "\n    ".join(model_rows))
        .replace(
            "#FOOTER",
            f"{queued} model files queued for download"
            if queued
            else "all model files present locally",
        )
    )

    with open(args.output, "w") as handle:
        handle.write(source)
    print(f"{args.output}: {prov.height} reports, {human_bytes(total_bytes)}")


if __name__ == "__main__":
    main()
