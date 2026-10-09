# encode-metadata

A [Snakemake](https://snakemake.readthedocs.io/) workflow that turns
[ENCODE](https://www.encodeproject.org/) metadata reports into Parquet tables using
[Polars](https://pola.rs/).

Each run materializes one immutable snapshot under `results/<run_id>/`, alongside a provenance
table recording the URL, fetch time, byte count, and SHA-256 of every report it pulled.

## Prerequisites

- Python >= 3.12 and [uv](https://docs.astral.sh/uv/) (provides the `snakemake` driver)
- `conda` (rule environments are built from `workflow/envs/env.yaml`)

Everything each rule needs at run time (`polars`, `python-slugify`, `aria2c`, `qsv`, `typst`) comes
from the conda environment, so nothing has to be on `PATH` beforehand.

```sh
uv sync
```

## Running

```sh
cp config/config.yaml.template config/config.yaml   # then set run_id
uv run snakemake --profile profiles/local           # local
uv run snakemake --profile profiles/slurm           # SLURM
uv run snakemake --profile profiles/local -n -p     # dry run
uv run pytest                                       # unit tests
```

`run_id` is the snapshot date and names the output directory. Bump it for a fresh pull; previous
runs are left untouched, so old snapshots need no archiving ritual.

## Targets

The default target fetches every report in `fetch`, converts each to Parquet, and writes the
provenance table and summary card. `fetch: all` pulls all 114 reports; narrow it for a quick run:

```sh
uv run snakemake --profile profiles/local --config fetch='[lab,award]'
```

## Pipeline

`docs/pipeline-rulegraph.png` shows the rules and `docs/pipeline-dag.png` the concrete jobs of a
three-report run. Both are rendered from Snakemake's own DAG; regenerate them after changing rules:

```sh
uv run snakemake --profile profiles/local --rulegraph -q | dot -Tpng -o docs/pipeline-rulegraph.png
uv run snakemake --profile profiles/local --dag -q --config 'fetch=[annotation,experiment,file]' \
    | dot -Tpng -o docs/pipeline-dag.png
```

```
config/reports.tsv        report_id + URL, one row per ENCODE object type
      |
      v
fetch_report              aria2c -> results/<run_id>/reports/<report>.raw.tsv
clean_report              strip banner line, qsv fmt -> <report>.tsv
report_parquet            snake_case columns -> parquets/<report>.parquet
      |
      v
provenance                url, fetched_at, bytes, sha256, rows, columns
summary_card              headline numbers, rendered with Typst
```

Outputs land in `results/<run_id>/`:

| Path | Contents |
| --- | --- |
| `reports/<report>.raw.tsv` | untouched ENCODE bytes, kept so a cleaning change costs no re-download |
| `reports/<report>.tsv` | banner stripped, reformatted |
| `parquets/<report>.parquet` | `snake_case` columns |
| `report/provenance.tsv` | what was fetched, when, and how big |
| `report/summary.{typ,png}` | headline numbers for the snapshot |

## Configuration

`config/config.yaml` holds everything environment-specific.

- **`run_id`** names the snapshot directory.
- **`fetch`** lists the reports to materialize, or `all`.
- **`netrc`** supplies ENCODE credentials: `true` for `~/.netrc`, a path, or `false` for anonymous.
  Anonymous reports omit unreleased objects. The file must be mode 600 with a
  `machine www.encodeproject.org` entry; the workflow refuses to start otherwise, since aria2c
  would silently fall back to anonymous.

## Notes

- `config/reports.tsv` is committed, so the exact field set requested from ENCODE is version
  controlled. ENCODE's published URL list contains a duplicate entry
  (`ScrnaSeqCountsSummaryQualityMetric`); the sheet is deduplicated and the workflow rejects
  repeated `report_id`s rather than letting two jobs race on one output.
- Report ids cannot be derived reliably from the URL's `type=` parameter: `IDRQualityMetric` is
  served as `idr_quality_metric`. They are therefore stored explicitly in the sheet.
- Column names are normalized with `%` and `#` spelled out before slugifying. Plain slugify drops
  both, collapsing `% of chimeric reads` and `# of chimeric reads` onto one name; three reports
  (`document`, `samtools_flagstats_quality_metric`, `star_quality_metric`) previously failed to
  convert for this reason and were silently skipped.
