# Run-level aggregation: provenance table and headline summary card.


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
        f"{OUTDIR}/report/provenance.tsv",
    output:
        source=f"{OUTDIR}/report/summary.typ",
        card=report(
            f"{OUTDIR}/report/summary.png",
            category="Summary",
            labels={"card": "snapshot headline numbers"},
        ),
    params:
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
            --provenance {input:q} \
            --run-id {params.run_id:q} \
            --output {output.source:q}

        typst compile \
            --format png \
            --ppi 200 \
            {output.source:q} \
            {output.card:q}
        """
