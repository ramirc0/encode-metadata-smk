# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the repo root.

```sh
uv sync                                              # install the snakemake driver + dev deps
cp config/config.yaml.template config/config.yaml    # then set run_id
uv run snakemake --profile profiles/local            # local
uv run snakemake --profile profiles/slurm            # SLURM
uv run snakemake --profile profiles/local -n -p      # dry run
uv run snakemake --profile profiles/local --config fetch='[lab,award]'  # quick subset
uv run pytest                                        # unit tests
```

`snakemake` comes from uv; everything a rule needs at run time (`polars`, `python-slugify`,
`aria2c`, `qsv`, `typst`) comes from the conda env in `workflow/envs/env.yaml`.

## Conventions

This repo follows `~/Projects/snakemake-template`. Read its README before editing rules. In short:
no `run:` blocks, custom logic lives in `workflow/scripts/` behind `build_parser()` + `main()`; raw
triple-quoted `shell` blocks with one option per line; every interpolation quoted with `:q`; config
reaches `shell` through `params:`, never interpolated directly; every rule carries `log:`,
`benchmark:`, and `conda:`; `input:`/`output:` are literal relative path strings.

One deliberate deviation: the template gitignores `config/*.tsv`, but `config/reports.tsv` is
committed here because it is pipeline input, not user-specific config.

## Architecture

`config/reports.tsv` (report_id, url) is the sample sheet. Per report:
`fetch_report` to `clean_report` to `report_parquet`. Then `provenance` fans in over every fetched
report and `summary_card` renders its totals.

`run_id` is the ENCODE snapshot date and everything lands under `results/<run_id>/`. Runs never
overwrite each other, which is why there is no archiving step; older snapshots are simply older
directories.

`fetch` selects the reports: `all` (114) or a list of `report_id`s.

## Invariants

- **`report_to_parquet.normalize()`** spells out `%` as `pct` and `#` as `num` before slugifying,
  because plain slugify drops both and merges distinct columns. Residual collisions get a
  deterministic `_2` suffix rather than failing the read.

## Verification

There is no CI. Run `uv run pytest`, a dry run, and a small real run
(`--config fetch='[lab,award]'`); `report/provenance.tsv` should have one row per fetched report.
