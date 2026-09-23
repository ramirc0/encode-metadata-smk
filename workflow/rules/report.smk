# Run-level aggregation: tarball manifest, provenance, headline summary card.


rule tarball_manifest:
    input:
        tables=expand(
            f"{OUTDIR}/annotations/{{model}}-model-annotations.parquet", model=MODELS
        ),
    output:
        f"{OUTDIR}/report/tarball_manifest.tsv",
    params:
        models=MODELS,
    log:
        f"{LOGDIR}/tarball_manifest.txt",
    benchmark:
        f"{BENCHDIR}/tarball_manifest.tsv",
    conda:
        CONDA_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        python workflow/scripts/tarball_manifest.py \
            --input {input.tables:q} \
            --model {params.models:q} \
            --output {output:q}
        """


# One row per materialized report: url, fetch time, bytes, sha256, rows, cols.
rule provenance:
    input:
        raw=expand(f"{OUTDIR}/reports/{{report}}.raw.tsv", report=FETCH),
        parquets=expand(f"{OUTDIR}/parquets/{{report}}.parquet", report=FETCH),
    output:
        f"{OUTDIR}/report/provenance.tsv",
    params:
        sheet=config["reports"],
        run_id=RUN_ID,
    log:
        f"{LOGDIR}/provenance.txt",
    benchmark:
        f"{BENCHDIR}/provenance.tsv",
    conda:
        CONDA_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        python workflow/scripts/provenance.py \
            --raw {input.raw:q} \
            --parquet {input.parquets:q} \
            --sheet {params.sheet:q} \
            --run-id {params.run_id:q} \
            --output {output:q}
        """


rule summary_card:
    input:
        provenance=f"{OUTDIR}/report/provenance.tsv",
        tables=expand(
            f"{OUTDIR}/annotations/{{model}}-model-annotations.parquet", model=MODELS
        ),
        manifests=expand(
            f"{OUTDIR}/annotations/{{model}}-model-annotations.manifest", model=MODELS
        ),
    output:
        source=f"{OUTDIR}/report/summary.typ",
        card=report(
            f"{OUTDIR}/report/summary.png",
            category="Summary",
            labels={"card": "snapshot headline numbers"},
        ),
    params:
        models=MODELS,
        run_id=RUN_ID,
    log:
        f"{LOGDIR}/summary_card.txt",
    benchmark:
        f"{BENCHDIR}/summary_card.tsv",
    conda:
        CONDA_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        python workflow/scripts/summary_card.py \
            --provenance {input.provenance:q} \
            --table {input.tables:q} \
            --manifest {input.manifests:q} \
            --model {params.models:q} \
            --run-id {params.run_id:q} \
            --output {output.source:q}

        typst compile \
            --format png \
            --ppi 200 \
            {output.source:q} \
            {output.card:q}
        """
