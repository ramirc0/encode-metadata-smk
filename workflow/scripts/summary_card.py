"""Headline numbers for one ENCODE snapshot, emitted as a Typst source file.

Writes `summary.typ`; the rule compiles it to PNG. The card answers "how much is
in this pull" at a glance: reports fetched, bytes downloaded, and rows.
"""

import argparse

import polars as pl

# Fixed width so `1fr` and `100%` have something to resolve against. On an
# auto-width page they collapse.
TEMPLATE = """\
#set page(width: auto, height: auto, margin: 10pt, fill: white)
#set text(size: 10pt, font: "Anthropic Serif Text")

#block(width: 380pt)[
  #rect(
    width: 100%,
    radius: 5pt,
    inset: 16pt,
    stroke: 0.7pt + luma(55%),
    fill: luma(99%),
  )[
    #text(size: 13pt, weight: "bold")[ENCODE snapshot #RUN_ID]

    #v(4pt)

    #grid(
      columns: (1fr, 1fr, 1fr),
      row-gutter: 3pt,
      #HEADLINES
    )
  ]
]
"""


def build_parser():
    """Build the summary_card.py command-line parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser for the summary_card.py flags.
    """
    p = argparse.ArgumentParser(description="Render snapshot headline numbers.")
    p.add_argument("--provenance", required=True, help="provenance.tsv.")
    p.add_argument("--run-id", required=True, help="Snapshot id.")
    p.add_argument("-o", "--output", required=True, help="Typst source to write.")
    return p


def human_bytes(n):
    """Format a byte count with a binary unit.

    Parameters
    ----------
    n : int
        Byte count.

    Returns
    -------
    str
        Count scaled to B, KB, MB, GB, or TB.
    """
    size = float(n)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.1f} {unit}"
        size /= 1024


def human_count(n):
    """Format a row count with a K or M suffix.

    Parameters
    ----------
    n : int
        Row count.

    Returns
    -------
    str
        Count as is below 1,000, else scaled to K or M with one decimal.
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M"
    if n >= 1_000:
        return f"{n / 1_000:.1f} K"
    return str(n)


def _cell(value, label):
    """Stack one headline number over its caption.

    Parameters
    ----------
    value : int or str
        Headline number, already formatted.
    label : str
        Caption under the number.

    Returns
    -------
    str
        Typst content block for one grid cell.
    """
    return (
        f'[#text(size: 20pt, weight: "bold")[{value}] \\ '
        f"#text(size: 8.5pt, fill: luma(40%))[{label}]]"
    )


def main(argv=None):
    """Read the provenance table and write the Typst card source.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments. Defaults to `sys.argv[1:]`.
    """
    args = build_parser().parse_args(argv)

    prov = pl.read_csv(args.provenance, separator="\t")
    total_bytes = int(prov.get_column("bytes").sum())
    total_rows = int(prov.get_column("rows").sum())

    headlines = [
        _cell(prov.height, "reports fetched"),
        _cell(human_bytes(total_bytes), "downloaded"),
        _cell(human_count(total_rows), "metadata rows"),
    ]

    source = TEMPLATE.replace("#RUN_ID", args.run_id).replace(
        "#HEADLINES", "\n    ".join(f"{c}," for c in headlines)
    )

    with open(args.output, "w") as handle:
        handle.write(source)
    print(f"{args.output}: {prov.height} reports, {human_bytes(total_bytes)}")


if __name__ == "__main__":
    main()
