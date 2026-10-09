# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the repo root.

```sh
cp config/config.yaml.template config/config.yaml    # then set run_id
pixi run snakemake --profile profiles/local          # local
pixi run snakemake --profile profiles/slurm          # SLURM
pixi run snakemake --profile profiles/local -n -p    # dry run
pixi run snakemake --profile profiles/local --config fetch='[lab,award]'  # quick subset
pixi run test                                        # unit tests
pixi run lint                                        # ruff check, ruff format --check, numpydoc lint
```

## Two pixi workspaces

- Root `pixi.toml` is the launcher: Snakemake main and its plugins, plus the `lint` and `test` envs.
- `workflow/envs/pixi.toml` is the rule env. Rule dependencies go there, never in the root.
- The `test` env repeats the rule env's `polars` and `python-slugify` so pytest can import the scripts.
- `pyproject.toml` is ruff, numpydoc, and pytest config only.
- Rules use `locked=True`. After a manifest edit, run `pixi lock` in `workflow/envs/`.
- Any manifest or lock change reruns every rule, `fetch_report` included. An existing `run_id` then
  re-downloads and overwrites its snapshot. Pass `--rerun-triggers mtime` to keep it.
- `SOFTWARE_ENV` resolves `../envs` relative to the rule file. New rule files MUST sit in `workflow/rules/`.
- polars is capped below 2 to match the conda env the snapshots were built with.

## Conventions

This repo follows `~/Projects/snakemake-template`. Read its README before editing rules. In short:

- No `run:` blocks. Custom logic lives in `workflow/scripts/` behind `build_parser()` + `main()`.
- Raw triple-quoted `shell` blocks, one option per line. Every interpolation is quoted with `:q`.
- Config reaches `shell` through `params:`, never interpolated directly.
- Every rule carries `log:`, `benchmark:`, and `software:`.
- `input:`/`output:` are literal relative path strings.
- Docstrings follow numpydoc. The linters skip `.smk` files, so keep the `common.smk` helpers in
  that style by hand.
- Resources are flat values. SLURM `mem_mb` scales by `attempt` for retries. Never derive resources
  from input size.

One deliberate deviation: the template gitignores `config/*.tsv`, but `config/reports.tsv` is
committed here because it is pipeline input, not user-specific config.

## Architecture

`config/reports.tsv` (report_id, url) is the sample sheet. Per report:
`fetch_report` to `clean_report` to `report_parquet`. Then `provenance` fans in over every fetched
report and `summary_card` renders its totals.

`run_id` is the ENCODE snapshot date and everything lands under `results/<run_id>/`. Runs never
overwrite each other. That is why there is no archiving step. Older snapshots are simply older
directories.

`fetch` selects the reports: `all` (114) or a list of `report_id`s.

`netrc` is validated at parse time (exists, mode 600, has an `www.encodeproject.org` entry) because
aria2c silently falls back to anonymous otherwise, and anonymous reports omit unreleased objects.

## Invariants

- **`report_to_parquet.normalize()`** spells out `%` as `pct` and `#` as `num` before slugifying,
  because plain slugify drops both and merges distinct columns. Residual collisions get a
  deterministic `_2` suffix rather than failing the read.

## Verification

There is no CI. Run `pixi run test`, `pixi run lint`, a dry run, and a small real run on a throwaway
`run_id` (`--config run_id=smoke fetch='[lab,award]'`). `report/provenance.tsv` should have one row
per fetched report. Delete the throwaway `results/`, `logs/`, and `benchmarks/` directories after.
