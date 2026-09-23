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
uv run snakemake --profile profiles/local all_reports  # all 114 reports, not just 3
uv run pytest                                        # unit tests
uv run pytest tests/test_model_annotations.py::test_own_file_wins_over_borrowed_contributing_file
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
`fetch_report` to `clean_report` to `report_parquet`. Then `model_annotations` fans in over three of
those Parquets, and `tarball_manifest` / `provenance` / `summary_card` aggregate.

`run_id` is the ENCODE snapshot date and everything lands under `results/<run_id>/`. Runs never
overwrite each other, which is why there is no archiving step; older snapshots are simply older
directories.

The default target needs only the `annotation`, `experiment`, and `file` reports. `fetch: all` or
the `all_reports` target pulls all 114.

## Invariants

Before editing `workflow/scripts/model_annotations.py`, know these. They are ported from the
original notebook and several were bug fixes.

- **`live()`** drops rows whose `status` is `deleted`, `revoked`, or `archived`. Applied to all
  three input tables.
- **`merge_provenance()`** is the subtle one. An annotation's own `files` and its
  `contributing_files` are concatenated with a parallel `is_own` flag. ENCODE sometimes lists a
  contributing file borrowed from *another* annotation under the **same `output_type`** as one of
  the annotation's own files, so own files win per `(annotation_accession, output_type)` and
  contributing files are kept only where the annotation has none of its own. Dropping this
  reintroduces comma-joined multi-file cells, which break the manifest's `Path(...).exists()` check
  and silently contaminate the tables. Contributing-only output types (control profiles, alignments,
  bias models) still survive. Covered by `tests/test_model_annotations.py`.
- **`dedup_oldest()`** keeps one row per `experiment_accession`, preferring the earliest
  `date_created`, tie-broken by descending accession. Output tables are 1:1 annotation to experiment.
- **`FILE_COLUMNS`** defines each model's output schema. `path` columns are rewritten to absolute
  paths under `model_dirs` and are what the download manifest is built from; `accession` columns
  keep bare accessions. The headers `"Experiment peturbed"` and `"Annotation profile sequence
  contrbiution scores"` carry typos from the original notebook and are preserved deliberately;
  downstream consumers depend on them.
- **`report_to_parquet.normalize()`** spells out `%` as `pct` and `#` as `num` before slugifying,
  because plain slugify drops both and merges distinct columns. Residual collisions get a
  deterministic `_2` suffix rather than failing the read.

## Verification

There is no CI. The regression test that matters: point `annotation_inputs` at
`resources/{annotations,experiments,files}.parquet` and confirm the rebuilt tables match
`output/*.parquet` exactly (3535 BPNet rows, 1552 ChromBPNet, 5087 tarball rows as of the Jul-07
vintage). The ported scripts reproduce those byte-for-byte.
