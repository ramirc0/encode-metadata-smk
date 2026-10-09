# Config, report sheet, path constants, and shared helpers.

from pathlib import Path

import polars as pl
from snakemake.exceptions import WorkflowError


configfile: "config/config.yaml"


RESULTS = config["outdir"]
RUN_ID = config["run_id"]
OUTDIR = f"{RESULTS}/{RUN_ID}"          # one immutable directory per ENCODE snapshot
LOGDIR = f"logs/{RUN_ID}"
BENCHDIR = f"benchmarks/{RUN_ID}"

# Absolute so conda: resolves the same from any rule file.
CONDA_ENV = str((Path(workflow.basedir).parent / config["conda_env"]).resolve())


_SHEET = Path(config["reports"])
if not _SHEET.exists():
    raise WorkflowError(
        f"Report sheet not found: {_SHEET}\n"
        "Columns: report_id, url; see config/reports.tsv."
    )

# All-string read so empty cells are "" (absent), not a type error.
_rows = pl.read_csv(
    _SHEET, separator="\t", infer_schema_length=0, comment_prefix="#"
)

_ids = _rows.get_column("report_id").to_list()
_duplicates = sorted({r for r in _ids if _ids.count(r) > 1})
if _duplicates:
    # ENCODE's URL list ships byte-identical duplicate lines; two jobs would
    # otherwise race on one output path.
    raise WorkflowError(f"Duplicate report_id in {_SHEET}: {', '.join(_duplicates)}")

URL_OF = {
    row["report_id"]: row["url"] for row in _rows.iter_rows(named=True)
}
REPORTS = list(URL_OF)

if not REPORTS:
    raise WorkflowError(f"Report sheet {_SHEET} has no rows.")


def _fetch_list():
    """config['fetch'] -> the report ids this run materializes."""
    requested = config["fetch"]
    if requested == "all":
        return REPORTS
    unknown = sorted(set(requested) - set(REPORTS))
    if unknown:
        raise WorkflowError(
            f"config['fetch'] names reports absent from {_SHEET}: "
            f"{', '.join(unknown)}"
        )
    return list(requested)


FETCH = _fetch_list()


wildcard_constraints:
    report=r"[a-z0-9][a-z0-9_]*",
