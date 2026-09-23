# encode-metadata

A [Snakemake](https://snakemake.readthedocs.io/) workflow that turns
[ENCODE](https://www.encodeproject.org/) metadata reports into Parquet tables and derives BPNet /
ChromBPNet model-annotation tables and download manifests, using [Polars](https://pola.rs/).

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
uv run snakemake --report report.html               # collect report() outputs
uv run pytest                                       # unit tests
```

`run_id` is the snapshot date and names the output directory. Bump it for a fresh pull; previous
runs are left untouched, so old snapshots need no archiving ritual.

## Targets

The default target builds the model-annotation deliverable, which needs only the `annotation`,
`experiment`, and `file` reports. The other 111 are opt-in:

```sh
uv run snakemake --profile profiles/local                          # 3 reports
uv run snakemake --profile profiles/local --config fetch=all       # all 114
uv run snakemake --profile profiles/local all_reports              # Parquets only
```

## Pipeline

`docs/pipeline-rulegraph.png` shows the rules and `docs/pipeline-dag.png` the concrete jobs of a
default run. Both are Graphviz renderings of Snakemake's own DAG, so they cannot drift from the
workflow. Regenerate with:

```sh
uv run snakemake --profile profiles/local --rulegraph | dot -Tpng -o docs/pipeline-rulegraph.png
uv run snakemake --profile profiles/local --dag       | dot -Tpng -o docs/pipeline-dag.png
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
model_annotations         per model: .tsv, .parquet, .manifest
tarball_manifest          both models' metadata blocks, stacked
provenance                url, fetched_at, bytes, sha256, rows, columns
summary_card              headline numbers, rendered with Typst
```

Outputs land in `results/<run_id>/`:

| Path | Contents |
| --- | --- |
| `reports/<report>.raw.tsv` | untouched ENCODE bytes, kept so a cleaning change costs no re-download |
| `reports/<report>.tsv` | banner stripped, reformatted |
| `parquets/<report>.parquet` | `snake_case` columns |
| `annotations/<model>-model-annotations.{tsv,parquet}` | one row per experiment |
| `annotations/<model>-model-annotations.manifest` | aria2c input for model files missing locally |
| `report/tarball_manifest.tsv` | both models' first 13 metadata columns |
| `report/provenance.tsv` | what was fetched, when, and how big |
| `report/summary.png` | headline numbers for the snapshot |

## Configuration

`config/config.yaml` holds everything environment-specific.

- **`run_id`** names the snapshot directory.
- **`fetch`** lists the reports to materialize, or `all`.
- **`model_dirs`** points at local model-file storage; the manifest lists whatever is missing there.
  These were hard-coded in the old notebook and must be adjusted per machine.
- **`models`** gives each model its `annotation_types` and the redundant file formats to exclude.
  ProCapNet annotations ship inside the ChromBPNet table.
- **`annotation_inputs`** overrides the Parquets feeding the annotation step. Leave it empty to use
  the current run's own output; point it at another vintage to rebuild the tables from older data
  without editing code.

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
- `notebooks/annotation_manifests.py` is superseded by `workflow/scripts/model_annotations.py` and
  is kept only for interactive inspection. It can be deleted once the workflow has replaced it in
  practice.
