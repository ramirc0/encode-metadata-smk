"""Record what was fetched: url, fetch time, bytes, checksum, and shape.

The notebooks recorded the snapshot date as an empty `.YYYY-MM-DD` sentinel file.
This writes a real table instead, so a derived output can be traced back to the
exact ENCODE bytes it came from.
"""

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

_CHUNK = 1 << 20


def build_parser():
    """Return the argument parser for provenance.py."""
    p = argparse.ArgumentParser(description="Summarize the fetched reports.")
    p.add_argument("--raw", required=True, nargs="+", help="Raw report TSVs.")
    p.add_argument("--parquet", required=True, nargs="+", help="Converted Parquets.")
    p.add_argument("--sheet", required=True, help="Report sheet (report_id, url).")
    p.add_argument("--run-id", required=True, help="Snapshot id for this run.")
    p.add_argument("-o", "--output", required=True, help="Provenance TSV to write.")
    return p


def sha256(path):
    """Hex digest of a file, read in chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def main(argv=None):
    """Join fetched bytes to converted shapes and write one row per report."""
    args = build_parser().parse_args(argv)

    urls = {
        row["report_id"]: row["url"]
        for row in pl.read_csv(
            args.sheet, separator="\t", infer_schema_length=0
        ).iter_rows(named=True)
    }
    parquets = {Path(p).stem: p for p in args.parquet}

    rows = []
    for raw in sorted(args.raw):
        report_id = Path(raw).name.removesuffix(".raw.tsv")
        stat = Path(raw).stat()
        parquet = parquets.get(report_id)
        shape = pl.read_parquet_schema(parquet) if parquet else {}
        rows.append(
            {
                "run_id": args.run_id,
                "report_id": report_id,
                "url": urls.get(report_id),
                "fetched_at": datetime.fromtimestamp(
                    stat.st_mtime, timezone.utc
                ).isoformat(),
                "bytes": stat.st_size,
                "sha256": sha256(raw),
                "rows": pl.scan_parquet(parquet).select(pl.len()).collect().item()
                if parquet
                else None,
                "columns": len(shape),
            }
        )

    df = pl.DataFrame(rows)
    df.write_csv(args.output, separator="\t")
    print(f"{args.output}: {df.height} reports")


if __name__ == "__main__":
    main()
